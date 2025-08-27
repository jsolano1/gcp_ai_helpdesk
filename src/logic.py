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
from src.services.memory_service import get_chat_history, save_chat_history, get_or_create_active_session, set_session_state
from src.utils.bigquery_client import obtener_rol_usuario, actualizar_feedback_comentario
from src.services.knowledge_service import search_knowledge_base

model = None
initialized = False

system_prompt = """
Eres 'ConnectGPT', un asistente personal y multiagente virtual experto. Tu motor es Gemini 2.5 flash. Tu misión es entender la solicitud del usuario, y resolverle en base al KB o determinar si es un tiquete y su prioridad, para ayudarlo a gestionar tiquetes de soporte de manera eficiente y amigable con el equipo correcto y que el sla que cumple con la solicitud.

**## Reglas Clave ##**
- **Personalización:** Dirígete al usuario por su nombre completo. El nombre completo se te proporcionará en la conversación.
- **IMPORTANTE:** El email y nombre del solicitante ya te fueron proporcionados automáticamente. **NUNCA le preguntes al usuario por su correo o nombre.**
- **Validación de Dominio:** El sistema validará internamente que el dominio del correo sea autorizado. debe ser @connect.inc, @consoda.com o premier.pr

**## Manejo de Sentimientos ##**
- La conversación iniciará con el sentimiento del usuario (ej. 'negativo').
- **Si el sentimiento es 'negativo':** Adopta un tono especialmente empático y proactivo. Reconoce la frustración del usuario. Por ejemplo: "Entiendo completamente tu frustración con esto, haré todo lo posible para solucionarlo rápidamente."
- **Si el sentimiento es 'positivo' o 'neutro':** Mantén tu tono amigable y eficiente estándar.

**## Proceso de Creación de Tiquetes ##**
**1. Análisis de Prioridad:** Tu tarea es analizar la solicitud y asignar una de las tres prioridades. El SLA se calculará automáticamente basado en tu elección.
- **Prioridad 'alta':** Para solicitudes críticas como 'sistema caído', 'ETL fallido', 'no funciona nada', o 'pérdida de datos'.
- **Prioridad 'media':** Para problemas estándar como un dashboard con datos incorrectos o un reporte que no carga. Esta es la prioridad por defecto.
- **Prioridad 'baja':** Para solicitudes de nuevas funcionalidades o preguntas generales sin urgencia.
**2. Enrutamiento por Equipo:**
- **"Data Engineering":** Para problemas de carga de datos, ETLs, pipelines.
- **"Data Analyst / BI":** Para problemas con dashboards o métricas.

**## Habilidades ##**
- **Análisis de Métricas:** Si preguntan por estadísticas, usa `consultar_metricas`.
- **Visualizar Flujo:** Si piden un 'historial' o 'diagrama', usa `visualizar_flujo_tiquete`.
- **Convertir a Tarea:** Si una incidencia es una nueva funcionalidad, usa `convertir_incidencia_a_tarea` para crearla en Asana.
- **Agendar Reuniones:** Usa la herramienta `agendar_reunion_gcalendar` para proponer reuniones cuando sea relevante para resolver un problema o planificar una tarea.

**## Feedback del Usuario ##**
 **REGLA DE CIERRE DE CONVERSACIÓN:**
 Cuando hayas completado exitosamente la solicitud principal de un usuario (crear un tiquete, consultar un estado, etc.), DEBES seguir este formato de dos pasos en tu respuesta final:
- 1. **Confirmación de Cierre:** Primero, pregunta si hay algo más en lo que puedas ayudar.
- 2. **Solicitud de Feedback:** Inmediatamente después, en una nueva línea, añade la frase para solicitar la valoración.
"""

available_tools = {
    "crear_tiquete_helpdesk": ticket_manager.crear_tiquete,
    "consultar_estado_tiquete": ticket_querier.consultar_estado_tiquete,
    "cerrar_tiquete": ticket_manager.cerrar_tiquete,
    "reasignar_tiquete": ticket_manager.reasignar_tiquete,
    "modificar_sla_manual": ticket_manager.modificar_sla_manual,
    "visualizar_flujo_tiquete": ticket_visualizer.visualizar_flujo_tiquete,
    "consultar_metricas": ticket_querier.consultar_metricas,
    "convertir_incidencia_a_tarea": ticket_manager.convertir_incidencia_a_tarea,
    "agendar_reunion_gcalendar": ticket_manager.agendar_reunion_gcalendar
}

def initialize_ai():
    """Inicializa el modelo de IA de forma segura, solo una vez."""
    global model, initialized
    if not initialized:
        vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)
        model = GenerativeModel(GEMINI_CHAT_MODEL, system_instruction=system_prompt, tools=[all_tools_config])
        initialized = True

def analizar_sentimiento(user_message: str) -> str:
    """Clasifica el sentimiento de un mensaje usando el modelo de chat principal."""
    try:
        sentiment_model = GenerativeModel(GEMINI_CHAT_MODEL)
        prompt = f"""
        Analiza el sentimiento del siguiente texto y clasifícalo estrictamente como 'positivo', 'negativo' o 'neutro'.
        Responde únicamente con una de esas tres palabras.
        Texto: "{user_message}"
        """
        response = sentiment_model.generate_content(prompt)
        return response.text.strip().lower()
    except Exception as e:
        print(f"⚠️  Advertencia: No se pudo analizar el sentimiento. {e}")
        return "neutro"

def tiene_permiso(rol: str, herramienta: str) -> bool:
    """Verifica si un rol tiene permiso para usar una herramienta."""
    permisos = {
        "admin": list(available_tools.keys()),
        "lead": list(available_tools.keys()),
        "agent": ["crear_tiquete_helpdesk", "consultar_estado_tiquete", "cerrar_tiquete", "visualizar_flujo_tiquete", "consultar_metricas"],
        "user": ["crear_tiquete_helpdesk", "consultar_estado_tiquete", "visualizar_flujo_tiquete", "consultar_metricas"]
    }
    return herramienta in permisos.get(rol, [])

def handle_dex_logic(user_message: str, user_email: str, user_display_name: str, user_id: str):
    """
    Maneja la lógica de la conversación, con análisis de sentimiento y estado de feedback.
    """
    try:
        initialize_ai()
        
        session_id, session_state = get_or_create_active_session(user_id)
        if not session_id:
            return "Lo siento, no pude iniciar una sesión de chat para ti."

        if session_state == 'AWAITING_FEEDBACK_COMMENT':
            actualizar_feedback_comentario(session_id, user_message)
            set_session_state(user_id, None)
            return "Muchas gracias por tus comentarios, los tomaré en cuenta para mejorar."

        if len(user_message.split()) > 3 and "estado" not in user_message.lower():
            kb_result = search_knowledge_base(user_message)
            if kb_result:
                answer = kb_result['answer']
                response_text = (
                    f"{answer}\n\n---\n"
                    f"ℹ️ _Fuente: Knowledge Base Data Connect_\n\n"
                    "¿Resolvió esto tu duda? Si no, por favor describe tu problema con más detalle para crear un tiquete."
                )
                return response_text

        print("▶️ No se encontró respuesta en KB, procediendo con el análisis de IA...")
        user_role, user_department = obtener_rol_usuario(user_email)
        
        history = get_chat_history(session_id)
        num_initial_messages = len(history)
        
        chat = model.start_chat(history=history)
        
        sentimiento = analizar_sentimiento(user_message)
        mensaje_con_contexto = f"[Mi nombre es {user_display_name} y mi sentimiento actual es '{sentimiento}'] {user_message}"
        response = chat.send_message(mensaje_con_contexto)
        
        function_call = None
        for part in response.candidates[0].content.parts:
            if part.function_call and part.function_call.name:
                function_call = part.function_call
                break
        
        if function_call:
            tool_name = function_call.name
            
            if not tiene_permiso(user_role, tool_name):
                return f"Lo siento, {user_display_name.split(' ')[0]}, tu rol de '{user_role}' no te permite realizar esta acción."

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
            
            if tool_name == "visualizar_flujo_tiquete":
                try:
                    data = json.loads(tool_response_text)
                    if "error" in data: return data["error"]
                    
                    return {
                        "cardsV2": [{
                            "cardId": f"flow_card_{data['ticketId']}", "card": { "header": { "title": f"Línea de Tiempo del Tiquete {data['ticketId']}", "subtitle": "Aquí tienes el historial visual de tu solicitud.", "imageUrl": "https://i.ibb.co/L1J50f1/timeline-icon.png", "imageType": "CIRCLE" }, "sections": [{"widgets": [{"image": { "imageUrl": data['imageUrl'] }}]}] }
                        }]
                    }
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"🔴 Error al procesar la respuesta de la imagen: {e}")
                    return "Hubo un error inesperado al procesar la visualización del tiquete."

            if tool_name == "agendar_reunion_gcalendar":
                try:
                    data = json.loads(tool_response_text)
                    if "error" in data: return data["error"]

                    return {
                        "cardsV2": [{
                            "cardId": "calendar_card", "card": { "header": { "title": "Agendar Reunión de Seguimiento", "subtitle": f"Para: {', '.join(data['invitados'])}", "imageType": "CIRCLE", "imageUrl": "https://i.ibb.co/VvfTff5/calendar-icon.png" }, "sections": [{"widgets": [{"buttonList": {"buttons": [{"text": "Buscar Horario en G-Calendar", "onClick": {"openLink": { "url": data['url'] }}}]}}]}] }
                        }]
                    }
                except (json.JSONDecodeError, KeyError) as e:
                    print(f"🔴 Error al procesar el enlace de calendario: {e}")
                    return "Hubo un error inesperado al generar el enlace de la reunión."

            final_response = chat.send_message(
                Part.from_function_response(name=tool_name, response={"content": tool_response_text})
            )
            final_text = final_response.text
        else:
            final_text = response.text
        
        save_chat_history(session_id, user_id, chat.history, num_initial_messages)
        return final_text

    except Exception as e:
        print(json.dumps({"log_name": "HandleDexLogic_Error", "error": str(e), "traceback": traceback.format_exc()}))
        return "Lo siento, ocurrió un error interno al procesar tu solicitud."