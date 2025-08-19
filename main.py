import os
import json
from flask import Flask, request
from src.logic import handle_dex_logic

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    event_data = request.get_json(silent=True)
    print(f"Evento recibido: {json.dumps(event_data, indent=2)}")

    response_payload = handle_dex_logic(event_data)
    
    return response_payload

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)