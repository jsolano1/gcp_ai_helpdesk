import os
import vertexai
from vertexai.language_models import TextEmbeddingModel
from google.cloud import aiplatform
from google.cloud import storage
from dotenv import load_dotenv

load_dotenv()

GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("LOCATION")
KB_BUCKET_NAME = os.getenv("KNOWLEDGE_BASE_BUCKET")
VECTOR_SEARCH_ENDPOINT_ID = os.getenv("VECTOR_SEARCH_ENDPOINT_ID")
EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME")
DEPLOYED_INDEX_ID = os.getenv("DEPLOYED_INDEX_ID")

try:
    vertexai.init(project=GCP_PROJECT_ID, location=LOCATION)
    embedding_model = TextEmbeddingModel.from_pretrained(EMBEDDING_MODEL_NAME)
    storage_client = storage.Client()
    aiplatform.init(project=GCP_PROJECT_ID, location=LOCATION)
    
    if VECTOR_SEARCH_ENDPOINT_ID:
        index_endpoint = aiplatform.MatchingEngineIndexEndpoint(index_endpoint_name=VECTOR_SEARCH_ENDPOINT_ID)
    else:
        index_endpoint = None
except Exception as e:
    print(f"⚠️  Advertencia al inicializar los servicios de IA: {e}")
    index_endpoint = None


def search_knowledge_base(user_query: str) -> dict | None:
    """
    Busca en la base de conocimiento usando búsqueda semántica para encontrar una respuesta relevante.
    """
    if not all([KB_BUCKET_NAME, index_endpoint, DEPLOYED_INDEX_ID]):
        print("⚠️ Advertencia: Faltan variables de configuración para la base de conocimiento. Saltando búsqueda.")
        return None

    try:
        print(f"▶️  Buscando en la base de conocimiento para: '{user_query}'")
        query_embedding = embedding_model.get_embeddings([user_query])[0].values
        
        response = index_endpoint.find_neighbors(
            deployed_index_id=DEPLOYED_INDEX_ID,
            queries=[query_embedding],
            num_neighbors=1
        )
        
        if response and response[0]:
            match = response[0][0]
            file_name = match.id
            similarity_score = 1 - match.distance
            
            print(f"✅ Coincidencia encontrada: '{file_name}' con una similitud de {similarity_score:.2%}")

            if similarity_score > 0.75:
                bucket = storage_client.bucket(KB_BUCKET_NAME)
                blob = bucket.blob(f"fuentes/{file_name}")
                
                if blob.exists():
                    answer_content = blob.download_as_text()
                    return {"answer": answer_content, "source": file_name}

        print("ℹ️  No se encontraron resultados suficientemente relevantes en la base de conocimiento.")
        return None
        
    except Exception as e:
        print(f"🔴 Error al buscar en la base de conocimiento: {e}")
        return None