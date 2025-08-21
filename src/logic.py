# src/logic.py

import os
import json
import traceback
from dotenv import load_dotenv
import vertexai
from vertexai.generative_models import GenerativeModel, Part

# Carga las variables de entorno desde el archivo .env
load_dotenv()
GEMINI_CHAT_MODEL = os.getenv("GEMINI_CHAT_MODEL")

# Importaciones de módulos locales
from src.config import GCP_PROJECT_ID, LOCATION
from src.services import ticket_manager, ticket_querier, ticket_visualizer
from src.tools.tool_definitions import all_tools_config

# Inicializa Vertex AI con el proyecto y la ubicación de GCP
vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)

# Define el prompt del sistema que guía el comportamiento del modelo de IA
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

# Inicializa el modelo generativo con el prompt del sistema y las herramientas disponibles
model = GenerativeModel(GEMINI_CHAT_MODEL, system_instruction=system_prompt, tools=[all_tools_config])

# Mapea los nombres de las herramientas a las funciones correspondientes
available_tools = {
    "crear_tiquete_helpdesk": ticket_manager.crear_tiquete,
    "consultar_estado_tiquete": ticket_querier.consultar_estado_tiquete,
    "cerrar_tiquete": ticket_manager.cerrar_tiquete,
    "reasignar_tiquete": ticket_manager.reasignar_tiquete,
    "modificar_sla_manual": ticket_manager.modificar_sla_manual,
    "visualizar_flujo_tiquete": ticket_visualizer.visualizar_flujo_tiquete,
    "consultar_metricas": ticket_querier.consultar_metricas
}

def handle_dex_logic(user_message: str, user_email: str, user_display_name: str) -> str:
    """
    Gestiona la lógica de conversación con Gemini y la ejecución de herramientas.
    Devuelve una respuesta de texto simple.
    """
    print(json.dumps({
        "log_name": "HandleDexLogic_Inicio",
        "mensaje": "Iniciando lógica de Dex.",
        "input": {
            "mensaje_usuario": user_message,
            "email_usuario": user_email,
            "nombre_usuario": user_display_name
        }
    }))

    # Valida que el email del usuario pertenezca a un dominio autorizado
    authorized_domains = ["@connect.inc", "@consoda.com", "@premier.io"]
    if not any(user_email.endswith(domain) for domain in authorized_domains):
        mensaje_error = "Lo siento, solo puedo procesar solicitudes de dominios autorizados."
        print(json.dumps({"log_name": "HandleDexLogic_Alerta", "alerta": "Correo no autorizado", "email": user_email}))
        return mensaje_error

    try:
        # Inicia una nueva sesión de chat con el modelo
        chat = model.start_chat()
        # Envía el mensaje del usuario al modelo
        response = chat.send_message(user_message)

        # Revisa si la respuesta del modelo incluye una llamada a una función
        function_call = response.candidates[0].content.parts[0].function_call
        
        if function_call and function_call.name:
            tool_name = function_call.name
            tool_to_call = available_tools.get(tool_name)
            
            if not tool_to_call:
                raise ValueError(f"Herramienta desconocida solicitada por el modelo: {tool_name}")

            tool_args = {key: value for key, value in function_call.args.items()}
            print(json.dumps({"log_name": "HandleDexLogic_ToolCall", "mensaje": "IA solicita llamar a función", "funcion": tool_name, "argumentos": tool_args}))
            
            # Si la herramienta es para crear un tiquete, inyecta los datos del solicitante
            if tool_name == "crear_tiquete_helpdesk":
                tool_args["solicitante"] = user_email
                tool_args["nombre_solicitante"] = user_display_name
                print(json.dumps({"log_name": "HandleDexLogic_Info", "info": "Inyectando datos del solicitante automáticamente"}))

            # Ejecuta la función/herramienta con sus argumentos
            tool_response_text = tool_to_call(**tool_args)
            print(json.dumps({"log_name": "HandleDexLogic_ToolResponse", "mensaje": "Respuesta de la función ejecutada", "funcion": tool_name, "resultado": tool_response_text}))

            # Envía la respuesta de la herramienta de vuelta al modelo para que genere una respuesta final en lenguaje natural
            final_response = chat.send_message(
                Part.from_function_response(name=tool_name, response={"content": tool_response_text})
            )
            final_text = final_response.text
        
        else:
            # Si no hubo llamada a función, la respuesta es el texto directo del modelo
            final_text = response.text

        print(json.dumps({"log_name": "HandleDexLogic_Exito", "mensaje": "Lógica finalizada. Respuesta generada.", "respuesta_texto": final_text}))
        return final_text

    except Exception as e:
        # Manejo de errores críticos, registrando todos los detalles
        error_details = {
            "log_name": "HandleDexLogic_Error",
            "nivel": "CRITICO",
            "mensaje": "Error CRÍTICO en la lógica de Dex",
            "tipo_error": type(e).__name__,
            "error": str(e),
            "traceback": traceback.format_exc()
        }
        print(json.dumps(error_details))
        
        return "Lo siento, ocurrió un error interno al procesar tu solicitud. El equipo técnico ha sido notificado."