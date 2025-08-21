import os
import json
import time
from flask import Flask, request, jsonify
from src.logic import handle_dex_logic

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    """
    Punto de entrada que recibe eventos de Google Chat, extrae los datos clave del usuario
    y los pasa a la lógica principal para ser procesados.
    """
    start_time = time.time()
    event_data = request.get_json(silent=True)
    
    log_entry = {
        "mensaje": "Procesando evento de Google Chat",
        "evento_recibido": event_data,
        "respuesta_enviada": None,
        "error": None,
        "duracion_ms": None
    }

    try:
        # --- ESTA ES LA LÓGICA CORREGIDA ---
        # La información del mensaje está dentro de event_data['message']
        message_info = event_data.get("message")
        
        # Procede solo si el objeto 'message' y su 'text' existen
        if message_info and message_info.get("text"):
            user_message_text = message_info.get("text")

            # La información del usuario que envía el mensaje está en el objeto 'user'
            user_info = event_data.get("user", {})
            user_email = user_info.get("email")
            user_display_name = user_info.get("displayName", "Usuario") # Usamos "Usuario" como fallback

            # Llama a la lógica principal con los argumentos correctos
            response_payload = handle_dex_logic(
                user_message=user_message_text, 
                user_email=user_email, 
                user_display_name=user_display_name
            )
            log_entry["respuesta_enviada"] = response_payload
        else:
            log_entry["mensaje"] = "Ignorando evento que no es un mensaje de usuario (sin 'message' o 'text')."
            response_payload = {}

    except Exception as e:
        log_entry["error"] = str(e)
        response_payload = {
            "cardsV2": [{
                "cardId": "errorCard",
                "card": {
                    "sections": [{
                        "widgets": [{
                            "textParagraph": {
                                "text": "Ocurrió un error inesperado en el servidor."
                            }
                        }]
                    }]
                }
            }]
        }
        log_entry["respuesta_enviada"] = response_payload
    
    finally:
        end_time = time.time()
        log_entry["duracion_ms"] = int((end_time - start_time) * 1000)
        print(json.dumps(log_entry))

    return jsonify(response_payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)