import os
import json
import time
from flask import Flask, request, jsonify

# LOG DE ARRANQUE 1: Para confirmar que el servidor Python se inició.
print(json.dumps({"log_name": "ServerStartup", "mensaje": "main.py cargado. Flask app inicializada."}))

app = Flask(__name__)

def format_chat_response(text_message: str) -> dict:
    """Toma un texto y lo envuelve en el formato de tarjeta de Google Chat."""
    return {
        "cardsV2": [{"cardId": "responseCard", "card": {"sections": [{"widgets": [{"textParagraph": {"text": text_message}}]}]}}]
    }

@app.route("/", methods=["POST"])
def handle_chat_event():
    start_time = time.time()
    event_data = request.get_json(silent=True) or {}
    print(json.dumps({"log_name": "HandleChatEvent_Entrada", "evento_recibido": event_data}))

    response_payload = {}

    try:
        # LOG DE ARRANQUE 2: Justo antes de importar la lógica pesada.
        print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": "Importando src.logic... Este es el punto crítico."}))
        
        # --- CAMBIO CLAVE: Importación local en lugar de global ---
        from src.logic import handle_dex_logic
        
        # LOG DE ARRANQUE 3: Si ves este log, la importación fue exitosa.
        print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": "src.logic importado exitosamente."}))

        event_type = event_data.get('type')

        if event_type == 'MESSAGE':
            user_message_text = event_data.get("message", {}).get("text", "").strip()
            user_info = event_data.get("user", {})
            user_email = user_info.get("email")
            user_display_name = user_info.get("displayName", "Usuario")

            if user_message_text and user_email:
                logic_response_text = handle_dex_logic(
                    user_message=user_message_text,
                    user_email=user_email,
                    user_display_name=user_display_name
                )
                response_payload = format_chat_response(logic_response_text)
            else:
                print(json.dumps({"log_name": "HandleChatEvent_Alerta", "mensaje": "Mensaje ignorado (sin texto o email)."}))
        else:
            print(json.dumps({"log_name": "HandleChatEvent_Info", "mensaje": f"Ignorando evento de tipo '{event_type}'."}))

    except Exception as e:
        print(json.dumps({"log_name": "HandleChatEvent_Error", "nivel": "CRITICO", "error": str(e)}))
        response_payload = format_chat_response("Ocurrió un error inesperado. Por favor, intenta de nuevo.")
    
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