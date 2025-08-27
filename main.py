import os
import json
import traceback
from flask import Flask, request, jsonify
from src.logic import handle_dex_logic
from src.tasks.summary_task import send_daily_summaries
from src.utils.bigquery_client import registrar_feedback
from src.services.memory_service import get_or_create_active_session, set_session_state

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    event_data = request.get_json(silent=True) or {}
    
    try:
        event_type = event_data.get('type')

        if event_type == 'MESSAGE':
            user_message = event_data.get('message', {}).get('text', '').strip()
            user_info = event_data.get('user', {})
            
            response_data = handle_dex_logic(
                user_message=user_message,
                user_email=user_info.get("email"),
                user_display_name=user_info.get("displayName"),
                user_id=user_info.get("name") 
            )
            
            if isinstance(response_data, str) and response_data.endswith("Si mi asistencia te fue de ayuda, por favor valórala:"):
                return jsonify({
                    "text": response_data,
                    "cardsV2": [{
                        "cardId": "feedback_card",
                        "card": {
                            "sections": [{
                                "widgets": [{
                                    "buttonList": {
                                        "buttons": [
                                            {
                                                "text": "👍",
                                                "onClick": { "action": { "function": "register_feedback_positive" } }
                                            },
                                            {
                                                "text": "👎",
                                                "onClick": { "action": { "function": "register_feedback_negative" } }
                                            }
                                        ]
                                    }
                                }]
                            }]
                        }
                    }]
                })
            elif isinstance(response_data, str):
                return jsonify({"text": response_data})
            elif isinstance(response_data, dict):
                return jsonify(response_data)
            else:
                return jsonify({"text": "No se pudo procesar la respuesta."})

        elif event_type == 'CARD_CLICKED':
            action = event_data.get('common', {}).get('invokedFunction')
            user_info = event_data.get('user', {})
            user_email = user_info.get("email")
            user_id = user_info.get("name")
            session_id, _ = get_or_create_active_session(user_id)

            response_card = { "actionResponse": { "type": "UPDATE_MESSAGE" } }

            if action == 'register_feedback_positive':
                registrar_feedback(session_id, user_email, 1)
                response_card["text"] = "¡Gracias por tu feedback!"
                return jsonify(response_card)

            elif action == 'register_feedback_negative':
                registrar_feedback(session_id, user_email, 0)
                set_session_state(user_id, 'AWAITING_FEEDBACK_COMMENT')
                response_card["text"] = "Lamento que tu experiencia no haya sido la mejor. ¿Podrías darme más detalles para poder mejorar?"
                return jsonify(response_card)

            return jsonify({})

        elif event_type == 'ADDED_TO_SPACE':
            return jsonify({"text": "¡Gracias por añadirme! Soy ConnectAI, tu asistente personal."})

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