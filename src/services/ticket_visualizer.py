import os
import json
import io
from dotenv import load_dotenv
from google.cloud import bigquery
from google.cloud import storage
from vertexai.preview.vision_models import ImageGenerationModel
from src.utils.bigquery_client import client, EVENTOS_TABLE_ID, validar_tiquete

load_dotenv()

IMAGEN_MODEL = os.getenv("IMAGEN_MODEL")
GCS_BUCKET_NAME = os.getenv("GCS_BUCKET_NAME")

def visualizar_flujo_tiquete(ticket_id: str, **kwargs) -> str:
    """
    Genera una infografía, la sube a Google Cloud Storage y devuelve la URL pública.
    """
    if not GCS_BUCKET_NAME:
        return "Error de configuración: La variable de entorno GCS_BUCKET_NAME no está definida."

    ticket_id = ticket_id.upper()
    id_normalizado, existe = validar_tiquete(ticket_id)
    if not existe:
        return f"Error: El tiquete '{id_normalizado}' no fue encontrado."

    query = f"""
        SELECT TipoEvento, FechaEvento, Detalles, Autor
        FROM `{EVENTOS_TABLE_ID}`
        WHERE TicketID = @ticket_id
        ORDER BY FechaEvento ASC
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ticket_id", "STRING", ticket_id)
        ]
    )
    
    try:
        eventos = list(client.query(query, job_config=job_config).result())
        
        if not eventos:
            return f"No se encontró historial para el tiquete con ID '{ticket_id}'."
        
        prompt_para_imagen = (
            f"Crea una infografía de una **línea de tiempo horizontal** para el tiquete de soporte '{ticket_id}'. "
            "El diseño debe ser **ultra moderno, limpio y minimalista**, similar a los componentes de UI de alta gama. "
            "Usa una paleta de colores sofisticada con gradientes sutiles. Fondo blanco o gris muy claro (#F9FAFB).\n\n"
            f"En la parte superior, agrega un título principal que diga 'Historial del Tiquete {ticket_id}'.\n\n"
            "Dibuja una línea gris delgada que conecte los siguientes hitos en orden cronológico de izquierda a derecha:\n"
        )

        total_eventos = len(eventos)
        for i, evento in enumerate(eventos):
            tipo_evento = evento.TipoEvento.replace("_", " ").title()
            fecha_local = evento.FechaEvento.astimezone().strftime('%d %b, %H:%M')
            detalles = json.loads(evento.Detalles)
            es_el_ultimo_evento = (i == total_eventos - 1)
            
            prompt_para_imagen += "\n- "
            if es_el_ultimo_evento and tipo_evento.lower() != "cerrado":
                prompt_para_imagen += f"Un círculo grande con un gradiente de azul a cian, con un sutil brillo exterior para indicar que es el estado actual. Dentro del círculo, el texto '{tipo_evento}' en negrita blanca. Debajo, la fecha '{fecha_local}' en gris claro. "
            else:
                prompt_para_imagen += f"Un círculo pequeño de color verde sólido con un ícono de checkmark blanco adentro. Arriba del círculo, el título del evento '{tipo_evento}' en negrita. Debajo del círculo, la fecha '{fecha_local}' en texto gris. "
            
            if tipo_evento.lower() == "creado":
                prompt_para_imagen += f"Añade un texto pequeño debajo de la fecha: 'Prioridad {detalles.get('prioridad_asignada', 'N/A')}'. "
            elif tipo_evento.lower() == "reasignado":
                prompt_para_imagen += f"Añade un texto pequeño debajo de la fecha: 'Asignado a {detalles.get('nuevo_responsable', 'N/A')}'. "
        
        generation_model = ImageGenerationModel.from_pretrained(IMAGEN_MODEL)
        
        print("▶️  Generando imagen con IA...")
        images = generation_model.generate_images(
            prompt=prompt_para_imagen, number_of_images=1, aspect_ratio="16:9"
        )
        
        buffer = io.BytesIO()
        images[0]._pil_image.save(buffer, format='PNG')
        image_bytes = buffer.getvalue()

        print(f"▶️  Subiendo imagen al bucket '{GCS_BUCKET_NAME}'...")
        storage_client = storage.Client()
        bucket = storage_client.bucket(GCS_BUCKET_NAME)
        
        nombre_archivo_en_bucket = f"flujos/{ticket_id}_timeline.png"
        blob = bucket.blob(nombre_archivo_en_bucket)
        
        blob.upload_from_string(image_bytes, content_type="image/png")
        
        print(f"✅ Imagen disponible en: {blob.public_url}")
        return f"He generado una línea de tiempo visual para el tiquete {ticket_id}. Puedes verla aquí: {blob.public_url}"

    except Exception as e:
        print(f"🔴 Error al visualizar el flujo: {e}")
        return f"Ocurrió un error al intentar generar el diagrama del tiquete: {e}"