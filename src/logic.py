import os
import json
import traceback
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, Part

load_dotenv()

# --- CONFIGURACIÓN Y CLIENTES ---
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL")
from src.config import GCP_PROJECT_ID, LOCATION
from src.services import ticket_manager, ticket_querier, ticket_visualizer
from src.tools.tool_definitions import all_tools_config

# --- INICIALIZACIÓN DIFERIDA (LAZY INITIALIZATION) ---
# Esto es crucial para un arranque rápido y estable en Cloud Run.
model = None
initialized = False

# --- PROMPT Y HERRAMIENTAS ---
# El prompt del sistema define la personalidad y reglas del bot.
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

# Mapea los nombres de las herramientas a las funciones reales.
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
    """
    Inicializa el cliente de Vertex AI y el modelo generativo.
    Usa variables globales para asegurar que esta operación pesada solo ocurra una vez.
    """
    global model, initialized
    if not initialized:
        print(json.dumps({"log_name": "InitializeAI", "mensaje": "Inicializando modelo de IA."}))
        vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)
        model = GenerativeModel(GEMINI_CHAT_MODEL, system_instruction=system_prompt, tools=[all_tools_config])
        initialized = True

def handle_dex_logic(user_message: str, user_email: str, user_display_name: str) -> str:
    """
    Maneja la lógica completa de forma síncrona y devuelve el texto de respuesta final.
    """
    try:
        # Se asegura de que el modelo esté listo para usarse.
        initialize_ai()
        
        chat = model.start_chat()
        response = chat.send_message(user_message)
        
        function_call = response.candidates[0].content.parts[0].function_call
        
        if function_call and function_call.name:
            tool_name = function_call.name
            tool_to_call = available_tools.get(tool_name)
            
            if not tool_to_call: 
                raise ValueError(f"Herramienta desconocida solicitada por el modelo: {tool_name}")

            tool_args = {key: value for key, value in function_call.args.items()}
            
            if tool_name == "crear_tiquete_helpdesk":
                tool_args["solicitante"] = user_email
                tool_args["nombre_solicitante"] = user_display_name

            # Ejecuta la herramienta (e.g., consulta a BigQuery) y espera el resultado.
            tool_response_text = tool_to_call(**tool_args)
            
            # Envía el resultado de la herramienta de vuelta a la IA para una respuesta final.
            final_response = chat.send_message(
                Part.from_function_response(name=tool_name, response={"content": tool_response_text})
            )
            final_text = final_response.text
        else:
            # Si no se necesita una herramienta, la respuesta es directa.
            final_text = response.text

        return final_text

    except Exception as e:
        print(json.dumps({"log_name": "HandleDexLogic_Error", "error": str(e), "traceback": traceback.format_exc()}))
        return "Lo siento, ocurrió un error interno al procesar tu solicitud."