from google.cloud import firestore
from vertexai.generative_models import Content, Part, FunctionCall
from datetime import datetime, timedelta, timezone
import uuid

db = firestore.Client()
HISTORY_COLLECTION = "chat_histories"
SESSION_COLLECTION = "active_sessions"

def _get_clean_user_id(user_id_full: str) -> str:
    """Extrae el ID numérico de la ruta 'users/12345'."""
    if not user_id_full or "/" not in user_id_full:
        return None
    return user_id_full.split('/')[-1]

def _serialize_part(part: Part) -> dict:
    """
    Convierte un objeto Part a un diccionario para guardarlo en Firestore,
    asegurándose de que todos los tipos de datos son compatibles.
    """
    if part.function_call:
        return {
            "type": "function_call",
            "name": part.function_call.name,
            "args": {key: value for key, value in part.function_call.args.items()}
        }
    if part.function_response:
        return {
            "type": "function_response",
            "name": part.function_response.name,
            "content": {key: value for key, value in part.function_response.response.items()}
        }
    if hasattr(part, 'text'):
        return {"type": "text", "content": part.text}
    
    return {}

def _deserialize_part(part_dict: dict) -> Part:
    """Convierte un diccionario de Firestore de vuelta a un objeto Part."""
    part_type = part_dict.get("type")
    if part_type == "text":
        return Part.from_text(part_dict.get("content", ""))
    
    # --- CORRECCIÓN CLAVE: Usar el constructor directo para FunctionCall ---
    if part_type == "function_call":
        # Primero se crea el objeto FunctionCall
        fc = FunctionCall(name=part_dict.get("name"), args=part_dict.get("args"))
        # Luego se crea el objeto Part pasándole el FunctionCall
        return Part(function_call=fc)
    
    if part_type == "function_response":
        return Part.from_function_response(
            name=part_dict.get("name"), response=part_dict.get("content")
        )
    return None

def get_or_create_active_session(user_id_full: str) -> str:
    """
    Obtiene la sesión activa de un usuario o crea una nueva si la anterior ha expirado (más de 24h).
    """
    user_id = _get_clean_user_id(user_id_full)
    if not user_id: return None

    session_doc_ref = db.collection(SESSION_COLLECTION).document(user_id)
    session_doc = session_doc_ref.get()
    now