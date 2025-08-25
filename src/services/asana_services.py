import os
import asana
from dotenv import load_dotenv

load_dotenv()

ASANA_PAT = os.getenv("ASANA_PERSONAL_ACCESS_TOKEN")
ASANA_PROJECT_GID = os.getenv("ASANA_PROJECT_GID")

ASANA_ASSIGNEE_MAP = {
    os.getenv("DATA_ENGINEERING_LEAD"): os.getenv("ASANA_LEAD_DATA_ENGINEERING_GID"),
    os.getenv("BI_ANALYST_LEAD"): os.getenv("ASANA_LEAD_BI_ANALYST_GID")
}

def get_asana_client():
    """Configura y devuelve el cliente de la API de Asana."""
    if not ASANA_PAT:
        print("🔴 Error: La variable de entorno ASANA_PERSONAL_ACCESS_TOKEN no está configurada.")
        return None
    
    client = asana.Client.access_token(ASANA_PAT)
    return client

def crear_tarea_asana(nombre_tarea: str, notas: str, responsable_email: str, fecha_entrega: str) -> dict:
    """
    Crea una nueva tarea en un proyecto específico de Asana.
    
    Args:
        nombre_tarea: Título de la tarea en Asana.
        notas: Descripción detallada de la tarea.
        responsable_email: Email del líder de equipo a quien se asignará.
        fecha_entrega: Fecha de entrega en formato YYYY-MM-DD.
        
    Returns:
        Un diccionario con el ID y la URL de la tarea creada, o un error.
    """
    client = get_asana_client()
    if not client or not ASANA_PROJECT_GID:
        return {"error": "El cliente de Asana no está configurado correctamente."}

    assignee_gid = ASANA_ASSIGNEE_MAP.get(responsable_email)
    if not assignee_gid:
        return {"error": f"No se encontró un GID de Asana para el responsable: {responsable_email}"}

    try:
        task_data = {
            "name": nombre_tarea,
            "notes": notas,
            "projects": [ASANA_PROJECT_GID],
            "assignee": assignee_gid,
            "due_on": fecha_entrega
        }
        
        print(f"▶️  Creando tarea en Asana para {responsable_email}...")
        result = client.tasks.create_task(task_data, opt_pretty=True)
        
        print(f"✅ Tarea creada en Asana: {result['gid']}")
        return {
            "asana_task_gid": result['gid'],
            "asana_task_url": f"https://app.asana.com/0/{ASANA_PROJECT_GID}/{result['gid']}"
        }

    except Exception as e:
        print(f"🔴 Error al crear la tarea en Asana: {e}")
        return {"error": str(e)}