import os
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, Part

load_dotenv()
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL")

from src.config import GCP_PROJECT_ID, LOCATION
from src.services import ticket_manager, ticket_querier, ticket_visualizer
from src.tools.tool_definitions import all_tools_config

def main():
    """Función principal para ejecutar el agente Dex como orquestador."""
    vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)

    system_prompt = """
    Eres 'Dex', un asistente de Helpdesk virtual de Nivel 1. Tu motor es el poderoso Gemini 2.5 Flash. Tu misión es entender la solicitud del usuario, determinar su prioridad, y ayudarlo a gestionar tiquetes de soporte de manera eficiente y amigable. Puedes crear, consultar el estado, reasignar, cerrar tiquetes, generar flujos y modificar el SLA.
    
    **## Reglas de Seguridad ##**
    - **IMPORTANTE:** Antes de crear cualquier tiquete, DEBES verificar que el email del solicitante termine en uno de estos dominios: '@connect.inc', '@consoda.com', o '@premier.io'. 
    - Si el email no pertenece a uno de estos dominios, responde amablemente que solo puedes aceptar solicitudes de correos autorizados y no crees el tiquete.
    - A partir de este momento que se entrego correo, llama al usuario por su nombre. Ejemplo: jose.solano@connect.inc, nombre: Jose Solano.

    **## Proceso de Creación de Tiquetes ##**
    **1. Análisis de Prioridad y Asignación de SLA:**
    - **Prioridad Alta (SLA de 8 horas):** Si el usuario menciona 'crítico', 'urgente', 'sistema caído', 'no funciona nada', 'pérdida de datos' o si un proceso ETL ha fallado.
    - **Prioridad Media (SLA de 24 horas):** Para problemas estándar como un dashboard con datos incorrectos o un reporte que no carga. Es la prioridad por defecto.
    - **Prioridad Baja (SLA de 72 horas):** Para solicitudes de nuevas funcionalidades sin urgencia.
    
    **2. Enrutamiento por Equipo:**
    - **"Data Engineering":** Para problemas de carga de datos, ETLs, pipelines, calidad de la fuente, o permisos.
    - **"Data Analyst / BI":** Para problemas con dashboards, reportes, métricas o visualizaciones.
        
    **## Otras Habilidades ##**
    - **Análisis de Métricas:** Si el usuario hace una pregunta sobre estadísticas o métricas (ej. 'cuántos tiquetes...', 'promedio de...', 'total de...'), usa la herramienta `consultar_metricas`.
    - **Visualizar Flujo:** Si un usuario pide ver el 'historial', 'flujo' o 'diagrama' de un tiquete, usa `visualizar_flujo_tiquete`. **IMPORTANTE:** Muestra la salida de esta herramienta EXACTAMENTE como la recibes, sin resumirla.
    - **Consultar:** Para preguntas rápidas de estado, usa `consultar_estado_tiquete`.
    - **Reasignar:** Para cambiar el responsable de un tiquete, usa `reasignar_tiquete`.
    - **Modificar SLA:** Para cambiar el SLA, usa `modificar_sla_manual`.
    - **Cerrar:** Para cerrar un tiquete, pide una nota de resolución y usa `cerrar_tiquete`.
    """
    
    model = GenerativeModel(GEMINI_CHAT_MODEL, system_instruction=system_prompt, tools=[all_tools_config])
    chat = model.start_chat()

    available_tools = {
        "crear_tiquete_helpdesk": ticket_manager.crear_tiquete,
        "consultar_estado_tiquete": ticket_querier.consultar_estado_tiquete,
        "cerrar_tiquete": ticket_manager.cerrar_tiquete,
        "reasignar_tiquete": ticket_manager.reasignar_tiquete,
        "modificar_sla_manual": ticket_manager.modificar_sla_manual,
        "visualizar_flujo_tiquete": ticket_visualizer.visualizar_flujo_tiquete,
        "consultar_metricas": ticket_querier.consultar_metricas
    }

    print("🤖 Dex está en línea. Describe tu problema o pide el estado de un tiquete (escribe 'salir' para terminar).")
    
    while True:
        user_input = input("Tu Mensaje > ")
        if user_input.lower() == 'salir':
            print("🤖 Dex desconectándose. ¡Que tengas un buen día!")
            break
        
        try:
            response = chat.send_message(user_input)
            
            function_call = None
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'function_call') and part.function_call and part.function_call.name:
                    function_call = part.function_call
                    break
            
            if function_call:
                print(f"🛠️  Dex quiere usar la herramienta: {function_call.name}")
                tool_name = function_call.name
                tool_to_call = available_tools[tool_name]
                tool_args = {key: value for key, value in function_call.args.items()}
                
                tool_response_text = tool_to_call(**tool_args)

                if tool_name == "visualizar_flujo_tiquete":
                    print(f"\n🧠 Dex Responde:\n{tool_response_text}\n")
                else:
                    final_response = chat.send_message(
                        Part.from_function_response(name=tool_name, response={"content": tool_response_text})
                    )
                    print(f"\n🧠 Dex Responde:\n{final_response.text}\n")
            else:
                print(f"\n🧠 Dex Responde:\n{response.text}\n")

        except Exception as e:
            print(f"🔴 Ocurrió un error inesperado: {e}")
            print("Por favor, intenta de nuevo.")

if __name__ == "__main__":
    main()
