# main.py (CORREGIDO)
import os
import json
import time
from flask import Flask, request, jsonify
from src.logic import handle_dex_logic

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    """
    Punto de entrada que recibe eventos de Google Chat, los valida y los
    pasa a la lógica principal para ser procesados.
    """
    start_time = time.time()
    event_data = request.get_json(silent=True)
    
    log_entry = {
        "mensaje": "Procesando evento de Google Chat",
        "tipo_evento": event_data.get("type", "DESCONOCIDO"),
        "respuesta_enviada": None,
        "error": None,
        "duracion_ms": None
    }

    response_payload = {} # Por defecto, una respuesta vacía válida

    try:
        # 1. VERIFICAR SI ES UN EVENTO DE MENSAJE
        # Solo reaccionamos a mensajes directos o menciones.
        if event_data and event_data.get('type') == 'MESSAGE':
            
            # 2. EXTRAER LA INFORMACIÓN DE FORMA SEGURA
            user_message_text = event_data.get("message", {}).get("text", "").strip()
            user_info = event_data.get("user", {})
            user_email = user_info.get("email")
            user_display_name = user_info.get("displayName", "Usuario")

            # Validar que tenemos la información mínima necesaria
            if user_message_text and user_email:
                # 3. LLAMAR A LA LÓGICA PRINCIPAL
                response_payload = handle_dex_logic(
                    user_message=user_message_text, 
                    user_email=user_email, 
                    user_display_name=user_display_name
                )
                log_entry["respuesta_enviada"] = response_payload
            else:
                log_entry["mensaje"] = "Evento de mensaje recibido pero sin texto o email de usuario."

        # Si es otro tipo de evento (ADDED_TO_SPACE, etc.), simplemente lo ignoramos
        # y devolvemos el 'response_payload' vacío, lo cual es una acción válida.
        else:
            log_entry["mensaje"] = f"Ignorando evento de tipo '{log_entry['tipo_evento']}'."

    except Exception as e:
        log_entry["error"] = str(e)
        # Devolver una tarjeta de error genérica al usuario
        response_payload = {
            "text": "Lo siento, ocurrió un error inesperado al procesar tu solicitud."
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