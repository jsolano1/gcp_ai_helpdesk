import os
import json
from flask import Flask, request, jsonify  # <-- Importa jsonify
from src.logic import handle_dex_logic

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    """
    Punto de entrada que recibe eventos de Google Chat, los registra
    y los pasa a la lógica principal para ser procesados.
    """
    event_data = request.get_json(silent=True)
    
    # --- LOGGING PARA DEPURACIÓN ---
    # Imprimimos el evento COMPLETO que nos llega de Google Chat. ¡Esto es clave!
    print("================ RECIBIENDO EVENTO DE GOOGLE CHAT ================")
    print(json.dumps(event_data, indent=2))
    print("==================================================================")

    # Verificamos si el evento es de un tipo que podemos manejar (un mensaje de un humano)
    event_type = event_data.get('type')
    
    if event_type == 'MESSAGE':
        # Si es un mensaje, se lo pasamos a nuestra lógica de IA
        response_payload = handle_dex_logic(event_data)
    elif event_type == 'ADDED_TO_SPACE':
        # Si el bot es añadido a un espacio, enviamos un saludo
        response_payload = {"text": "¡Gracias por añadirme! Soy Dex, tu asistente de Helpdesk. ¿En qué puedo ayudarte?"}
    else:
        # Para cualquier otro tipo de evento que no manejamos, no hacemos nada.
        # Devolver un cuerpo vacío con 200 OK es la forma correcta de ignorar eventos.
        print(f"Ignorando evento de tipo no manejado: {event_type}")
        return jsonify({})

    # --- LOGGING PARA DEPURACIÓN ---
    # Imprimimos la respuesta EXACTA que le vamos a enviar a Google Chat.
    print("================ ENVIANDO RESPUESTA A GOOGLE CHAT ================")
    print(json.dumps(response_payload, indent=2))
    print("==================================================================")
    
    # Usamos jsonify para asegurarnos que la respuesta sea un JSON válido
    return jsonify(response_payload)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)