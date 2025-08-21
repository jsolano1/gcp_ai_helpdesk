import os
import json
import traceback
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Carga las variables de entorno
load_dotenv()
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL")

# Importaciones de módulos locales
from src.config import GCP_PROJECT_ID, LOCATION
from src.services import ticket_manager, ticket_querier, ticket_visualizer
from src.tools.tool_definitions import all_tools_config

# --- Variables Globales para Inicialización Diferida ---
# Esto asegura que el modelo pesado solo se cargue una vez por instancia.
model = None
initialized = False

# El prompt y las herramientas se pueden definir globalmente
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
    Inicializa Vertex AI y el modelo de forma diferida, asegurando que solo se ejecute una vez.
    """
    global model, initialized
    if not initialized:
        print(json.dumps({"log_name": "InitializeAI", "mensaje": "Iniciando la carga del modelo de IA por primera vez."}))
        vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)
        model = GenerativeModel(GEMINI_CHAT_MODEL, system_instruction=system_prompt, tools=[all_tools_config])
        initialized = True
        print(json.dumps({"log_name": "InitializeAI", "mensaje": "✅ Inicialización de IA completada."}))

def execute_task_and_get_reply(user_message: str, user_email: str, user_display_name: str) -> str:
    """
    Esta función contiene la lógica pesada. Es llamada por el trabajador de Cloud Tasks.
    Realiza la llamada a Gemini, ejecuta herramientas y devuelve la respuesta final en texto.
    """
    try:
        # Paso 1: Asegurarse de que el modelo de IA esté listo.
        initialize_ai()
        print(json.dumps({"log_name": "ExecuteTask", "mensaje": "Iniciando ejecución de tarea pesada."}))

        # Paso 2: Interactuar con el modelo de Gemini.
        chat = model.start_chat()
        response = chat.send_message(user_message)
        
        function_call = response.candidates[0].content.parts[0].function_call
        
        # Paso 3: Manejar la lógica de llamada a herramientas si es necesario.
        if function_call and function_call.name:
            tool_name = function_call.name
            tool_to_call = available_tools.get(tool_name)
            
            if not tool_to_call:
                raise ValueError(f"Herramienta desconocida solicitada por el modelo: {tool_name}")

            tool_args = {key: value for key, value in function_call.args.items()}
            
            if tool_name == "crear_tiquete_helpdesk":
                tool_args["solicitante"] = user_email
                tool_args["nombre_solicitante"] = user_display_name

            # Ejecutar la herramienta (ej. consulta a BigQuery)
            tool_response_text = tool_to_call(**tool_args)
            
            # Devolver el resultado de la herramienta al modelo para una respuesta final.
            final_response = chat.send_message(
                Part.from_function_response(name=tool_name, response={"content": tool_response_text})
            )
            final_text = final_response.text
        else:
            # Si no hay herramientas, la respuesta es el texto directo del modelo.
            final_text = response.text

        print(json.dumps({"log_name": "ExecuteTask_Exito", "respuesta_final": final_text}))
        return final_text

    except Exception as e:
        error_details = {
            "log_name": "ExecuteTask_Error", "nivel": "CRITICO",
            "mensaje": "Error CRÍTICO durante la ejecución de la tarea en segundo plano.",
            "tipo_error": type(e).__name__,
            "error": str(e), "traceback": traceback.format_exc()
        }
        print(json.dumps(error_details))
        return "Lo siento, ocurrió un error interno al procesar tu solicitud. El equipo técnico ha sido notificado."