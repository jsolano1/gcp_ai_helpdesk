from google.cloud import firestore
from vertexai.generative_models import Content, Part

db = firestore.Client()
HISTORY_COLLECTION = "chat_histories"

def save_chat_history(user_id: str, history: list):
    """Guarda el historial de una conversación en Firestore, si el user_id es válido."""
    if not user_id or "/" not in user_id:
        print(f"ID de usuario inválido, no se guardará el historial: {user_id}")
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

def get_chat_history(user_id: str) -> list:
    """Recupera el historial de una conversación desde Firestore, si el user_id es válido."""
    if not user_id or "/" not in user_id:
        print(f"ID de usuario inválido, no se obtendrá el historial: {user_id}")
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