from datetime import datetime, timedelta
from google.cloud import bigquery
from src.utils.bigquery_client import client, registrar_evento, TICKETS_TABLE_ID, validar_tiquete
from src.config import DATA_ENGINEERING_LEAD, BI_ANALYST_LEAD
from src.services.notification_service import enviar_notificacion_email, enviar_notificacion_chat

def crear_tiquete(descripcion: str, solicitante: str, nombre_solicitante: str, equipo_asignado: str, prioridad: str) -> str: [cite: 1]
    """Crea un nuevo tiquete, calcula su SLA y envía notificaciones personalizadas.""" [cite: 1]
    try:
        sla_map = {"alta": 8, "media": 24, "baja": 72} [cite: 1]
        prioridad_limpia = prioridad.lower() [cite: 1]
        if "alta" in prioridad_limpia: sla_horas = sla_map["alta"] [cite: 1]
        elif "baja" in prioridad_limpia: sla_horas = sla_map["baja"] [cite: 1]
        else: sla_horas = sla_map["media"] [cite: 1]
        
        fecha_creacion = datetime.utcnow() [cite: 1]
        fecha_vencimiento = fecha_creacion + timedelta(hours=sla_horas) [cite: 1]
        count_query_job = client.query(f"SELECT COUNT(*) as count FROM `{TICKETS_TABLE_ID}`") [cite: 1]
        row_count = next(count_query_job.result()).count [cite: 1]
        ticket_id = f"DEX-{row_count + 1}" [cite: 1]
        responsable = DATA_ENGINEERING_LEAD if equipo_asignado == "Data Engineering" else BI_ANALYST_LEAD [cite: 1]
        
        insert_ticket_query = f"""
            INSERT INTO `{TICKETS_TABLE_ID}` (TicketID, Solicitante, FechaCreacion, SLA_Horas, FechaVencimiento)
            VALUES (@ticket_id, @solicitante, @fecha_creacion, @sla_horas, @fecha_vencimiento)
        """ [cite: 1]
        job_config_ticket = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticket_id", "STRING", ticket_id),
                bigquery.ScalarQueryParameter("solicitante", "STRING", solicitante),
                bigquery.ScalarQueryParameter("fecha_creacion", "TIMESTAMP", fecha_creacion),
                bigquery.ScalarQueryParameter("sla_horas", "INTEGER", sla_horas),
                bigquery.ScalarQueryParameter("fecha_vencimiento", "TIMESTAMP", fecha_vencimiento),
            ]
        ) [cite: 1]
        client.query(insert_ticket_query, job_config=job_config_ticket).result() [cite: 1]
        
        detalles_creacion = {"descripcion": descripcion, "equipo_asignado": equipo_asignado, "responsable_inicial": responsable, "prioridad_asignada": prioridad, "sla_calculado_horas": sla_horas} [cite: 1]
        registrar_evento(ticket_id, "CREADO", solicitante, detalles_creacion) [cite: 1]
        
        primer_nombre = nombre_solicitante.split(" ")[0]

        asunto_solicitante = f"✅ Tiquete Creado Exitosamente: {ticket_id}" [cite: 1]
        cuerpo_solicitante = f"""
        <html>
        <body>
            <h2>Hola, {primer_nombre},</h2>
            <p>Hemos recibido tu solicitud y hemos creado el tiquete <b>{ticket_id}</b>.</p>
            <p><b>Descripción:</b> {descripcion}</p>
            <p>Ha sido asignado a: <b>{responsable}</b>.</p>
            <p>Recibirás más notificaciones sobre su progreso.</p>
            <p>Gracias,<br>Dex Helpdesk AI</p>
        </body>
        </html>
        """ [cite: 1]
        enviar_notificacion_email(solicitante, asunto_solicitante, cuerpo_solicitante) [cite: 1]

        asunto_responsable = f"⚠️ Nuevo Tiquete Asignado: {ticket_id}" [cite: 1]
        cuerpo_responsable = f"""
        <html>
        <body>
            <h2>Hola,</h2>
            <p>Se te ha asignado un nuevo tiquete de soporte: <b>{ticket_id}</b>.</p>
            <p><b>Solicitante:</b> {nombre_solicitante} ({solicitante})</p>
            <p><b>Descripción:</b> {descripcion}</p>
            <p><b>Prioridad:</b> {prioridad}</p>
        </body>
        </html>
        """ [cite: 1]
        enviar_notificacion_email(responsable, asunto_responsable, cuerpo_responsable) [cite: 1]
        
        mensaje_chat_creacion = f"✅ Nuevo Tiquete Creado: *{ticket_id}*\n*Solicitante:* {nombre_solicitante}\n*Asignado a:* {responsable}\n*Descripción:* {descripcion}" [cite: 1]
        enviar_notificacion_chat(mensaje_chat_creacion) [cite: 1]

        return f"Tiquete {ticket_id} creado con prioridad '{prioridad}' y un SLA de {sla_horas} horas. Asignado a {responsable}. Se han enviado las notificaciones." [cite: 1]
    except Exception as e:
        print(f"🔴 Error al crear tiquete: {e}") [cite: 1]
        return f"Ocurrió un error al crear el tiquete: {e}" [cite: 1]

def cerrar_tiquete(ticket_id: str, resolucion: str) -> str: [cite: 1]
    ticket_id = ticket_id.upper() [cite: 1]
    id_normalizado, existe = validar_tiquete(ticket_id) [cite: 1]
    if not existe: [cite: 1]
        return f"Error: El tiquete '{id_normalizado}' no fue encontrado." [cite: 1]
    
    try:
        detalles_cierre = {"resolucion": resolucion} [cite: 1]
        registrar_evento(id_normalizado, "CERRADO", "Dex", detalles_cierre) [cite: 1]
        mensaje_chat_cierre = f"✔️ Tiquete Cerrado: *{ticket_id}*\n*Resolución:* {resolucion}" [cite: 1]
        enviar_notificacion_chat(mensaje_chat_cierre) [cite: 1]
        return f"El tiquete {id_normalizado} ha sido marcado como cerrado." [cite: 1]
    except Exception as e:
        print(f"🔴 Error al cerrar tiquete: {e}") [cite: 1]
        return f"Ocurrió un error al cerrar el tiquete: {e}" [cite: 1]

def reasignar_tiquete(ticket_id: str, nuevo_responsable_email: str) -> str: [cite: 1]
    ticket_id = ticket_id.upper() [cite: 1]
    id_normalizado, existe = validar_tiquete(ticket_id) [cite: 1]
    if not existe: [cite: 1]
        return f"Error: El tiquete '{id_normalizado}' no fue encontrado." [cite: 1]

    try:
        current_status = consultar_estado_tiquete(id_normalizado) [cite: 1]
        detalles_reasignacion = {"nuevo_responsable": nuevo_responsable_email, "estado_anterior": current_status} [cite: 1]
        registrar_evento(id_normalizado, "REASIGNADO", "Dex", detalles_reasignacion) [cite: 1]
        mensaje_chat_reasignacion = f"👤 Tiquete Reasignado: *{id_normalizado}*\n*Nuevo Responsable:* {nuevo_responsable_email}" [cite: 1]
        enviar_notificacion_chat(mensaje_chat_reasignacion) [cite: 1]
        return f"El tiquete {id_normalizado} ha sido reasignado a {nuevo_responsable_email}." [cite: 1]
    except Exception as e:
        print(f"🔴 Error al reasignar tiquete: {e}") [cite: 1]
        return f"Ocurrió un error al reasignar el tiquete: {e}" [cite: 1]

def modificar_sla_manual(ticket_id: str, nuevas_horas_sla: int) -> str: [cite: 1]
    ticket_id = ticket_id.upper() [cite: 1]
    id_normalizado, existe = validar_tiquete(ticket_id) [cite: 1]
    if not existe: [cite: 1]
        return f"Error: El tiquete '{id_normalizado}' no fue encontrado." [cite: 1]

    try:
        query_fecha = f"SELECT FechaCreacion FROM `{TICKETS_TABLE_ID}` WHERE TicketID = @ticket_id" [cite: 1]
        job_config_fecha = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("ticket_id", "STRING", id_normalizado)]) [cite: 1]
        results = list(client.query(query_fecha, job_config=job_config_fecha).result()) [cite: 1]
        fecha_creacion = results[0].FechaCreacion [cite: 1]
        nueva_fecha_vencimiento = fecha_creacion + timedelta(hours=nuevas_horas_sla) [cite: 1]
        update_query = f"""
            UPDATE `{TICKETS_TABLE_ID}`
            SET SLA_Horas = @nuevas_horas, FechaVencimiento = @nueva_fecha
            WHERE TicketID = @ticket_id
        """ [cite: 1]
        job_config_update = bigquery.QueryJobConfig(
            query_parameters=[
                bigquery.ScalarQueryParameter("ticket_id", "STRING", id_normalizado),
                bigquery.ScalarQueryParameter("nuevas_horas", "INTEGER", nuevas_horas_sla),
                bigquery.ScalarQueryParameter("nueva_fecha", "TIMESTAMP", nueva_fecha_vencimiento),
            ]
        ) [cite: 1]
        client.query(update_query, job_config=job_config_update).result() [cite: 1]
        detalles_modificacion = {"nuevo_sla_horas": nuevas_horas_sla} [cite: 1]
        registrar_evento(id_normalizado, "SLA_MODIFICADO", "Dex", detalles_modificacion) [cite: 1]
        return f"El SLA del tiquete {id_normalizado} ha sido modificado a {nuevas_horas_sla} horas." [cite: 1]
    except Exception as e:
        print(f"🔴 Error al modificar el SLA: {e}") [cite: 1]
        return f"Ocurrió un error al intentar modificar el SLA del tiquete: {e}" [cite: 1]