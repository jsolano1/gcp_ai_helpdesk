import os
import json
import time
from flask import Flask, request, jsonify

print(json.dumps({"log_name": "ServerStartup", "mensaje": "main.py cargado. Flask app inicializada."}))

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    start_time = time.time()
    event_data = request.get_json(silent=True) or {}
    print(json.dumps({"log_name": "HandleChatEvent_Entrada", "evento_recibido": event_data}))

    response_payload = {}

    try:
        # --- CAMBIO FINAL: Leemos la estructura JSON correcta ---
        chat_event = event_data.get("chat", {})
        
        # Verificamos si es un evento de MENSAJE buscando la existencia del objeto 'message'
        if chat_event.get("messagePayload", {}).get("message"):
            print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": "Evento de tipo MENSAJE detectado."}))
            
            # Importamos la lógica solo cuando es necesario
            from src.logic import handle_dex_logic
            
            # Extraemos los datos de sus ubicaciones correctas
            user_message_text = chat_event.get("messagePayload", {}).get("message", {}).get("text", "").strip()
            user_info = chat_event.get("user", {})
            user_email = user_info.get("email")
            user_display_name = user_info.get("displayName", "Usuario")

            if user_message_text and user_email:
                logic_response_text = handle_dex_logic(user_message=user_message_text, user_email=user_email, user_display_name=user_display_name)
                response_payload = {
                    "cardsV2": [{"cardId": "responseCard", "card": {"sections": [{"widgets": [{"textParagraph": {"text": logic_response_text}}]}]}}]
                }
        else:
            # Si no es un evento de mensaje, lo ignoramos educadamente.
            # Podríamos añadir lógica para 'ADDED_TO_SPACE' aquí en el futuro si quisiéramos.
            print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": "Ignorando evento que no es de tipo MENSAJE."}))

    except Exception as e:
        print(json.dumps({"log_name": "HandleChatEvent_Error", "nivel": "CRITICO", "error": str(e)}))
        response_payload = {"text": "Ocurrió un error inesperado al procesar tu solicitud."}
    
    finally:
        end_time = time.time()
        print(json.dumps({
            "log_name": "HandleChatEvent_Salida", "duracion_ms": int((end_time - start_time) * 1000),
            "respuesta_enviada": response_payload
        }))
    
    return jsonify(response_payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)