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
    Convierte un objeto Part a un diccionario para guardarlo en Firestore.
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
    
    if part_type == "function_call":
        fc = FunctionCall(name=part_dict.get("name"), args=part_dict.get("args"))
        # --- ESTA ES LA LÍNEA CORREGIDA ---
        return Part(fc)
    
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
    now = datetime.now(timezone.utc)

    if session_doc.exists:
        session_data = session_doc.to_dict()
        last_activity = session_data.get("last_activity")
        
        if last_activity and (now - last_activity > timedelta(hours=24)):
            print(f"▶️  La sesión para {user_id} ha expirado. Creando una nueva sesión.")
            new_session_id = str(uuid.uuid4())
            session_doc_ref.set({"active_session_id": new_session_id, "last_activity": now})
            return new_session_id
        else:
            return session_data.get("active_session_id")
    else:
        print(f"▶️  Creando primera sesión para el usuario {user_id}.")
        new_session_id = str(uuid.uuid4())
        session_doc_ref.set({"active_session_id": new_session_id, "last_activity": now})
        return new_session_id

def save_chat_history(session_id: str, user_id_full: str, history: list, num_existing: int):
    """Guarda los nuevos mensajes en el documento de la sesión activa."""
    if not session_id: return
    
    history_doc_ref = db.collection(HISTORY_COLLECTION).document(session_id)
    session_doc_ref = db.collection(SESSION_COLLECTION).document(_get_clean_user_id(user_id_full))
    now = datetime.now(timezone.utc)
    
    new_messages = history[num_existing:]
    if not new_messages: return

    items_to_save = [
        {
            "role": item.role,
            "parts": [_serialize_part(p) for p in item.parts if p],
            "timestamp": now
        }
        for item in new_messages
    ]

    @firestore.transactional
    def update_in_transaction(transaction, history_ref, session_ref):
        transaction.set(history_ref, {"history": firestore.ArrayUnion(items_to_save), "user_id": _get_clean_user_id(user_id_full)}, merge=True)
        transaction.update(session_ref, {"last_activity": now})

    transaction = db.transaction()
    update_in_transaction(transaction, history_doc_ref, session_doc_ref)

def get_chat_history(session_id: str) -> list:
    """Recupera y reconstruye el historial completo de una sesión."""
    if not session_id: return []
    
    doc_ref = db.collection(HISTORY_COLLECTION).document(session_id)
    doc = doc_ref.get()
    if doc.exists:
        history_from_db = doc.to_dict().get("history", [])
        reconstructed_history = []
        for item in history_from_db:
            parts = [_deserialize_part(p) for p in item.get("parts", []) if p]
            if parts:
                reconstructed_history.append(Content(role=item["role"], parts=parts))
        return reconstructed_history
    return []