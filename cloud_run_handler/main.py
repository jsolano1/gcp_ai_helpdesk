import os
import json
from flask import Flask, request

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    """
    Función que se activa cuando Google Chat envía un evento.
    """
    event_data = request.get_json(silent=True)
    
    print("Evento recibido de Google Chat:")
    print(json.dumps(event_data, indent=4))
    
    response_text = "He recibido tu mensaje."
    return {"text": response_text}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)