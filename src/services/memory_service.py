from google.cloud import firestore
from vertexai.generative_models import Content, Part

db = firestore.Client()
HISTORY_COLLECTION = "chat_histories"

def _get_clean_user_id(user_id_full: str) -> str:
    """Extrae el ID numérico de la ruta 'users/12345'."""
    if not user_id_full or "/" not in user_id_full:
        return None
    return user_id_full.split('/')[-1]

def save_chat_history(user_id_full: str, history: list):
    """Guarda el historial de una conversación en Firestore."""
    user_id = _get_clean_user_id(user_id_full)
    if not user_id:
        print(f"ID de usuario inválido, no se guardará el historial: {user_id_full}")
        return

    try:
        doc_ref = db.collection(HISTORY_COLLECTION).document(user_id)
        history_to_save = [
            {"role": item.role, "parts": [part.text for part in item.parts]}
            for item in history
        ]
        doc_ref.set({"history": history_to_save})
    except Exception as e:
        print(f"Error al guardar el historial para {user_id}: {e}")

def get_chat_history(user_id_full: str) -> list:
    """Recupera el historial de una conversación desde Firestore."""
    user_id = _get_clean_user_id(user_id_full)
    if not user_id:
        print(f"ID de usuario inválido, no se obtendrá el historial: {user_id_full}")
        return []

    try:
        doc_ref = db.collection(HISTORY_COLLECTION).document(user_id)
        doc = doc_ref.get()
        if doc.exists:
            history_from_db = doc.to_dict().get("history", [])
            return [
                Content(role=item["role"], parts=[Part.from_text(text) for text in item["parts"]])
                for item in history_from_db
            ]
        return []
    except Exception as e:
        print(f"Error al obtener el historial para {user_id}: {e}")
        return []