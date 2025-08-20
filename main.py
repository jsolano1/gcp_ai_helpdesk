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
        # Extrae el texto del mensaje del usuario
        user_message_text = event_data.get("message", {}).get("text")
        
        # Procede solo si es un mensaje de usuario con texto
        if user_message_text:
            # Extrae la información del usuario del payload
            user_info = event_data.get("user", {})
            user_email = user_info.get("email")
            
            # El nombre a mostrar (displayName) está en el objeto "sender"
            sender_info = event_data.get("message", {}).get("sender", {})
            user_display_name = sender_info.get("displayName", "Usuario") # Usamos "Usuario" como fallback

            # Llama a la lógica principal con los TRES argumentos requeridos
            response_payload = handle_dex_logic(
                user_message=user_message_text, 
                user_email=user_email, 
                user_display_name=user_display_name
            )
            log_entry["respuesta_enviada"] = response_payload
        else:
            log_entry["mensaje"] = "Ignorando evento que no es un mensaje de usuario."
            response_payload = {}

    except Exception as e:
        log_entry["error"] = str(e)
        # Importante: La respuesta de error también debe estar en formato de Tarjeta
        # para que Chat la pueda mostrar.
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