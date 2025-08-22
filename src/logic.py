import os
import json
import traceback
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, Part

load_dotenv()

GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL")
from src.config import GCP_PROJECT_ID, LOCATION
from src.services import ticket_manager, ticket_querier, ticket_visualizer
from src.tools.tool_definitions import all_tools_config

model = None
initialized = False

system_prompt = """
Eres 'Bladi', un asistente de Helpdesk virtual experto en todo lo referente a IT manager. Tu motor es Gemini 2.5 flash. Tu misión es entender la solicitud del usuario, determinar su prioridad, y ayudarlo a gestionar tiquetes de soporte de manera eficiente y amigable para el equipo correcto con el sla que cumple con la solicitud.
**## Reglas Clave ##**
- **Personalización:** Siempre que sea natural, dirígete al usuario por su primer nombre. El nombre completo se te proporcionará; úsalo para extraer el primer nombre y saludarlo o mencionarlo en la conversación.
- **IMPORTANTE:** El email y nombre del solicitante ya te fueron proporcionados automáticamente. **NUNCA le preguntes al usuario por su correo o nombre.**
- **Validación de Dominio:** El sistema validará internamente que el dominio del correo sea autorizado.
**## Proceso de Creación de Tiquetes ##**
**1. Análisis de Prioridad y SLA:**
- **Prioridad Alta (8 horas):** Para solicitudes críticas como 'sistema caído' o 'ETL fallido'.
- **Prioridad Media (24 horas):** Para problemas estándar como un dashboard con datos incorrectos. Es la prioridad por defecto.
- **Prioridad Baja (72 horas):** Para solicitudes de nuevas funcionalidades.
**2. Enrutamiento por Equipo:**
- **"Data Engineering":** Para problemas de carga de datos, ETLs, pipelines.
- **"Data Analyst / BI":** Para problemas con dashboards o métricas.
**## Habilidades ##**
- **Análisis de Métricas:** Si preguntan por estadísticas, usa `consultar_metricas`.
- **Visualizar Flujo:** Si piden un 'historial' o 'diagrama', usa `visualizar_flujo_tiquete`.
- **Y el resto de tus habilidades...**
"""

available_tools = {
    "crear_tiquete_helpdesk": ticket_manager.crear_tiquete,
    "consultar_estado_tiquete": ticket_querier.consultar_estado_tiquete,
    "cerrar_tiquete": ticket_manager.cerrar_tiquete,
    "reasignar_tiquete": ticket_manager.reasignar_tiquete,
    "modificar_sla_manual": ticket_manager.modificar_sla_manual,
    "visualizar_flujo_tiquete": ticket_visualizer.visualizar_flujo_tiquete,
    "consultar_metricas": ticket_querier.consultar_metricas
}

def initialize_ai():
    """Inicializa el cliente de Vertex AI de forma segura."""
    global model, initialized
    if not initialized:
        print(json.dumps({"log_name": "InitializeAI", "mensaje": "Inicializando modelo de IA."}))
        vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)
        model = GenerativeModel(GEMINI_CHAT_MODEL, system_instruction=system_prompt, tools=[all_tools_config])
        initialized = True

def handle_dex_logic(user_message: str, user_email: str, user_display_name: str) -> str:
    """
    Maneja la lógica completa, procesa respuestas de múltiples partes y personaliza la conversación.
    """
    try:
        initialize_ai()
        
        primer_nombre = user_display_name.split(" ")[0]
        mensaje_personalizado = f"Hola {primer_nombre}, soy Dex. {user_message}"

        chat = model.start_chat()
        response = chat.send_message(mensaje_personalizado)
        
        function_call = None
        for part in response.candidates[0].content.parts:
            if part.function_call and part.function_call.name:
                function_call = part.function_call
                break
        
        if function_call:
            tool_name = function_call.name
            tool_to_call = available_tools.get(tool_name)
            
            if not tool_to_call: raise ValueError(f"Herramienta desconocida: {tool_name}")

            tool_args = {key: value for key, value in function_call.args.items()}
            
            if tool_name == "crear_tiquete_helpdesk":
                tool_args["solicitante"] = user_email
                tool_args["nombre_solicitante"] = user_display_name

            tool_response_text = tool_to_call(**tool_args)
            
            final_response = chat.send_message(
                Part.from_function_response(name=tool_name, response={"content": tool_response_text})
            )
            final_text = final_response.text
        else:
            final_text = response.text

        return final_text

    except Exception as e:
        print(json.dumps({"log_name": "HandleDexLogic_Error", "error": str(e), "traceback": traceback.format_exc()}))
        return "Lo siento, ocurrió un error interno al procesar tu solicitud."