@app.route("/", methods=["POST"])
def handle_chat_event():
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
        if "message" in event_data:
            user_message = event_data["message"].get("text", "")
            user_email = event_data["message"]["sender"].get("email", "")
            user_display_name = event_data["message"]["sender"].get("displayName", "")

            response_payload = handle_dex_logic(user_message, user_email, user_display_name)

            # Agregar fallback "text" obligatorio para Google Chat
            if "text" not in response_payload:
                response_payload["text"] = response_payload.get("cardsV2", [{}])[0] \
                    .get("card", {}).get("sections", [{}])[0] \
                    .get("widgets", [{}])[0] \
                    .get("textParagraph", {}).get("text", " ")
            
            log_entry["respuesta_enviada"] = response_payload
        else:
            log_entry["mensaje"] = "Evento no es un mensaje válido de usuario."
            response_payload = {"text": "Evento ignorado."}

    except Exception as e:
        log_entry["error"] = str(e)
        response_payload = {"text": "Ocurrió un error inesperado en el servidor."}
        log_entry["respuesta_enviada"] = response_payload
    
    finally:
        log_entry["duracion_ms"] = int((time.time() - start_time) * 1000)
        print(json.dumps(log_entry))

    return jsonify(response_payload), 200, {"Content-Type": "application/json; charset=UTF-8"}
