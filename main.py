# /main.py (en la raíz)

import os
import json
from flask import Flask, request
# Importamos nuestra función "cerebro" desde src/logic.py
from src.logic import handle_dex_logic

# Inicializamos el servidor web
app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_chat_event():
    """
    Este es el único punto de entrada. Recibe el evento de Google Chat
    y se lo pasa a la lógica de Dex para que lo procese.
    """
    event_data = request.get_json(silent=True)
    
    # Imprimimos el evento para tener un registro (¡muy útil para depurar!)
    print(f"Evento recibido de Google Chat: {json.dumps(event_data, indent=2)}")

    # Le pasamos el trabajo completo a nuestra función lógica
    response_payload = handle_dex_logic(event_data)
    
    # Devolvemos la respuesta que el cerebro nos dio, sea texto o una tarjeta
    return response_payload

if __name__ == "__main__":
    # Esta parte es la que Gunicorn usará para iniciar el servidor en Cloud Run
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)