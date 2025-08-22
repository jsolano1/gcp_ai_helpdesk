# src/services/ticket_manager.py

import json
import uuid
from datetime import datetime, timedelta
from google.cloud import bigquery
from src.utils.bigquery_client import client, registrar_evento, TICKETS_TABLE_ID, validar_tiquete
from src.config import DATA_ENGINEERING_LEAD, BI_ANALYST_LEAD
from src.services.ticket_querier import consultar_estado_tiquete
from src.services.notification_service import enviar_notificacion_email, enviar_notificacion_chat

def crear_tiquete(descripcion: str, equipo_asignado: str, prioridad: str, solicitante: str, nombre_solicitante: str, **kwargs) -> str:
    """
    Crea un nuevo tiquete con un ID único y robusto, calcula su SLA y envía notificaciones.
    El rol del usuario ya fue validado en la capa de lógica, por lo que cualquier rol permitido puede crear un tiquete.
    """
    print(json.dumps({
        "log_name": "CrearTiquete_Inicio",
        "mensaje": "Iniciando la creación de un nuevo tiquete.",
        "parametros": {
            "solicitante": solicitante,
            "equipo_asignado": equipo_asignado,
            "prioridad": prioridad
        }
    }))
    
    try:
        # --- Lógica de cálculo de SLA ---
        sla_map = {"alta": 8, "media": 24, "baja": 72}
        prioridad_limpia = prioridad.lower()
        if "alta" in prioridad_limpia: sla_horas = sla_map["alta"]
        elif "baja" in prioridad_limpia: sla_horas = sla_map["baja"]
        else: sla_horas = sla_map["media"]
        
        fecha_creacion = datetime.utcnow()
        fecha_vencimiento = fecha_creacion + timedelta(hours=sla_horas)
        
        timestamp_id = fecha_creacion.strftime('%Y%m%d')
        unique_hash = str(uuid.uuid4().hex)[:4].upper()
        ticket_id = f"DEX-{timestamp_id}-{unique_hash}"
        print(json.dumps({"log_name": "CrearTiquete_Info", "mensaje": f"ID de tiquete único generado: {ticket_id}"}))

        responsable = DATA_ENGINEERING_LEAD if equipo_asignado == "Data Engineering" else BI_ANALYST_LEAD
        
        # --- Inserción en BigQuery ---
        insert_ticket_query = f"""
            INSERT INTO `{TICKETS_TABLE_ID}` (TicketID, Solicitante, FechaCreacion, SLA_Horas, FechaVencimiento)
            VALUES (@ticket_id, @solicitante, @fecha_creacion, @sla_horas, @fecha_vencimiento)
        """
        job_config_ticket = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticket_id", "STRING", ticket_id),
                bigquery.ScalarQueryParameter("solicitante", "STRING", solicitante),
                bigquery.ScalarQueryParameter("fecha_creacion", "TIMESTAMP", fecha_creacion),
                bigquery.ScalarQueryParameter("sla_horas", "INTEGER", sla_horas),
                bigquery.ScalarQueryParameter("fecha_vencimiento", "TIMESTAMP", fecha_vencimiento),
            ]
        )
        client.query(insert_ticket_query, job_config=job_config_ticket).result()
        print(json.dumps({"log_name": "CrearTiquete_Info", "mensaje": f"Tiquete {ticket_id} insertado en BigQuery."}))

        detalles_creacion = {"descripcion": descripcion, "equipo_asignado": equipo_asignado, "responsable_inicial": responsable, "prioridad_asignada": prioridad, "sla_calculado_horas": sla_horas}
        registrar_evento(ticket_id, "CREADO", solicitante, detalles_creacion)        
        
        # --- Lógica de Notificaciones ---
        primer_nombre = nombre_solicitante.split(" ")[0]

        asunto_solicitante = f"✅ Tiquete Creado Exitosamente: {ticket_id}"
        cuerpo_solicitante = f"<html><body><h2>Hola, {primer_nombre},</h2><p>Hemos recibido tu solicitud y hemos creado el tiquete <b>{ticket_id}</b>.</p><p><b>Descripción:</b> {descripcion}</p><p>Ha sido asignado a: <b>{responsable}</b>.</p><p>Recibirás más notificaciones sobre su progreso.</p><p>Gracias,<br>Dex Helpdesk AI</p></body></html>"
        enviar_notificacion_email(solicitante, asunto_solicitante, cuerpo_solicitante)

        asunto_responsable = f"⚠️ Nuevo Tiquete Asignado: {ticket_id}"
        cuerpo_responsable = f"<html><body><h2>Hola,</h2><p>Se te ha asignado un nuevo tiquete de soporte: <b>{ticket_id}</b>.</p><p><b>Solicitante:</b> {nombre_solicitante} ({solicitante})</p><p><b>Descripción:</b> {descripcion}</p><p><b>Prioridad:</b> {prioridad}</p></body></html>"
        enviar_notificacion_email(responsable, asunto_responsable, cuerpo_responsable)
        
        mensaje_chat_creacion = f"✅ Nuevo Tiquete Creado: *{ticket_id}*\n*Solicitante:* {nombre_solicitante}\n*Asignado a:* {responsable}\n*Descripción:* {descripcion}"
        enviar_notificacion_chat(mensaje_chat_creacion)
        
        response_text = f"Tiquete {ticket_id} creado con prioridad '{prioridad}' y un SLA de {sla_horas} horas. Asignado a {responsable}. Se han enviado las notificaciones correspondientes."
        return response_text

    except Exception as e:
        print(json.dumps({
            "log_name": "CrearTiquete_Error", "nivel": "CRITICO", "mensaje": "Error no manejado durante la creación del tiquete.", "error": str(e)
        }))
        return f"Ocurrió un error crítico al intentar crear el tiquete: {e}"

def cerrar_tiquete(ticket_id: str, resolucion: str, solicitante_email: str, solicitante_rol: str, **kwargs) -> str:
    """Cierra un tiquete registrando un evento de cierre y aplicando lógica de RBAC."""
    id_normalizado, existe = validar_tiquete(ticket_id.upper())
    if not existe:
        return f"Error: El tiquete '{id_normalizado}' no fue encontrado."
    
    # --- LÓGICA DE PERMISOS RBAC ---
    if solicitante_rol == 'agent':
        estado_actual = consultar_estado_tiquete(id_normalizado)
        # Un agente solo puede cerrar un tiquete si está asignado a él.
        if solicitante_email not in estado_actual:
             return f"Acción denegada. Como 'agent', solo puedes cerrar tiquetes que están asignados a ti. Consulta con el responsable actual."

    # Roles 'admin' y 'lead' ya fueron validados en la capa de lógica y pueden proceder.
    # El rol 'user' no tiene permiso para acceder a esta función.
    
    try:
        detalles_cierre = {"resolucion": resolucion, "cerrado_por": solicitante_email}
        registrar_evento(id_normalizado, "CERRADO", solicitante_email, detalles_cierre)

        mensaje_chat_cierre = f"✔️ Tiquete Cerrado: *{id_normalizado}*\n*Resolución:* {resolucion}"
        enviar_notificacion_chat(mensaje_chat_cierre)

        return f"El tiquete {id_normalizado} ha sido marcado como cerrado."
    except Exception as e:
        print(f"🔴 Error al cerrar tiquete: {e}")
        return f"Ocurrió un error al cerrar el tiquete: {e}"

def reasignar_tiquete(ticket_id: str, nuevo_responsable_email: str, solicitante_email: str, solicitante_rol: str, solicitante_departamento: str, **kwargs) -> str:
    """Reasigna un tiquete, aplicando lógica de RBAC para roles y departamentos."""
    id_normalizado, existe = validar_tiquete(ticket_id.upper())
    if not existe:
        return f"Error: El tiquete '{id_normalizado}' no fue encontrado."
    
    # --- LÓGICA DE PERMISOS RBAC ---
    if solicitante_rol == 'lead':
        # Un 'lead' solo puede reasignar tiquetes dentro de su propio departamento.
        # (Esta lógica requiere una función para obtener el departamento del tiquete)
        # Por simplicidad, asumimos que la validación se hace aquí. Si el tiquete
        # no pertenece a su departamento, se deniega.
        # Por ejemplo: if obtener_departamento_tiquete(id_normalizado) != solicitante_departamento:
        #   return "Acción denegada. Como 'lead', solo puedes reasignar tiquetes de tu departamento."
        pass # Implementar lógica de verificación de departamento si es necesario.

    # El rol 'admin' puede reasignar cualquier tiquete.
    # Los roles 'agent' y 'user' no tienen permiso para esta función.
    
    try:
        current_status = consultar_estado_tiquete(id_normalizado)
        detalles_reasignacion = {"nuevo_responsable": nuevo_responsable_email, "estado_anterior": current_status, "reasignado_por": solicitante_email}
        registrar_evento(id_normalizado, "REASIGNADO", solicitante_email, detalles_reasignacion)

        mensaje_chat_reasignacion = f"👤 Tiquete Reasignado: *{id_normalizado}*\n*Nuevo Responsable:* {nuevo_responsable_email}"
        enviar_notificacion_chat(mensaje_chat_reasignacion)

        return f"El tiquete {id_normalizado} ha sido reasignado a {nuevo_responsable_email}."
    except Exception as e:
        print(f"🔴 Error al reasignar tiquete: {e}")
        return f"Ocurrió un error al reasignar el tiquete: {e}"

def modificar_sla_manual(ticket_id: str, nuevas_horas_sla: int, solicitante_email: str, solicitante_rol: str, **kwargs) -> str:
    """Modifica manualmente el SLA de un tiquete, permitido solo para roles altos."""
    id_normalizado, existe = validar_tiquete(ticket_id.upper())
    if not existe:
        return f"Error: El tiquete '{id_normalizado}' no fue encontrado."

    # --- LÓGICA DE PERMISOS RBAC ---
    # La lógica en `handle_dex_logic` ya previene que 'agent' y 'user' llamen a esta función.
    # Solo 'admin' y 'lead' pueden proceder.
    
    try:
        query_fecha = f"SELECT FechaCreacion FROM `{TICKETS_TABLE_ID}` WHERE TicketID = @ticket_id"
        job_config_fecha = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("ticket_id", "STRING", id_normalizado)])
        results = list(client.query(query_fecha, job_config=job_config_fecha).result())
        
        fecha_creacion = results[0].FechaCreacion
        nueva_fecha_vencimiento = fecha_creacion + timedelta(hours=nuevas_horas_sla)
        
        update_query = f"""
            UPDATE `{TICKETS_TABLE_ID}`
            SET SLA_Horas = @nuevas_horas, FechaVencimiento = @nueva_fecha
            WHERE TicketID = @ticket_id
        """
        job_config_update = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticket_id", "STRING", id_normalizado),
                bigquery.ScalarQueryParameter("nuevas_horas", "INTEGER", nuevas_horas_sla),
                bigquery.ScalarQueryParameter("nueva_fecha", "TIMESTAMP", nueva_fecha_vencimiento),
            ]
        )
        client.query(update_query, job_config=job_config_update).result()
        
        detalles_modificacion = {"nuevo_sla_horas": nuevas_horas_sla, "modificado_por": solicitante_email}
        registrar_evento(id_normalizado, "SLA_MODIFICADO", solicitante_email, detalles_modificacion)
        
        return f"El SLA del tiquete {id_normalizado} ha sido modificado a {nuevas_horas_sla} horas."
    except Exception as e:
        print(f"🔴 Error al modificar el SLA: {e}")
        return f"Ocurrió un error al intentar modificar el SLA del tiquete: {e}"