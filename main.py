import os
import json
import traceback
from flask import Flask, request, jsonify

print(json.dumps({"log_name": "ServerStartup", "mensaje": "main.py cargado."}))

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    event_data = request.get_json(silent=True) or {}
    
    try:
        # Para un bot estándar, el 'type' sí debería estar en el nivel superior
        if event_data.get('type') == 'MESSAGE':
            from src.logic import handle_dex_logic
            
            user_message = event_data.get('message', {}).get('text', '').strip()
            user_info = event_data.get('user', {})
            
            final_text_reply = handle_dex_logic(
                user_message=user_message,
                user_email=user_info.get("email"),
                user_display_name=user_info.get("displayName")
            )
            
            # --- LA RESPUESTA CORRECTA PARA UN BOT ESTÁNDAR ---
            # Un objeto 'Message' simple con solo texto.
            return jsonify({"text": final_text_reply})
        
        elif event_data.get('type') == 'ADDED_TO_SPACE':
            return jsonify({"text": "¡Gracias por añadirme! Soy Dex, tu asistente de Helpdesk."})

        # Ignoramos otros tipos de eventos
        return jsonify({})

    except Exception as e:
        print(json.dumps({"log_name": "HandleChatEvent_Error", "error": str(e), "traceback": traceback.format_exc()}))
        return jsonify({"text": "Ocurrió un error inesperado."})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)