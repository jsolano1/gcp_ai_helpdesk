
import os
import json
from dotenv import load_dotenv
from google.cloud import bigquery
from vertexai.generative_models import GenerativeModel
from src.utils.bigquery_client import client, TICKETS_TABLE_ID, EVENTOS_TABLE_ID, validar_tiquete

load_dotenv()
GEMINI_TASK_MODEL = os.getenv("GEMINI_TASK_MODEL")

def consultar_estado_tiquete(ticket_id: str) -> str:
    """Consulta el último evento para determinar el estado actual de un tiquete."""
    ticket_id = ticket_id.upper()
    id_normalizado, existe = validar_tiquete(ticket_id)
    query = f"""
        SELECT TipoEvento, Detalles
        FROM `{EVENTOS_TABLE_ID}`
        WHERE TicketID = @ticket_id
        ORDER BY FechaEvento DESC
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("ticket_id", "STRING", ticket_id)])
    try:
        results = list(client.query(query, job_config=job_config).result())
        if not results:
            return f"No se encontró ningún tiquete o evento con el ID '{ticket_id}'."
        
        ultimo_evento = results[0]
        detalles = json.loads(ultimo_evento.Detalles)
        
        if ultimo_evento.TipoEvento == "CREADO":
            return f"El tiquete {ticket_id} está 'Abierto' y asignado a {detalles.get('responsable_inicial')}."
        elif ultimo_evento.TipoEvento == "CERRADO":
            return f"El tiquete {ticket_id} está 'Cerrado'. Resolución: {detalles.get('resolucion')}."
        elif ultimo_evento.TipoEvento == "REASIGNADO":
            return f"El tiquete {ticket_id} está 'Abierto' y ha sido reasignado a {detalles.get('nuevo_responsable')}."
        else:
            return f"El último evento para el tiquete {ticket_id} fue '{ultimo_evento.TipoEvento}'."
    except Exception as e:
        print(f"🔴 Error al consultar estado: {e}")
        return f"Ocurrió un error al consultar el estado del tiquete: {e}"
    pass

def consultar_metricas(pregunta_del_usuario: str) -> str:
    """Convierte una pregunta en lenguaje natural sobre métricas de tiquetes en una consulta SQL."""
    model = GenerativeModel(GEMINI_TASK_MODEL)
    
    prompt_para_sql = f"""
    Tu tarea es actuar como un experto analista de datos y convertir una pregunta en una consulta SQL para Google BigQuery.
    **Esquema de Tablas:**
    1. `tickets` (Creación): TicketID, Solicitante, FechaCreacion.
    2. `eventos_tiquetes` (Historial): TicketID, FechaEvento, TipoEvento, Detalles (JSON String).
    **REGLAS CRÍTICAS E INQUEBRANTABLES (¡SÍGUELAS SIEMPRE!):**
    1.  **PARA ENCONTRAR EL ÚLTIMO ESTADO/RESPONSABLE (LA LÓGICA MÁS IMPORTANTE):**
        -   Usa SIEMPRE un `WITH` clause para crear una tabla temporal llamada `UltimosEventos`.
        -   Dentro de `UltimosEventos`, usa la función de ventana `ROW_NUMBER() OVER(PARTITION BY TicketID ORDER BY FechaEvento DESC) as rn`.
        -   Filtra SIEMPRE por `WHERE rn = 1` para obtener solo el evento más reciente de cada tiquete.
        -   **Responsable Actual:** Se encuentra DENTRO del JSON `Detalles`. Para obtenerlo, usa `JSON_EXTRACT_SCALAR(Detalles, '$.responsable_inicial')` o `JSON_EXTRACT_SCALAR(Detalles, '$.nuevo_responsable')`.
    2.  **PARA CALCULAR TIEMPO DE RESOLUCIÓN:**
        -   Calcula la diferencia en **MINUTOS**: `TIMESTAMP_DIFF(fecha_cierre, fecha_creacion, MINUTE)`.
        -   Luego, si se piden horas, divide el resultado por 60.0: `AVG(...) / 60.0`. Esto dará decimales y será más preciso.
        -   `fecha_creacion` se obtiene de la tabla `tickets`.
        -   `fecha_cierre` se obtiene de `FechaEvento` de la tabla `eventos_tiquetes` donde `TipoEvento` sea 'CERRADO'.
        -   SIEMPRE haz un `JOIN` entre `tickets` y `eventos_tiquetes` por `TicketID`.
    3.  **REGLAS DE FORMATO SQL:**
        -   Usa los nombres completos de las tablas: `{TICKETS_TABLE_ID}` y `{EVENTOS_TABLE_ID}`.
        -   Responde **ÚNICAMENTE con el código SQL**. No añadas explicaciones, ni la palabra "sql", ni ```.
    Pregunta del usuario: "{pregunta_del_usuario}"
    Consulta SQL:
    """
    try:
        print("▶️  Generando consulta SQL con IA...")
        response = model.generate_content(prompt_para_sql)
        sql_query = response.text.strip().replace("`", "").replace("sql", "", 1)
        print(f"▶️  SQL Generado (limpio): {sql_query}")
        print("▶️  Ejecutando consulta en BigQuery...")
        query_job = client.query(sql_query)
        results = query_job.result()
        rows = [dict(row) for row in results]
        if not rows:
            return "La consulta no arrojó resultados."
        return json.dumps(rows)
    except Exception as e:
        print(f"🔴 Error al consultar métricas: {e}")
        return f"Ocurrió un error al procesar la consulta de métricas: {e}"
    pass
