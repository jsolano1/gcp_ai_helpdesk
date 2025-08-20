# /main.py

import os
import json
import time
from flask import Flask, request, jsonify
from src.logic import handle_dex_logic

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    """
    Punto de entrada que recibe eventos de Google Chat, los registra de forma estructurada
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
        if 'chat' in event_data and 'messagePayload' in event_data['chat']:
            response_payload = handle_dex_logic(event_data['chat']['messagePayload'])
            log_entry["respuesta_enviada"] = response_payload
        else:
            log_entry["mensaje"] = "Ignorando evento que no es un mensaje de usuario."
            response_payload = {}

    except Exception as e:
        log_entry["error"] = str(e)
        response_payload = {"text": "Ocurrió un error inesperado en el servidor."}
        log_entry["respuesta_enviada"] = response_payload
    
    finally:
        end_time = time.time()
        log_entry["duracion_ms"] = int((end_time - start_time) * 1000)
        
        print(json.dumps(log_entry))

    return jsonify(response_payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)