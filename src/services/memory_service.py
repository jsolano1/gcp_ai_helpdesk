from google.cloud import firestore
from vertexai.generative_models import Content, Part
from datetime import datetime, timedelta
import uuid

db = firestore.Client()
HISTORY_COLLECTION = "chat_histories"
SESSION_COLLECTION = "active_sessions"

def _get_clean_user_id(user_id_full: str) -> str:
    """Extrae el ID numérico de la ruta 'users/12345'."""
    if not user_id_full or "/" not in user_id_full:
        return None
    return user_id_full.split('/')[-1]

def get_or_create_active_session(user_id_full: str) -> str:
    """
    Obtiene la sesión activa de un usuario o crea una nueva si la anterior ha expirado (más de 24h).
    No borra datos, solo crea una nueva referencia de sesión.
    Devuelve el ID de la sesión que se debe usar.
    """
    user_id = _get_clean_user_id(user_id_full)
    if not user_id: return None

    session_doc_ref = db.collection(SESSION_COLLECTION).document(user_id)
    session_doc = session_doc_ref.get()

    now = datetime.utcnow()

    if session_doc.exists:
        session_data = session_doc.to_dict()
        last_activity = session_data.get("last_activity")
        
        if last_activity and (now - last_activity > timedelta(hours=24)):
            print(f"▶️  La sesión para {user_id} ha expirado. Creando una nueva sesión.")
            new_session_id = str(uuid.uuid4())
            session_doc_ref.set({
                "active_session_id": new_session_id,
                "last_activity": now,
                "user_email": user_id_full  # Guardamos el email para referencia
            })
            return new_session_id
        else:
            return session_data.get("active_session_id")
    else:
        print(f"▶️  Creando primera sesión para el usuario {user_id}.")
        new_session_id = str(uuid.uuid4())
        session_doc_ref.set({
            "active_session_id": new_session_id,
            "last_activity": now
        })
        return new_session_id

def save_chat_history(session_id: str, user_id_full: str, history: list, num_existing: int):
    """Guarda los nuevos mensajes en el documento de la sesión activa."""
    if not session_id: return
    
    history_doc_ref = db.collection(HISTORY_COLLECTION).document(session_id)
    session_doc_ref = db.collection(SESSION_COLLECTION).document(_get_clean_user_id(user_id_full))
    now = datetime.utcnow()
    
    new_messages = history[num_existing:]
    if not new_messages: return

    items_to_save = [
        {"role": item.role, "parts": [part.text for part in item.parts], "timestamp": now}
        for item in new_messages
    ]

    @firestore.transactional
    def update_in_transaction(transaction, history_ref, session_ref):
        transaction.set(history_ref, {"history": firestore.ArrayUnion(items_to_save), "user_id": _get_clean_user_id(user_id_full)}, merge=True)
        transaction.update(session_ref, {"last_activity": now})

    transaction = db.transaction()
    update_in_transaction(transaction, history_doc_ref, session_doc_ref)


def get_chat_history(session_id: str) -> list:
    """Recupera el historial de una sesión de chat específica."""
    if not session_id: return []
    
    doc_ref = db.collection(HISTORY_COLLECTION).document(session_id)
    doc = doc_ref.get()
    if doc.exists:
        history_from_db = doc.to_dict().get("history", [])
        return [
            Content(role=item["role"], parts=[Part.from_text(p) for p in item["parts"]])
            for item in history_from_db
        ]
    return []