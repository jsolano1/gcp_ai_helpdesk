
import os
import uuid
import json
from datetime import datetime
from google.cloud import bigquery
from src.config import GCP_PROJECT_ID, BIGQUERY_DATASET_ID, TICKETS_TABLE_NAME, EVENTOS_TABLE_NAME

client = bigquery.Client(project=GCP_PROJECT_ID)
ROLES_TABLE_ID = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET_ID}.roles_usuarios"
TICKETS_TABLE_ID = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET_ID}.{TICKETS_TABLE_NAME}"
EVENTOS_TABLE_ID = f"{GCP_PROJECT_ID}.{BIGQUERY_DATASET_ID}.{EVENTOS_TABLE_NAME}"

def registrar_evento(ticket_id: str, tipo_evento: str, autor: str, detalles: dict):
    """Función centralizada para insertar un nuevo evento en la tabla de eventos."""
    evento_id = str(uuid.uuid4())
    query = f"""
        INSERT INTO `{EVENTOS_TABLE_ID}` 
        (EventoID, TicketID, FechaEvento, Autor, TipoEvento, Detalles)
        VALUES (@evento_id, @ticket_id, @timestamp, @autor, @tipo_evento, @detalles)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("evento_id", "STRING", evento_id),
            bigquery.ScalarQueryParameter("ticket_id", "STRING", ticket_id),
            bigquery.ScalarQueryParameter("timestamp", "TIMESTAMP", datetime.utcnow()),
            bigquery.ScalarQueryParameter("autor", "STRING", autor),
            bigquery.ScalarQueryParameter("tipo_evento", "STRING", tipo_evento),
            bigquery.ScalarQueryParameter("detalles", "STRING", json.dumps(detalles)),
        ]
    )
    client.query(query, job_config=job_config).result()
    print(f"✅ Evento '{tipo_evento}' registrado para el tiquete {ticket_id}.")


def validar_tiquete(ticket_id: str) -> (str, bool):
    """
    Normaliza un ID de tiquete a mayúsculas y verifica si existe en la base de datos.
    Devuelve el ID normalizado y un booleano indicando si existe.
    """
    id_normalizado = ticket_id.upper()
    
    query = f"SELECT COUNT(TicketID) as count FROM `{TICKETS_TABLE_ID}` WHERE TicketID = @ticket_id"
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("ticket_id", "STRING", id_normalizado)
        ]
    )
    
    try:
        query_job = client.query(query, job_config=job_config)
        results = query_job.result()
        count = next(results).count
        
        existe = count > 0
        return id_normalizado, existe
        
    except Exception as e:
        print(f"🔴 Error al validar el tiquete {id_normalizado}: {e}")
        return id_normalizado, False

def obtener_rol_usuario(user_email: str) -> (str, str):
    """
    Consulta la tabla de roles para obtener el rol y departamento de un usuario.
    Si el usuario no se encuentra, devuelve el rol 'user' por defecto.
    """
    query = f"""
        SELECT role, department
        FROM `{ROLES_TABLE_ID}`
        WHERE user_email = @user_email
        LIMIT 1
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("user_email", "STRING", user_email)
        ]
    )
    
    try:
        results = list(client.query(query, job_config=job_config).result())
        if results:
            user_data = results[0]
            print(f"✅ Rol encontrado para {user_email}: {user_data.role}")
            return user_data.role, user_data.department
        else:
            # Si no está en la tabla, es un usuario estándar
            print(f"✅ Usuario {user_email} no encontrado en tabla de roles. Asignado rol 'user'.")
            return "user", None
            
    except Exception as e:
        print(f"🔴 Error al obtener el rol para {user_email}: {e}")
        # En caso de error, se asigna el rol más restrictivo por seguridad
        return "user", None
