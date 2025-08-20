# En cloud_run_handler/main.py
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
    
    # ====== LÓGICA DE RESPUESTA MODIFICADA ======
    
    # Obtenemos el tipo de evento. Para un mensaje, será 'MESSAGE'.
    event_type = event_data.get("type", "")
    
    response_text = "He recibido tu mensaje. ¡La conexión funciona!"

    # Si el evento es un mensaje, construimos una respuesta de tarjeta simple.
    if event_type == "MESSAGE":
        return {
            "cardsV2": [
                {
                    "cardId": "welcome_card",
                    "card": {
                        "header": {
                            "title": "Dex Helpdesk",
                            "subtitle": "Conexión Exitosa"
                        },
                        "sections": [
                            {
                                "widgets": [
                                    {
                                        "textParagraph": {
                                            "text": response_text
                                        }
                                    }
                                ]
                            }
                        ]
                    }
                }
            ]
        }
    
    # Para otros tipos de eventos (como ser añadido a un espacio), no hacemos nada.
    return {}

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)