import os
import json
import traceback
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Carga de variables de entorno y configuración inicial
load_dotenv()
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL")

from src.config import GCP_PROJECT_ID, LOCATION
from src.services import ticket_manager, ticket_querier, ticket_visualizer
from src.tools.tool_definitions import all_tools_config

# Inicialización de Vertex AI
vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)

# Prompt del sistema para guiar el comportamiento de Gemini
system_prompt = """
Eres 'Dex', un asistente de Helpdesk virtual de Nivel 1. Tu motor es Gemini. Tu misión es entender la solicitud del usuario, determinar su prioridad, y ayudarlo a gestionar tiquetes de soporte de manera eficiente y amigable.

**## Reglas Clave ##**
- **IMPORTANTE:** El email y nombre del solicitante ya te fueron proporcionados automáticamente. **NUNCA le preguntes al usuario por su correo o nombre.** Simplemente usa los que se te dan.
- **Validación de Dominio:** Antes de crear un tiquete, el sistema validará internamente que el dominio del correo sea autorizado ('@connect.inc', '@consoda.com', '@premier.io').

**## Proceso de Creación de Tiquetes ##**
**1. Análisis de Prioridad y SLA:**
- **Prioridad Alta (8 horas):** Si mencionan 'crítico', 'urgente', 'sistema caído', 'no funciona nada', o si un ETL ha fallado.
- **Prioridad Media (24 horas):** Para problemas estándar como un dashboard con datos incorrectos. Es la prioridad por defecto.
- **Prioridad Baja (72 horas):** Para solicitudes de nuevas funcionalidades sin urgencia.

**2. Enrutamiento por Equipo:**
- **"Data Engineering":** Para problemas de carga de datos, ETLs, pipelines, o permisos.
- **"Data Analyst / BI":** Para problemas con dashboards, reportes, o métricas.
    
**## Habilidades ##**
- **Análisis de Métricas:** Si preguntan por estadísticas ('cuántos tiquetes', 'promedio'), usa `consultar_metricas`.
- **Visualizar Flujo:** Si piden 'historial', 'flujo' o 'diagrama', usa `visualizar_flujo_tiquete`.
- **Y el resto de tus habilidades...**
"""

# Inicialización del modelo generativo con el prompt y las herramientas
model = GenerativeModel(GEMINI_CHAT_MODEL, system_instruction=system_prompt, tools=[all_tools_config])

# Mapeo de nombres de herramientas a funciones reales
available_tools = {
    "crear_tiquete_helpdesk": ticket_manager.crear_tiquete,
    "consultar_estado_tiquete": ticket_querier.consultar_estado_tiquete,
    "cerrar_tiquete": ticket_manager.cerrar_tiquete,
    "reasignar_tiquete": ticket_manager.reasignar_tiquete,
    "modificar_sla_manual": ticket_manager.modificar_sla_manual,
    "visualizar_flujo_tiquete": ticket_visualizer.visualizar_flujo_tiquete,
    "consultar_metricas": ticket_querier.consultar_metricas
}

def format_chat_response(text_message: str) -> dict:
    """
    Envuelve un mensaje de texto simple en la estructura de Tarjeta v2
    que Google Chat espera para evitar errores de formato.
    """
    return {
        "cardsV2": [
            {
                "cardId": "responseCard",
                "card": {
                    "sections": [
                        {
                            "widgets": [
                                {
                                    "textParagraph": {
                                        "text": text_message
                                    }
                                }
                            ]
                        }
                    ]
                }
            }
        ]
    }

def handle_dex_logic(user_message: str, user_email: str, user_display_name: str) -> dict:
    """
    Toma un mensaje, correo y nombre del usuario, lo procesa y devuelve una respuesta
    en el formato de Tarjeta de Google Chat.
    """
    print(json.dumps({
        "mensaje": "Iniciando handle_dex_logic",
        "mensaje_usuario": user_message,
        "email_usuario": user_email,
        "nombre_usuario": user_display_name
    }))

    # Validación de dominio del correo del solicitante
    authorized_domains = ["@connect.inc", "@consoda.com", "@premier.io"]
    if not any(user_email.endswith(domain) for domain in authorized_domains):
        mensaje_error = "Lo siento, solo puedo procesar solicitudes de dominios autorizados."
        print(json.dumps({"alerta": "Correo no autorizado", "email": user_email}))
        return format_chat_response(mensaje_error)

    try:
        chat = model.start_chat()
        response = chat.send_message(user_message)

        function_call = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                function_call = part.function_call
                break

        if function_call:
            tool_name = function_call.name
            tool_to_call = available_tools.get(tool_name)
            
            if not tool_to_call:
                raise ValueError(f"Herramienta desconocida: {tool_name}")

            tool_args = {key: value for key, value in function_call.args.items()}

            if tool_name == "crear_tiquete_helpdesk":
                tool_args["solicitante"] = user_email
                tool_args["nombre_solicitante"] = user_display_name
                print(json.dumps({
                    "info": "Inyectando datos del solicitante automáticamente",
                    "email": user_email,
                    "nombre": user_display_name
                }))

            print(json.dumps({"mensaje": "IA solicita llamar a función", "funcion": tool_name, "argumentos": tool_args}))
            tool_response_text = tool_to_call(**tool_args)
            print(json.dumps({"mensaje": "Respuesta de la función ejecutada", "resultado": tool_response_text}))

            final_response = chat.send_message(
                Part.from_function_response(name=tool_name, response={"content": tool_response_text})
            )
            return format_chat_response(final_response.text)
        else:
            return format_chat_response(response.text)

    except Exception as e:
        error_details = {
            "mensaje": "Error CRÍTICO en la lógica de Dex",
            "tipo_error": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_details))
        
        return format_chat_response("Lo siento, ocurrió un error interno al procesar tu solicitud.")