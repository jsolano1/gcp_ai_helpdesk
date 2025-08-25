from datetime import datetime, timezone, timedelta
from collections import defaultdict
from src.services.notification_service import enviar_notificacion_email, enviar_notificacion_chat
from src.utils.bigquery_client import client, TICKETS_TABLE_ID, EVENTOS_TABLE_ID

def get_open_tickets_summary():
    """
    Consulta BigQuery para obtener todos los datos necesarios para los resúmenes, 
    incluyendo solicitante, responsable, fecha de vencimiento y departamento.
    """
    query = f"""
    WITH CreacionEventos AS (
        SELECT
            TicketID,
            JSON_EXTRACT_SCALAR(Detalles, '$.equipo_asignado') as Departamento
        FROM `{EVENTOS_TABLE_ID}`
        WHERE TipoEvento = 'CREADO'
    ),
    UltimosEventosConResponsable AS (
        SELECT
            TicketID,
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
        ue.Responsable,
        ce.Departamento
    FROM `{TICKETS_TABLE_ID}` t
    JOIN UltimosEventosConResponsable ue ON t.TicketID = ue.TicketID
    JOIN CreacionEventos ce ON t.TicketID = ce.TicketID
    WHERE 
        ue.rn = 1 
        AND ue.TipoEvento != 'CERRADO'
        AND t.FechaVencimiento IS NOT NULL
    """
    try:
        results = client.query(query).result()
        all_tickets = []
        user_tickets = defaultdict(list)
        
        for row in results:
            ticket_data = {
                "ticket_id": row.TicketID,
                "solicitante": row.Solicitante,
                "due_date": row.FechaVencimiento,
                "assignee": row.Responsable or "No asignado",
                "departamento": row.Departamento or "Sin Departamento"
            }
            all_tickets.append(ticket_data)
            user_tickets[row.Solicitante].append(ticket_data)
            
        return all_tickets, user_tickets
    except Exception as e:
        print(f"🔴 Error al obtener tiquetes abiertos: {e}")
        return None, None

def format_time_remaining(due_date, is_email=False):
    """
    Calcula el tiempo restante. Si está vencido, calcula los días de vencimiento para el email.
    """
    if not due_date:
        return "Fecha no definida"
        
    now = datetime.now(timezone.utc)
    remaining = due_date - now
    
    if remaining.total_seconds() <= 0:
        if is_email:
            days_overdue = -remaining.days
            if days_overdue == 0:
                return "<span style='color:red;'>Vencido (Hoy)</span>"
            else:
                return f"<span style='color:red;'>Vencido por {days_overdue} día(s)</span>"
        else:
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
    Genera un resumen agregado para administradores (Chat) y envía notificaciones 
    detalladas y privadas a usuarios (Email).
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

    # --- 1. Generar y enviar el resumen agregado para Administradores por Google Chat ---
    stats = defaultdict(lambda: defaultdict(lambda: {'total': 0, 'due_soon': 0, 'overdue': 0}))
    now = datetime.now(timezone.utc)
    four_hours_from_now = now + timedelta(hours=4)

    for ticket in all_tickets:
        dept = ticket['departamento']
        assignee = ticket['assignee']
        due_date = ticket['due_date']
        
        stats[dept][assignee]['total'] += 1
        if due_date < now:
            stats[dept][assignee]['overdue'] += 1
        elif due_date < four_hours_from_now:
            stats[dept][assignee]['due_soon'] += 1
            
    admin_summary = "*Resumen Diario Agrupado de Tiquetes Abiertos*\n"
    for dept, assignees in sorted(stats.items()):
        admin_summary += f"\n*ᐅ Departamento: {dept}*\n"
        for assignee, data in sorted(assignees.items()):
            not_overdue = data['total'] - data['overdue']
            admin_summary += f"  • *{assignee}*:\n"
            admin_summary += f"    - Tiquetes Totales: *{data['total']}* (Sin Vencer: {not_overdue}, Vencidos: {data['overdue']})\n"
            if data['due_soon'] > 0:
                admin_summary += f"    - 🔥 Por Vencer (<4h): *{data['due_soon']}*\n"
    
    print("📢 Enviando resumen de administrador al canal principal...")
    enviar_notificacion_chat(admin_summary)

    # --- 2. Enviar correos privados y personales para cada usuario ---
    for user_email, tickets in user_tickets.items():
        asunto = "📄 Tu Resumen Diario de Tiquetes Abiertos"
        html_body = "<html><body><h2>Hola,</h2><p>Este es tu resumen diario de tiquetes de soporte abiertos:</p>"
        html_body += "<table border='1' cellpadding='5' cellspacing='0' style='border-collapse:collapse;'>"
        html_body += "<tr style='background-color:#f2f2f2;'><th>ID del Tiquete</th><th>Asignado a</th><th>Estado del SLA</th></tr>"
        
        for ticket in tickets:
            # Usamos is_email=True para obtener el nuevo formato de vencido
            time_left = format_time_remaining(ticket['due_date'], is_email=True)
            html_body += f"<tr><td>{ticket['ticket_id']}</td><td>{ticket['assignee']}</td><td style='text-align:center;'>{time_left}</td></tr>"
        
        html_body += "</table><p>Gracias,<br>Dex Helpdesk AI</p></body></html>"
        
        print(f"✉️  Enviando resumen por email a {user_email}...")
        enviar_notificacion_email(user_email, asunto, html_body)

    print("✅ Proceso de resúmenes diarios finalizado.")