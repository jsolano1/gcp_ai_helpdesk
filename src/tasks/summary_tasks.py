from datetime import datetime, timezone
from collections import defaultdict
from src.services.notification_service import enviar_notificacion_email, enviar_notificacion_chat
from src.utils.bigquery_client import client, TICKETS_TABLE_ID, EVENTOS_TABLE_ID

def get_open_tickets_summary():
    """
    Consulta BigQuery para obtener todos los tiquetes abiertos y los agrupa por solicitante.
    """
    query = f"""
    WITH UltimosEventos AS (
        SELECT
            TicketID,
            TipoEvento,
            ROW_NUMBER() OVER(PARTITION BY TicketID ORDER BY FechaEvento DESC) as rn
        FROM `{EVENTOS_TABLE_ID}`
    )
    SELECT
        t.TicketID,
        t.Solicitante,
        t.FechaVencimiento
    FROM `{TICKETS_TABLE_ID}` t
    LEFT JOIN UltimosEventos ue ON t.TicketID = ue.TicketID
    WHERE ue.rn = 1 AND ue.TipoEvento != 'CERRADO'
    """
    try:
        results = client.query(query).result()
        user_tickets = defaultdict(list)
        for row in results:
            user_tickets[row.Solicitante].append({
                "ticket_id": row.TicketID,
                "due_date": row.FechaVencimiento
            })
        return user_tickets
    except Exception as e:
        print(f"🔴 Error al obtener tiquetes abiertos: {e}")
        return None

def format_time_remaining(due_date):
    """
    Calcula y formatea el tiempo restante hasta la fecha de vencimiento.
    """
    now = datetime.now(timezone.utc)
    remaining = due_date - now
    
    if remaining.total_seconds() <= 0:
        return "Vencido"
    
    days = remaining.days
    hours, remainder = divmod(remaining.seconds, 3600)
    minutes, _ = divmod(remainder, 60)
    
    return f"{days}d {hours}h {minutes}m"

def format_chat_summary(tickets):
    """
    Formatea el resumen de tiquetes para un mensaje de texto plano en Google Chat.
    """
    message = "*Tu Resumen Diario de Tiquetes Abiertos*\n\n"
    for ticket in tickets:
        time_left = format_time_remaining(ticket['due_date'])
        message += f"• *{ticket['ticket_id']}:* Tiempo restante: {time_left}\n"
    return message

def send_daily_summaries():
    """
    Función principal para generar y enviar resúmenes diarios por correo y Google Chat.
    """
    print("🚀 Iniciando el envío de resúmenes diarios de tiquetes abiertos...")
    user_tickets = get_open_tickets_summary()
    
    if not user_tickets:
        print("✅ No hay tiquetes abiertos para notificar. Finalizando.")
        return

    for user_email, tickets in user_tickets.items():
        # --- 1. Enviar Correo Electrónico ---
        html_body = "<html><body>"
        html_body += "<h2>Hola,</h2>"
        html_body += "<p>Este es tu resumen diario de tiquetes de soporte abiertos:</p>"
        html_body += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;'>"
        html_body += "<tr style='background-color:#f2f2f2;'><th>ID del Tiquete</th><th>Tiempo Restante</th></tr>"
        
        for ticket in tickets:
            time_left_email = format_time_remaining(ticket['due_date']).replace("Vencido", "<span style='color:red;'>Vencido</span>")
            html_body += f"<tr><td>{ticket['ticket_id']}</td><td style='text-align:center;'>{time_left_email}</td></tr>"
            
        html_body += "</table><p>Gracias,<br>Dex Helpdesk AI</p></body></html>"
        asunto = "📄 Tu Resumen Diario de Tiquetes Abiertos"
        
        print(f"✉️  Enviando resumen por email a {user_email}...")
        enviar_notificacion_email(user_email, asunto, html_body)
        
        # --- 2. Enviar Mensaje por Google Chat ---
        chat_message = format_chat_summary(tickets)
        message_to_channel = f"Resumen para *{user_email}*:\n{chat_message}"
        
        print(f"💬 Enviando resumen por Google Chat al canal...")
        enviar_notificacion_chat(message_to_channel)

    print("✅ Proceso de resúmenes diarios finalizado.")