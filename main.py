import os
import json
import traceback
from flask import Flask, request, jsonify

from src.logic import handle_dex_logic
from src.tasks.summary_task import send_daily_summaries

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    event_data = request.get_json(silent=True) or {}
    
    print(f"DEBUGGING EVENT RECEIVED: {json.dumps(event_data)}")
    
    try:
        if event_data.get('type') == 'MESSAGE':
            user_message = event_data.get('message', {}).get('text', '').strip()
            user_info = event_data.get('user', {})
            
            response_data = handle_dex_logic(
                user_message=user_message,
                user_email=user_info.get("email"),
                user_display_name=user_info.get("displayName"),
                user_id=user_info.get("name") 
            )
            
            if isinstance(response_data, str):
                return jsonify({"text": response_data})
            elif isinstance(response_data, dict):
                return jsonify(response_data)
            else:
                return jsonify({"text": "No se pudo procesar la respuesta."})

        elif event_data.get('type') == 'ADDED_TO_SPACE':
            return jsonify({"text": "¡Gracias por añadirme! Soy ConnectAI, tu asistente de Helpdesk."})

        return jsonify({})

    except Exception as e:
        print(json.dumps({"log_name": "HandleChatEvent_Error", "error": str(e), "traceback": traceback.format_exc()}))
        return jsonify({"text": "Ocurrió un error inesperado."})

@app.route("/run-summary", methods=["POST"])
def handle_summary_trigger():
    print("🚀 Tarea de resumen diario iniciada por Cloud Scheduler.")
    try:
        send_daily_summaries()
        return "Tarea de resumen completada.", 200
    except Exception as e:
        print(f"🔴 Error ejecutando la tarea de resumen: {e}")
        return "Error interno ejecutando la tarea.", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)