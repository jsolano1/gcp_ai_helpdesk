import os
import json
import time
from flask import Flask, request, jsonify

# --- Importaciones de Google Cloud ---
# Las importaciones están bien a nivel global, pero no la inicialización de clientes.
from google.cloud import tasks_v2
from google.protobuf import timestamp_pb2

print(json.dumps({"log_name": "ServerStartup", "mensaje": "main.py cargado. Flask app inicializada."}))

# --- CONFIGURACIÓN DE CLOUD TASKS ---
GCP_PROJECT = os.getenv("GCP_PROJECT_ID")
GCP_LOCATION = os.getenv("LOCATION")
TASK_QUEUE = "dex-helpdesk-tasks" # Asegúrate de que este sea el nombre de tu fila
APP_URL = os.getenv("CLOUD_RUN_URL")

# --- INICIALIZACIÓN DIFERIDA DEL CLIENTE DE TASKS ---
tasks_client = None

def get_tasks_client():
    """Inicializa y devuelve el cliente de Cloud Tasks, asegurando que solo se cree una vez."""
    global tasks_client
    if tasks_client is None:
        print(json.dumps({"log_name": "ClientInit", "mensaje": "Inicializando CloudTasksClient por primera vez."}))
        tasks_client = tasks_v2.CloudTasksClient()
    return tasks_client

app = Flask(__name__)

# --- ENDPOINT 1: Interacción con el usuario ---
@app.route("/", methods=["POST"])
def handle_chat_event():
    event_data = request.get_json(silent=True) or {}
    print(json.dumps({"log_name": "HandleChatEvent_Entrada", "evento": event_data}))
    
    try:
        chat_event = event_data.get("chat", {})
        if chat_event.get("messagePayload", {}).get("message"):
            
            user_message = chat_event.get("messagePayload", {}).get("message", {}).get("text", "").strip()
            user_info = chat_event.get("user", {})
            
            task_payload = {
                "user_message": user_message,
                "user_email": user_info.get("email"),
                "user_display_name": user_info.get("displayName")
            }
            
            # --- Obtenemos el cliente usando nuestra función segura ---
            client = get_tasks_client()
            parent = client.queue_path(GCP_PROJECT, GCP_LOCATION, TASK_QUEUE)
            
            task = {
                "http_request": {
                    "http_method": tasks_v2.HttpMethod.POST,
                    "url": f"{APP_URL}/process-task",
                    "headers": {"Content-type": "application/json"},
                    "body": json.dumps(task_payload).encode()
                }
            }
            client.create_task(parent=parent, task=task)
            
            # RESPUESTA INMEDIATA
            return jsonify({"text": "Recibido. Estoy procesando tu solicitud, te avisaré en un momento..."})
        else:
            return jsonify({})

    except Exception as e:
        print(json.dumps({"log_name": "HandleChatEvent_Error", "error": str(e), "traceback": traceback.format_exc()}))
        return jsonify({"text": "Ocurrió un error al iniciar tu solicitud."})

# --- ENDPOINT 2: El trabajador que procesa la tarea ---
@app.route("/process-task", methods=["POST"])
def process_task_handler():
    task_payload = request.get_json(silent=True) or {}
    print(json.dumps({"log_name": "ProcessTask_Inicio", "payload": task_payload}))

    try:
        from src.logic import execute_task_and_get_reply
        from src.services.notification_service import enviar_notificacion_chat

        final_reply = execute_task_and_get_reply(
            user_message=task_payload.get("user_message"),
            user_email=task_payload.get("user_email"),
            user_display_name=task_payload.get("user_display_name")
        )
        enviar_notificacion_chat(final_reply)
        return "OK", 200
    except Exception as e:
        print(json.dumps({"log_name": "ProcessTask_Error", "error": str(e), "traceback": traceback.format_exc()}))
        return "Error", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)