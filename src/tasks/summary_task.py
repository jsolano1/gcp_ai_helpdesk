from datetime import datetime, timezone
from collections import defaultdict
from src.services.notification_service import enviar_notificacion_email, enviar_notificacion_chat
from src.utils.bigquery_client import client, TICKETS_TABLE_ID, EVENTOS_TABLE_ID

def get_open_tickets_summary():
    """
    Consulta BigQuery para obtener todos los tiquetes abiertos, incluyendo su responsable actual,
    y filtrando aquellos sin fecha de vencimiento.
    """
    query = f"""
    WITH UltimosEventosConResponsable AS (
        SELECT
            TicketID,
            -- Coalesce para encontrar el último responsable asignado
            COALESCE(
                JSON_EXTRACT_SCALAR(Detalles, '$.nuevo_responsable'),
                JSON_EXTRACT_SCALAR(Detalles, '$.responsable_inicial')
            ) as Responsable,
            TipoEvento,
            ROW_NUMBER() OVER(PARTITION BY TicketID ORDER BY FechaEvento DESC) as rn
        FROM `{EVENTOS_TABLE_ID}`
    )
    SELECT
        t.TicketID,
        t.Solicitante,
        t.FechaVencimiento,
        ue.Responsable
    FROM `{TICKETS_TABLE_ID}` t
    JOIN UltimosEventosConResponsable ue ON t.TicketID = ue.TicketID
    WHERE 
        ue.rn = 1 
        AND ue.TipoEvento != 'CERRADO'
        AND t.FechaVencimiento IS NOT NULL -- CORRECCIÓN: Evita el error con tiquetes sin fecha
    """
    try:
        results = client.query(query).result()
        all_tickets = []
        user_tickets = defaultdict(list)
        
        for row in results:
            ticket_data = {
                "ticket_id": row.TicketID,
                "due_date": row.FechaVencimiento,
                "assignee": row.Responsable or "No asignado"
            }
            # Agrega el solicitante a la lista general para el resumen de admin
            ticket_data_admin = ticket_data.copy()
            ticket_data_admin['solicitante'] = row.Solicitante
            all_tickets.append(ticket_data_admin)
            
            user_tickets[row.Solicitante].append(ticket_data)
            
        return all_tickets, user_tickets
    except Exception as e:
        print(f"🔴 Error al obtener tiquetes abiertos: {e}")
        return None, None

def format_time_remaining(due_date):
    """
    Calcula y formatea el tiempo restante hasta la fecha de vencimiento.
    """
    if not due_date:
        return "Fecha no definida"
        
    now = datetime.now(timezone.utc)
    remaining = due_date - now
    
    if remaining.total_seconds() <= 0:
        return "Vencido"
    
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    if days > 0:
        return f"{days}d {hours}h"
    else:
        return f"{hours}h {minutes}m"

def send_daily_summaries():
    """
    Genera un resumen para administradores (Chat) y envía notificaciones privadas a usuarios (Email).
    """
    print("🚀 Iniciando el envío de resúmenes diarios de tiquetes abiertos...")
    all_tickets, user_tickets = get_open_tickets_summary()
    
    if all_tickets is None:
        print("🔴 Finalizando la tarea debido a un error al consultar la base de datos.")
        return

    if not all_tickets:
        admin_summary = "✅ ¡Buen día! No hay tiquetes abiertos pendientes hoy."
        print(admin_summary)
        enviar_notificacion_chat(admin_summary)
        return

    # --- 1. Resumen único para el canal de Administradores por Google Chat ---
    admin_summary = "*Resumen Diario General de Tiquetes Abiertos*\n\n"
    for ticket in all_tickets:
        time_left = format_time_remaining(ticket['due_date'])
        admin_summary += f"• *{ticket['ticket_id']}* | Solicitante: {ticket['solicitante']} | Asignado a: *{ticket['assignee']}* | Vence en: {time_left}\n"
    
    print("📢 Enviando resumen de administrador al canal principal...")
    enviar_notificacion_chat(admin_summary)

    # --- 2. Correos privados y personales para cada usuario ---
    if not user_tickets:
        return

    for user_email, tickets in user_tickets.items():
        asunto = "📄 Tu Resumen Diario de Tiquetes Abiertos"
        html_body = "<html><body><h2>Hola,</h2><p>Este es tu resumen diario de tiquetes de soporte abiertos:</p>"
        html_body += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;'>"
        html_body += "<tr style='background-color:#f2f2f2;'><th>ID del Tiquete</th><th>Asignado a</th><th>Tiempo Restante</th></tr>"
        
        for ticket in tickets:
            time_left = format_time_remaining(ticket['due_date']).replace("Vencido", "<span style='color:red;'>Vencido</span>")
            html_body += f"<tr><td>{ticket['ticket_id']}</td><td>{ticket['assignee']}</td><td style='text-align:center;'>{time_left}</td></tr>"
        
        html_body += "</table><p>Gracias,<br>Dex Helpdesk AI</p></body></html>"
        
        print(f"✉️  Enviando resumen por email a {user_email}...")
        enviar_notificacion_email(user_email, asunto, html_body)

    print("✅ Proceso de resúmenes diarios finalizado.")