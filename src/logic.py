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


def handle_dex_logic(event_data: dict) -> dict:
    """Toma un payload de mensaje, lo procesa y devuelve una respuesta, con logging detallado."""
    print(json.dumps({"mensaje": "Iniciando handle_dex_logic", "payload_recibido": event_data}))

    try:
        user_message = event_data.get('message', {}).get('text', '').strip()
        
        if not user_message:
            print(json.dumps({"mensaje": "Payload sin texto, ignorando."}))
            return {}

        chat = model.start_chat()
        
        print(json.dumps({"mensaje": "Enviando mensaje a Gemini", "contenido": user_message}))
        response = chat.send_message(user_message)
        
        print(json.dumps({"mensaje": "Respuesta recibida de Gemini", "respuesta_api": str(response)}))
        
        function_call = None
        for part in response.candidates[0].content.parts:
            if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                function_call = part.function_call
                break
        
        if function_call:
            tool_name = function_call.name
            tool_to_call = available_tools[tool_name]
            tool_args = {key: value for key, value in function_call.args.items()}
            
            print(json.dumps({"mensaje": "IA solicita llamar a función", "funcion": tool_name, "argumentos": tool_args}))
            tool_response_text = tool_to_call(**tool_args)
            print(json.dumps({"mensaje": "Respuesta de la función ejecutada", "resultado": tool_response_text}))

            final_response = chat.send_message(
                Part.from_function_response(name=tool_name, response={"content": tool_response_text})
            )
            return {"text": final_response.text}
        else:
            return {"text": response.text}

    except Exception as e:
        error_details = {
            "mensaje": "Error CRÍTICO en la lógica de Dex",
            "tipo_error": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_details))
        
        return {"text": f"Lo siento, ocurrió un error interno al procesar tu solicitud."}