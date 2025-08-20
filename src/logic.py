import os
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, Part

load_dotenv()
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL")

from src.config import GCP_PROJECT_ID, LOCATION
from src.services import ticket_manager, ticket_querier, ticket_visualizer
from src.tools.tool_definitions import all_tools_config

# --- INICIO: Esta parte se ejecuta solo una vez al arrancar ---
vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)

system_prompt = """
Eres 'Dex', un asistente de Helpdesk virtual de Nivel 1. Tu motor es Gemini. Tu misión es entender la solicitud del usuario, determinar su prioridad, y ayudarlo a gestionar tiquetes de soporte de manera eficiente y amigable. Puedes crear, consultar el estado, reasignar, cerrar tiquetes, modificar el SLA, generar flujos visuales y consultar métricas.

**## Reglas de Seguridad ##**
- **IMPORTANTE:** Antes de crear cualquier tiquete, DEBES verificar que el email del solicitante termine en un dominio autorizado: '@connect.inc', '@consoda.com', o '@premier.io'. Si no es válido, responde amablemente que no puedes procesar la solicitud.

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
- **Visualizar Flujo:** Si piden 'historial', 'flujo' o 'diagrama', usa `visualizar_flujo_tiquete`. **IMPORTANTE:** Muestra la salida de esta herramienta EXACTAMENTE como la recibes.
- **Consultar Estado:** Para preguntas rápidas de estado, usa `consultar_estado_tiquete`.
- **Reasignar:** Para cambiar el responsable, usa `reasignar_tiquete`.
- **Modificar SLA:** Para cambiar el SLA, usa `modificar_sla_manual`.
- **Cerrar:** Para cerrar un tiquete, pide una nota de resolución y usa `cerrar_tiquete`.
"""

# Se define el modelo una vez
model = GenerativeModel(GEMINI_CHAT_MODEL, system_instruction=system_prompt, tools=[all_tools_config])

available_tools = {
    "crear_tiquete_helpdesk": ticket_manager.crear_tiquete,
    "consultar_estado_tiquete": ticket_querier.consultar_estado_tiquete,
    "cerrar_tiquete": ticket_manager.cerrar_tiquete,
    "reasignar_tiquete": ticket_manager.reasignar_tiquete,
    "modificar_sla_manual": ticket_manager.modificar_sla_manual,
    "visualizar_flujo_tiquete": ticket_visualizer.visualizar_flujo_tiquete,
    "consultar_metricas": ticket_querier.consultar_metricas
}
# --- FIN: Código de inicialización ---


def handle_dex_logic(event_data: dict) -> dict:
    """Toma un payload de mensaje de Chat, lo procesa con la lógica de Dex y devuelve una respuesta."""
    try:
        # Extraemos el texto del mensaje desde la ruta correcta
        user_message = event_data.get('message', {}).get('text', '').strip()
        
        if not user_message:
            print("Payload de mensaje recibido pero sin texto. Ignorando.")
            # --- ✅ ESTE ES EL CAMBIO CLAVE ---
            # Devolvemos un diccionario vacío para no enviar ninguna respuesta al chat.
            return {}

        # Inicia una sesión de chat nueva con cada mensaje.
        chat = model.start_chat()
        
        # Envía el mensaje del usuario a la sesión de chat
        response = chat.send_message(user_message)
        
        function_call = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                function_call = part.function_call
                break
        
        if function_call:
            tool_name = function_call.name
            tool_to_call = available_tools[tool_name]
            tool_args = {key: value for key, value in function_call.args.items()}
            
            print(f"▶️  IA solicita llamar a la función: {tool_name} con argumentos: {tool_args}")
            tool_response_text = tool_to_call(**tool_args)
            print(f"◀️  Respuesta de la función: {tool_response_text}")

            final_response = chat.send_message(
                Part.from_function_response(name=tool_name, response={"content": tool_response_text})
            )
            return {"text": final_response.text}
        else:
            return {"text": response.text}

    except Exception as e:
        print(f"🔴 Error CRÍTICO en la lógica de Dex: {e}")
        # Devolvemos una respuesta de texto simple en caso de error para asegurar
        # que Google Chat siempre reciba un formato válido.
        return {"text": f"Lo siento, ocurrió un error interno al procesar tu solicitud."}