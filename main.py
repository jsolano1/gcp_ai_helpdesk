import os
import json
import time
from flask import Flask, request, jsonify
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

# --- CONFIGURACIÓN DE CLOUD TASKS ---
GCP_PROJECT = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("LOCATION") # ej. 'us-central1'
TASK_QUEUE = "dex-helpdesk-tasks" # El nombre de la fila que creaste
APP_URL = os.getenv("CLOUD_RUN_URL") # La URL de tu servicio de Cloud Run

tasks_client = tasks_v2.CloudTasksClient()

app = Flask(__name__)

# --- ENDPOINT 1: Interacción con el usuario ---
@app.route("/", methods=["POST"])
def handle_chat_event():
    event_data = request.get_json(silent=True) or {}
    print(json.dumps({"log_name": "HandleChatEvent_Entrada", "evento": event_data}))
    
    try:
        chat_event = event_data.get("chat", {})
        if chat_event.get("messagePayload", {}).get("message"):
            
            # Extraemos los datos para pasarlos a la tarea
            user_message = chat_event.get("messagePayload", {}).get("message", {}).get("text", "").strip()
            user_info = chat_event.get("user", {})
            
            task_payload = {
                "user_message": user_message,
                "user_email": user_info.get("email"),
                "user_display_name": user_info.get("displayName")
            }
            
            # Creamos la tarea en Cloud Tasks
            parent = tasks_client.queue_path(GCP_PROJECT, GCP_LOCATION, TASK_QUEUE)
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{APP_URL}/process-task", # Apunta al nuevo endpoint del trabajador
                    "headers": {"Content-type": "application/json"},
                    "body": json.dumps(task_payload).encode()
                }
            }
            tasks_client.create_task(parent=parent, task=task)
            
            # --- RESPUESTA INMEDIATA ---
            return jsonify({"text": "Recibido. Estoy procesando tu solicitud, te avisaré en un momento..."})
        else:
            return jsonify({})

    except Exception as e:
        print(f"Error creando la tarea: {e}")
        return jsonify({"text": "Ocurrió un error al iniciar tu solicitud."})

# --- ENDPOINT 2: El trabajador que procesa la tarea ---
@app.route("/process-task", methods=["POST"])
def process_task_handler():
    task_payload = request.get_json(silent=True) or {}
    print(json.dumps({"log_name": "ProcessTask_Inicio", "payload": task_payload}))

    try:
        # Importamos la lógica y los servicios necesarios
        from src.logic import execute_task_and_get_reply
        from src.services.notification_service import enviar_notificacion_chat

        # Ejecutamos la tarea pesada
        final_reply = execute_task_and_get_reply(
            user_message=task_payload.get("user_message"),
            user_email=task_payload.get("user_email"),
            user_display_name=task_payload.get("user_display_name")
        )

        # Enviamos la respuesta final al chat usando el webhook
        enviar_notificacion_chat(final_reply)

        # Devolvemos un 200 para decirle a Cloud Tasks que la tarea fue exitosa
        return "OK", 200

    except Exception as e:
        print(f"Error procesando la tarea: {e}")
        # Devolvemos un error para que Cloud Tasks pueda reintentar si es necesario
        return "Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)