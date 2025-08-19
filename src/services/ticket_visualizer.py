import os
import json
from dotenv import load_dotenv
from google.cloud import bigquery
from vertexai.preview.vision_models import ImageGenerationModel
from src.utils.bigquery_client import client, EVENTOS_TABLE_ID, validar_tiquete

load_dotenv()
IMAGEN_MODEL = os.getenv("IMAGEN_MODEL")

def visualizar_flujo_tiquete(ticket_id: str) -> str:
    """
    Genera una INFOGRAFÍA HORIZONTAL del flujo de un tiquete con un estilo de UI moderno,
    conciso y mostrando todos los pasos clave.
    """
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
        estado_final = "Abierto"

        for i, evento in enumerate(eventos):
            tipo_evento = evento.TipoEvento.replace("_", " ").title()
            fecha_local = evento.FechaEvento.astimezone().strftime('%d %b, %H:%M')
            detalles = json.loads(evento.Detalles)
            
            es_el_ultimo_evento = (i == total_eventos - 1)
            
            prompt_para_imagen += "\n- "
            
            if es_el_ultimo_evento and tipo_evento.lower() != "cerrado":
                prompt_para_imagen += "Un círculo grande con un gradiente de azul a cian, con un sutil brillo exterior para indicar que es el estado actual. "
                prompt_para_imagen += f"Dentro del círculo, el texto '{tipo_evento}' en negrita blanca. "
                prompt_para_imagen += f"Debajo, la fecha '{fecha_local}' en gris claro. "
            else:
                prompt_para_imagen += "Un círculo pequeño de color verde sólido con un ícono de checkmark blanco adentro. "
                prompt_para_imagen += f"Arriba del círculo, el título del evento '{tipo_evento}' en negrita. "
                prompt_para_imagen += f"Debajo del círculo, la fecha '{fecha_local}' en texto gris. "
            
            if tipo_evento.lower() == "creado":
                prompt_para_imagen += f"Añade un texto pequeño debajo de la fecha: 'Prioridad {detalles.get('prioridad_asignada', 'N/A')}'. "
            elif tipo_evento.lower() == "reasignado":
                prompt_para_imagen += f"Añade un texto pequeño debajo de la fecha: 'Asignado a {detalles.get('nuevo_responsable', 'N/A')}'. "
            elif tipo_evento.lower() == "cerrado":
                estado_final = "Cerrado"
        
        generation_model = ImageGenerationModel.from_pretrained(IMAGEN_MODEL)
        
        print("▶️  Generando imagen estandarizada...")
        images = generation_model.generate_images(
            prompt=prompt_para_imagen,
            number_of_images=1,
            aspect_ratio="16:9",
            #seed=42
        )
        
        
        carpeta_destino = "img_flujos"
        os.makedirs(carpeta_destino, exist_ok=True)
        
        nombre_archivo = f"{ticket_id}_timeline.png"
        ruta_completa = os.path.join(carpeta_destino, nombre_archivo)
        
        images[0]._pil_image.save(ruta_completa)
        
        print(f"✅ Imagen guardada en: {ruta_completa}")
        return f"He generado una línea de tiempo visual y la he guardado en la carpeta '{carpeta_destino}' con el nombre '{nombre_archivo}'. Por favor, ábrela para verla."

    except Exception as e:
        print(f"🔴 Error al visualizar el flujo: {e}")
        return f"Ocurrió un error al intentar generar el diagrama del tiquete: {e}"