import os
import json
import time
from flask import Flask, request, jsonify

print(json.dumps({"log_name": "ServerStartup", "mensaje": "main.py cargado. Flask app inicializada."}))

app = Flask(__name__)

def format_chat_response(text_message: str) -> dict:
    """Envuelve un texto en el formato de tarjeta de Google Chat."""
    return { "text": text_message } # Usamos el formato simple de texto para el saludo.

@app.route("/", methods=["POST"])
def handle_chat_event():
    start_time = time.time()
    event_data = request.get_json(silent=True) or {}
    print(json.dumps({"log_name": "HandleChatEvent_Entrada", "evento_recibido": event_data}))

    response_payload = {} # Por defecto, no respondemos nada.

    try:
        event_type = event_data.get('type')

        # --- CAMBIO CLAVE: Manejar el evento cuando se añade el bot a un espacio ---
        if event_type == 'ADDED_TO_SPACE':
            print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": "Bot añadido a un espacio. Enviando saludo."}))
            response_payload = format_chat_response("¡Gracias por añadirme! Soy Dex, tu asistente de Helpdesk con IA. Escribe tu solicitud para empezar.")

        elif event_type == 'MESSAGE':
            print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": "Importando src.logic para procesar mensaje..."}))
            from src.logic import handle_dex_logic
            print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": "src.logic importado."}))

            user_message_text = event_data.get("message", {}).get("text", "").strip()
            user_info = event_data.get("user", {})
            user_email = user_info.get("email")
            user_display_name = user_info.get("displayName", "Usuario")

            if user_message_text and user_email:
                logic_response_text = handle_dex_logic(user_message=user_message_text, user_email=user_email, user_display_name=user_display_name)
                # Para los mensajes, usamos el formato de tarjeta más complejo.
                response_payload = {
                    "cardsV2": [{"cardId": "responseCard", "card": {"sections": [{"widgets": [{"textParagraph": {"text": logic_response_text}}]}]}}]
                }
        else:
            print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": f"Ignorando evento de tipo '{event_type}'."}))

    except Exception as e:
        print(json.dumps({"log_name": "HandleChatEvent_Error", "nivel": "CRITICO", "error": str(e)}))
        response_payload = format_chat_response("Ocurrió un error inesperado.")
    
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