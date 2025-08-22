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
from src.services.memory_service import get_chat_history, save_chat_history
from src.utils.bigquery_client import obtener_rol_usuario

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
    """Inicializa el modelo de IA de forma segura, solo una vez."""
    global model, initialized
    if not initialized:
        vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)
        model = GenerativeModel(GEMINI_CHAT_MODEL, system_instruction=system_prompt, tools=[all_tools_config])
        initialized = True

def tiene_permiso(rol: str, herramienta: str) -> bool:
    """Verifica si un rol tiene permiso para usar una herramienta."""
    permisos = {
        "admin": ["crear_tiquete_helpdesk", "consultar_estado_tiquete", "cerrar_tiquete", "reasignar_tiquete", "modificar_sla_manual", "visualizar_flujo_tiquete", "consultar_metricas"],
        "lead": ["crear_tiquete_helpdesk", "consultar_estado_tiquete", "cerrar_tiquete", "reasignar_tiquete", "modificar_sla_manual", "visualizar_flujo_tiquete", "consultar_metricas"],
        "agent": ["crear_tiquete_helpdesk", "consultar_estado_tiquete", "cerrar_tiquete", "visualizar_flujo_tiquete", "consultar_metricas"],
        "user": ["crear_tiquete_helpdesk", "consultar_estado_tiquete", "visualizar_flujo_tiquete", "consultar_metricas"]
    }
    if rol == "admin":
        return True
    return herramienta in permisos.get(rol, [])

ddef handle_dex_logic(user_message: str, user_email: str, user_display_name: str, user_id: str) -> str:
    """
    Maneja la lógica de la conversación con el nuevo sistema RBAC.
    """
    try:
        initialize_ai()
        
        user_role, user_department = obtener_rol_usuario(user_email)
        
        history = get_chat_history(user_id)
        num_initial_messages = len(history)
        
        chat = model.start_chat(history=history)
        
        mensaje_con_contexto = f"[Mi nombre es {user_display_name.split(' ')[0]}] {user_message}"
        response = chat.send_message(mensaje_con_contexto)
        
        function_call = None
        for part in response.candidates[0].content.parts:
            if part.function_call and part.function_call.name:
                function_call = part.function_call
                break
        
        if function_call:
            tool_name = function_call.name
            
            print(f"▶️  Verificando permiso para rol '{user_role}' en herramienta '{tool_name}'...")
            if not tiene_permiso(user_role, tool_name):
                print(f"🚫 Acceso denegado para {user_email} (rol: {user_role}) a la herramienta {tool_name}.")
                return f"Lo siento, {user_display_name.split(' ')[0]}, tu rol de '{user_role}' no te permite realizar esta acción."

            print("✅ Permiso concedido.")
            tool_to_call = available_tools.get(tool_name)
            if not tool_to_call: raise ValueError(f"Herramienta desconocida: {tool_name}")

            tool_args = {key: value for key, value in function_call.args.items()}
            
            tool_args["solicitante_email"] = user_email
            tool_args["solicitante_nombre"] = user_display_name
            tool_args["solicitante_rol"] = user_role
            tool_args["solicitante_departamento"] = user_department
            
            if tool_name == "crear_tiquete_helpdesk":
                 tool_args.pop("solicitante", None)
                 tool_args.pop("nombre_solicitante", None)
                 tool_args["solicitante"] = user_email
                 tool_args["nombre_solicitante"] = user_display_name

            tool_response_text = tool_to_call(**tool_args)
            
            final_response = chat.send_message(
                Part.from_function_response(name=tool_name, response={"content": tool_response_text})
            )
            final_text = final_response.text
        else:
            final_text = response.text
        
        save_chat_history(user_id, chat.history)
        return final_text

    except Exception as e:
        print(json.dumps({"log_name": "HandleDexLogic_Error", "error": str(e), "traceback": traceback.format_exc()}))
        return "Lo siento, ocurrió un error interno al procesar tu solicitud."
