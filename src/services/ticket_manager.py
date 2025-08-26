import json
import uuid
from datetime import datetime, timedelta
from google.cloud import bigquery
from src.utils.bigquery_client import (
    client, registrar_evento, TICKETS_TABLE_ID, validar_tiquete, 
    obtener_departamento_tiquete, obtener_sla_por_configuracion,
    obtener_participantes_tiquete
)
from src.config import DATA_ENGINEERING_LEAD, BI_ANALYST_LEAD
from src.services.ticket_querier import consultar_estado_tiquete
from src.services.notification_service import enviar_notificacion_email, enviar_notificacion_chat
from urllib.parse import urlencode
from src.services.asana_service import crear_tarea_asana

# ... (Las funciones crear_tiquete, cerrar_tiquete, etc., no cambian y se mantienen como están) ...
def crear_tiquete(descripcion: str, equipo_asignado: str, prioridad: str, solicitante: str, nombre_solicitante: str, **kwargs) -> str:
    """
    Crea un nuevo tiquete consultando dinámicamente el SLA desde BigQuery.
    """
    print(json.dumps({
        "log_name": "CrearTiquete_Inicio", "mensaje": "Iniciando la creación de un nuevo tiquete.",
        "parametros": {"solicitante": solicitante, "equipo_asignado": equipo_asignado, "prioridad": prioridad}
    }))
    
    try:
        sla_horas = obtener_sla_por_configuracion(equipo_asignado, prioridad)
        print(f"✅ SLA obtenido de BigQuery para {equipo_asignado}/{prioridad}: {sla_horas} horas.")
        
        fecha_creacion = datetime.utcnow()
        fecha_vencimiento = fecha_creacion + timedelta(hours=sla_horas)
        
        timestamp_id = fecha_creacion.strftime('%Y%m%d')
        unique_hash = str(uuid.uuid4().hex)[:4].upper()
        ticket_id = f"DEX-{timestamp_id}-{unique_hash}"
        
        responsable = DATA_ENGINEERING_LEAD if equipo_asignado == "Data Engineering" else BI_ANALYST_LEAD
        
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
        
        detalles_creacion = {"descripcion": descripcion, "equipo_asignado": equipo_asignado, "responsable_inicial": responsable, "prioridad_asignada": prioridad, "sla_calculado_horas": sla_horas}
        registrar_evento(ticket_id, "CREADO", solicitante, detalles_creacion)        
        
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
        print(json.dumps({"log_name": "CrearTiquete_Error", "nivel": "CRITICO", "mensaje": "Error no manejado", "error": str(e)}))
        return f"Ocurrió un error crítico al intentar crear el tiquete: {e}"


def cerrar_tiquete(ticket_id: str, resolucion: str, solicitante_email: str, solicitante_rol: str, solicitante_departamento: str, **kwargs) -> str:
    """Cierra un tiquete con validación de departamento para roles 'lead' y 'agent'."""
    id_normalizado, existe = validar_tiquete(ticket_id.upper())
    if not existe: return f"Error: El tiquete '{id_normalizado}' no fue encontrado."

    if solicitante_rol in ['lead', 'agent']:
        departamento_tiquete = obtener_departamento_tiquete(id_normalizado)
        if not departamento_tiquete:
            return f"Error: No se pudo determinar el departamento del tiquete {id_normalizado}."
        if departamento_tiquete != solicitante_departamento:
            return f"Acción denegada. Tu rol solo permite gestionar tiquetes del departamento '{solicitante_departamento}'."

    if solicitante_rol == 'agent':
        estado_actual = consultar_estado_tiquete(id_normalizado)
        if solicitante_email not in estado_actual:
             return f"Acción denegada. Como 'agent', solo puedes cerrar tiquetes asignados a ti."

    try:
        detalles_cierre = {"resolucion": resolucion, "cerrado_por": solicitante_email}
        registrar_evento(id_normalizado, "CERRADO", solicitante_email, detalles_cierre)
        enviar_notificacion_chat(f"✔️ Tiquete Cerrado: *{id_normalizado}*\n*Resolución:* {resolucion}")
        return f"El tiquete {id_normalizado} ha sido marcado como cerrado."
    except Exception as e:
        print(f"🔴 Error al cerrar tiquete: {e}")
        return f"Ocurrió un error al cerrar el tiquete: {e}"

def reasignar_tiquete(ticket_id: str, nuevo_responsable_email: str, solicitante_email: str, solicitante_rol: str, solicitante_departamento: str, **kwargs) -> str:
    """Reasigna un tiquete con validación de departamento para el rol 'lead'."""
    id_normalizado, existe = validar_tiquete(ticket_id.upper())
    if not existe: return f"Error: El tiquete '{id_normalizado}' no fue encontrado."

    if solicitante_rol == 'lead':
        departamento_tiquete = obtener_departamento_tiquete(id_normalizado)
        if not departamento_tiquete:
            return f"Error: No se pudo determinar el departamento del tiquete {id_normalizado}."
        if departamento_tiquete != solicitante_departamento:
            return f"Acción denegada. Como 'lead', solo puedes reasignar tiquetes de tu departamento ('{solicitante_departamento}')."
    
    try:
        current_status = consultar_estado_tiquete(id_normalizado)
        detalles = {"nuevo_responsable": nuevo_responsable_email, "estado_anterior": current_status, "reasignado_por": solicitante_email}
        registrar_evento(id_normalizado, "REASIGNADO", solicitante_email, detalles)
        enviar_notificacion_chat(f"👤 Tiquete Reasignado: *{id_normalizado}*\n*Nuevo Responsable:* {nuevo_responsable_email}")
        return f"El tiquete {id_normalizado} ha sido reasignado a {nuevo_responsable_email}."
    except Exception as e:
        print(f"🔴 Error al reasignar tiquete: {e}")
        return f"Ocurrió un error al reasignar el tiquete: {e}"

def modificar_sla_manual(ticket_id: str, nuevas_horas_sla: int, solicitante_email: str, solicitante_rol: str, solicitante_departamento: str, **kwargs) -> str:
    """Modifica el SLA con validación de departamento para el rol 'lead'."""
    id_normalizado, existe = validar_tiquete(ticket_id.upper())
    if not existe: return f"Error: El tiquete '{id_normalizado}' no fue encontrado."

    if solicitante_rol == 'lead':
        departamento_tiquete = obtener_departamento_tiquete(id_normalizado)
        if not departamento_tiquete:
            return f"Error: No se pudo determinar el departamento del tiquete {id_normalizado}."
        if departamento_tiquete != solicitante_departamento:
            return f"Acción denegada. Como 'lead', solo puedes modificar el SLA de tiquetes de tu departamento ('{solicitante_departamento}')."

    try:
        query_fecha = f"SELECT FechaCreacion FROM `{TICKETS_TABLE_ID}` WHERE TicketID = @ticket_id"
        job_config_fecha = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("ticket_id", "STRING", id_normalizado)])
        fecha_creacion = list(client.query(query_fecha, job_config=job_config_fecha).result())[0].FechaCreacion
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
        
        detalles = {"nuevo_sla_horas": nuevas_horas_sla, "modificado_por": solicitante_email}
        registrar_evento(id_normalizado, "SLA_MODIFICADO", solicitante_email, detalles)
        
        return f"El SLA del tiquete {id_normalizado} ha sido modificado a {nuevas_horas_sla} horas."
    except Exception as e:
        print(f"🔴 Error al modificar el SLA: {e}")
        return f"Ocurrió un error al intentar modificar el SLA del tiquete: {e}"

def convertir_incidencia_a_tarea(ticket_id: str, motivo: str, fecha_entrega: str, solicitante_email: str, **kwargs) -> str:
    """
    Convierte una incidencia existente en una tarea de Asana y lo registra en BigQuery.
    """
    id_normalizado, existe = validar_tiquete(ticket_id.upper())
    if not existe: return f"Error: El tiquete '{id_normalizado}' no fue encontrado."

    try:
        # 1. Obtener el estado actual para saber a quién está asignado
        estado_actual = consultar_estado_tiquete(id_normalizado)
        
        # Extraer el email del responsable del texto de estado
        responsable_actual = ""
        if "asignado a " in estado_actual:
            responsable_actual = estado_actual.split(" a ")[-1].strip().replace('.','')

        if not responsable_actual:
            return "Error: No se pudo determinar el responsable actual del tiquete para asignarlo en Asana."

        # 2. Crear la tarea en Asana
        nombre_tarea = f"Tarea [Desde Tiquete {id_normalizado}]"
        notas_tarea = f"Esta tarea fue convertida desde una incidencia.\n\nMotivo: {motivo}\nSolicitante: {solicitante_email}"
        
        resultado_asana = crear_tarea_asana(
            nombre_tarea=nombre_tarea,
            notas=notas_tarea,
            responsable_email=responsable_actual,
            fecha_entrega=fecha_entrega
        )

        if "error" in resultado_asana:
            return f"No se pudo crear la tarea en Asana: {resultado_asana['error']}"

        # 3. Registrar el evento en BigQuery
        detalles_conversion = {
            "motivo": motivo,
            "convertido_por": solicitante_email,
            "asana_task_info": resultado_asana
        }
        registrar_evento(id_normalizado, "CONVERTIDO_A_TAREA", solicitante_email, detalles_conversion)
        
        mensaje_chat = f"🔄 Tiquete *{id_normalizado}* convertido a Tarea en Asana.\nAsignado a: *{responsable_actual}*\nURL: {resultado_asana['asana_task_url']}"
        enviar_notificacion_chat(mensaje_chat)
        
        return f"Tiquete {id_normalizado} convertido exitosamente a una tarea en Asana. Se ha notificado al canal."

    except Exception as e:
        print(f"🔴 Error al convertir tiquete a tarea: {e}")
        return f"Ocurrió un error inesperado durante la conversión: {e}"


def agendar_reunion_gcalendar(ticket_id: str, email_invitados_adicionales: list = None, **kwargs) -> str:
    """
    Construye y devuelve un objeto JSON para una tarjeta de Google Chat con un enlace
    de Google Calendar optimizado para la vista "Find a time".
    """
    # 1. Obtener automáticamente al solicitante y responsable
    participantes = obtener_participantes_tiquete(ticket_id)
    if "error" in participantes or not participantes.get("solicitante") or not participantes.get("responsable"):
        error_msg = participantes.get("error", "No se pudo determinar al solicitante o responsable.")
        return json.dumps({"error": f"No pude encontrar a los participantes: {error_msg}"})
    
    invitados = {participantes.get("solicitante"), participantes.get("responsable")}
    if email_invitados_adicionales:
        for email in email_invitados_adicionales:
            invitados.add(email)
    invitados.discard(None)

    # 2. Configurar detalles del evento
    titulo = f"Seguimiento para Tarea ({ticket_id})"
    detalles = f"Reunión para discutir los requerimientos de la tarea generada a partir del tiquete {ticket_id}."
    
    # 3. Construir la URL inteligente SIN FECHAS para maximizar la probabilidad
    #    de que se abra en la pestaña "Find a time".
    params = {
        "action": "TEMPLATE",
        "text": titulo,
        "details": detalles,
        "add": ",".join(invitados)
    }
    base_url = "https://calendar.google.com/calendar/render?"
    url_final = base_url + urlencode(params)
    
    # 4. Devolver la estructura de la tarjeta como un JSON
    card_data = {
        "type": "calendar_link",
        "invitados": list(invitados),
        "url": url_final
    }
    return json.dumps(card_data)