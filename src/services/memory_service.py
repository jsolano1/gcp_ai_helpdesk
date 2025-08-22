from google.cloud import firestore
from vertexai.generative_models import Content
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
    """
    Guarda los nuevos mensajes en Firestore usando el formato oficial de la librería
    y añadiendo un timestamp.
    """
    if not session_id: return
    
    history_doc_ref = db.collection(HISTORY_COLLECTION).document(session_id)
    session_doc_ref = db.collection(SESSION_COLLECTION).document(_get_clean_user_id(user_id_full))
    now = datetime.now(timezone.utc)
    
    new_messages = history[num_existing:]
    if not new_messages: return

    # 1. Convierte los objetos a diccionarios usando el método oficial .to_dict()
    items_to_save = [msg.to_dict() for msg in new_messages]
    
    # 2. Añade nuestro campo personalizado 'timestamp' a cada diccionario
    for item in items_to_save:
        item['timestamp'] = now

    @firestore.transactional
    def update_in_transaction(transaction, history_ref, session_ref):
        transaction.set(history_ref, {"history": firestore.ArrayUnion(items_to_save), "user_id": _get_clean_user_id(user_id_full)}, merge=True)
        transaction.update(session_ref, {"last_activity": now})

    transaction = db.transaction()
    update_in_transaction(transaction, history_doc_ref, session_doc_ref)

def get_chat_history(session_id: str) -> list:
    """
    Recupera el historial y lo prepara para la librería, eliminando campos personalizados.
    """
    if not session_id: return []
    
    doc_ref = db.collection(HISTORY_COLLECTION).document(session_id)
    doc = doc_ref.get()
    if not doc.exists:
        return []

    history_from_db = doc.to_dict().get("history", [])
    reconstructed_history = []
    
    for item in history_from_db:
        # --- ESTA ES LA CORRECCIÓN HOLÍSTICA Y DEFINITIVA ---
        # 1. Crea un diccionario limpio solo con los campos que la librería entiende.
        clean_item = {
            "role": item.get("role"),
            "parts": item.get("parts", [])
        }
        
        # 2. Reconstruye el objeto Content usando el diccionario limpio
        if clean_item["parts"]:
            reconstructed_history.append(Content.from_dict(clean_item))
            
    return reconstructed_history