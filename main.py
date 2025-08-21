# main.py

import os
import json
import time
from flask import Flask, request, jsonify
from src.logic import handle_dex_logic

app = Flask(__name__)

def format_chat_response(text_message: str) -> dict:
    """
    Toma un mensaje de texto simple y lo envuelve en el formato de tarjeta
    JSON que la API de Google Chat requiere.
    """
    return {
        "cardsV2": [
            {
                "cardId": "responseCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": text_message
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        ]
    }

@app.route("/", methods=["POST"])
def handle_chat_event():
    """
    Punto de entrada que recibe eventos de Google Chat, los valida,
    pasa la lógica a un manejador separado y formatea la respuesta final.
    """
    start_time = time.time()
    event_data = request.get_json(silent=True) or {}
    
    print(json.dumps({"log_name": "HandleChatEvent_Entrada", "evento_recibido": event_data}))

    response_payload = {}  # Respuesta vacía por defecto para eventos ignorados

    try:
        event_type = event_data.get('type')

        if event_type == 'MESSAGE':
            user_message_text = event_data.get("message", {}).get("text", "").strip()
            user_info = event_data.get("user", {})
            user_email = user_info.get("email")
            user_display_name = user_info.get("displayName", "Usuario")

            if user_message_text and user_email:
                # 1. Llama a la lógica para obtener una respuesta de texto simple
                logic_response_text = handle_dex_logic(
                    user_message=user_message_text,
                    user_email=user_email,
                    user_display_name=user_display_name
                )
                
                # 2. Formatea esa respuesta para Google Chat
                response_payload = format_chat_response(logic_response_text)
            else:
                print(json.dumps({"log_name": "HandleChatEvent_Alerta", "mensaje": "Evento de mensaje ignorado (sin texto o email)."}))
        
        else:
            print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": f"Ignorando evento de tipo '{event_type}'."}))

    except Exception as e:
        print(json.dumps({
            "log_name": "HandleChatEvent_Error",
            "nivel": "CRITICO",
            "mensaje": "Error no manejado en el nivel superior del endpoint.",
            "error": str(e)
        }))
        # Crear una respuesta de error para el usuario
        error_text = "Ocurrió un error inesperado. Por favor, intenta de nuevo."
        response_payload = format_chat_response(error_text)
    
    finally:
        end_time = time.time()
        print(json.dumps({
            "log_name": "HandleChatEvent_Salida",
            "duracion_ms": int((end_time - start_time) * 1000),
            "respuesta_enviada": response_payload
        }))

    return jsonify(response_payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)