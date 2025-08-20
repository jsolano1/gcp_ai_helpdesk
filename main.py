# /main.py (en la raíz)

import os
import json
from flask import Flask, request, jsonify
from src.logic import handle_dex_logic

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    """
    Punto de entrada que recibe eventos de Google Chat, los registra
    y los pasa a la lógica principal para ser procesados.
    """
    event_data = request.get_json(silent=True)
    
    # Log para depuración
    print("================ RECIBIENDO EVENTO DE GOOGLE CHAT ================")
    print(json.dumps(event_data, indent=2))
    print("==================================================================")

    response_payload = None

    # --- CAMBIO CLAVE ---
    # Buscamos directamente si el evento contiene un mensaje de usuario.
    # Esta es la forma más robusta de identificar un mensaje para responder.
    if 'chat' in event_data and 'messagePayload' in event_data['chat']:
        # Pasamos el contenido de 'messagePayload' a la lógica,
        # que es lo que realmente contiene la información del mensaje.
        response_payload = handle_dex_logic(event_data['chat']['messagePayload'])
    else:
        # Si no es un mensaje (puede ser un evento de autorización, etc.), lo ignoramos.
        print("Ignorando evento que no es un mensaje de usuario.")
        return jsonify({})

    # Log para depuración
    print("================ ENVIANDO RESPUESTA A GOOGLE CHAT ================")
    print(json.dumps(response_payload, indent=2))
    print("==================================================================")
    
    return jsonify(response_payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)