
import os
import json
import time
import traceback
from flask import Flask, request, jsonify

# No hay inicialización de clientes aquí, todo es diferido
print(json.dumps({"log_name": "ServerStartup", "mensaje": "main.py cargado."}))

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    event_data = request.get_json(silent=True) or {}
    
    try:
        chat_event = event_data.get("chat", {})
        if chat_event.get("messagePayload", {}).get("message"):
            
            # Importamos la lógica justo cuando la necesitamos
            from src.logic import handle_dex_logic
            
            user_message = chat_event.get("messagePayload", {}).get("message", {}).get("text", "").strip()
            user_info = chat_event.get("user", {})
            
            # Llamamos a la lógica y esperamos la respuesta (flujo síncrono)
            final_text_reply = handle_dex_logic(
                user_message=user_message,
                user_email=user_info.get("email"),
                user_display_name=user_info.get("displayName")
            )
            
            # --- LA RESPUESTA CORRECTA Y DEFINITIVA ---
            # Devolvemos un objeto CARD puro, como lo exige la API de Add-ons
            response_payload = {
                "sections": [{
                    "widgets": [{
                        "textParagraph": {
                            "text": final_text_reply
                        }
                    }]
                }]
            }
            return jsonify(response_payload)
        else:
            # Si no es un mensaje, no hacemos nada
            return jsonify({})

    except Exception as e:
        print(json.dumps({"log_name": "HandleChatEvent_Error", "error": str(e), "traceback": traceback.format_exc()}))
        # Devolvemos una tarjeta de error
        return jsonify({
            "sections": [{
                "widgets": [{
                    "textParagraph": {
                        "text": "Ocurrió un error inesperado al procesar tu solicitud."
                    }
                }]
            }]
        })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)