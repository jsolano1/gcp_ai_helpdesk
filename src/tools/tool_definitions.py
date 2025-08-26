
from vertexai.generative_models import Tool, FunctionDeclaration

crear_tiquete_declaration = FunctionDeclaration(
    name="crear_tiquete_helpdesk",
    description="Útil para crear un nuevo tiquete de soporte cuando un usuario reporta un problema.",
    parameters={
        "type": "object",
        "properties": {
            "descripcion": {"type": "string"},
            "solicitante": {"type": "string", "description": "El correo electrónico del usuario. El sistema lo provee."},
            "nombre_solicitante": {"type": "string", "description": "El nombre del usuario. El sistema lo provee."},
            "equipo_asignado": {"type": "string"},
            "prioridad": {"type": "string"}
        },
        "required": ["descripcion", "equipo_asignado", "prioridad"]
    }
)

consultar_estado_declaration = FunctionDeclaration(
    name="consultar_estado_tiquete",
    description="Útil para verificar el estado actual de un tiquete existente usando su ID.",
    parameters={"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}
)

cerrar_tiquete_declaration = FunctionDeclaration(
    name="cerrar_tiquete",
    description="Cierra un tiquete de soporte que ya ha sido resuelto.",
    parameters={"type": "object", "properties": {"ticket_id": {"type": "string"}, "resolucion": {"type": "string"}}, "required": ["ticket_id", "resolucion"]}
)

reasignar_tiquete_declaration = FunctionDeclaration(
    name="reasignar_tiquete",
    description="Reasigna un tiquete existente a un nuevo responsable.",
    parameters={"type": "object", "properties": {"ticket_id": {"type": "string"}, "nuevo_responsable_email": {"type": "string"}}, "required": ["ticket_id", "nuevo_responsable_email"]}
)

modificar_sla_declaration = FunctionDeclaration(
    name="modificar_sla_manual",
    description="Modifica o cambia el SLA de un tiquete existente a un número específico de horas.",
    parameters={"type": "object", "properties": {"ticket_id": {"type": "string"}, "nuevas_horas_sla": {"type": "integer"}}, "required": ["ticket_id", "nuevas_horas_sla"]}
)

visualizar_flujo_declaration = FunctionDeclaration(
    name="visualizar_flujo_tiquete",
    description="Muestra el historial completo de un tiquete como una infografía visual.",
    parameters={"type": "object", "properties": {"ticket_id": {"type": "string"}}, "required": ["ticket_id"]}
)

consultar_metricas_declaration = FunctionDeclaration(
    name="consultar_metricas",
    description="Útil para responder preguntas sobre métricas y estadísticas del sistema de tiquetes.",
    parameters={"type": "object", "properties": {"pregunta_del_usuario": {"type": "string"}}, "required": ["pregunta_del_usuario"]}
)

convertir_a_tarea_declaration = FunctionDeclaration(
    name="convertir_incidencia_a_tarea",
    description="Útil cuando una incidencia reportada no es un error sino una solicitud de nueva funcionalidad o una tarea planificable. La convierte en una tarea en Asana.",
    parameters={
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"},
            "motivo": {"type": "string", "description": "La razón por la cual se está convirtiendo a tarea."},
            "fecha_entrega": {"type": "string", "description": "La fecha de entrega acordada en formato YYYY-MM-DD."}
        },
        "required": ["ticket_id", "motivo", "fecha_entrega"]
    }
)

agendar_reunion_declaration = FunctionDeclaration(
    name="agendar_reunion_gcalendar",
    description="Genera un enlace de Google Calendar para agendar una reunión de seguimiento. Obtiene automáticamente al solicitante y responsable, y puede incluir invitados adicionales.",
    parameters={
        "type": "object",
        "properties": {
            "ticket_id": {"type": "string"},
            "email_invitados_adicionales": {
                "type": "array",
                "description": "Una lista opcional de correos electrónicos de otras personas a invitar.",
                "items": {"type": "string"}
            }
        },
        "required": ["ticket_id"]
    }
)

all_tools_config = Tool(function_declarations=[
    crear_tiquete_declaration,
    consultar_estado_declaration,
    cerrar_tiquete_declaration,
    reasignar_tiquete_declaration,
    modificar_sla_declaration,
    visualizar_flujo_declaration,
    consultar_metricas_declaration,
    convertir_a_tarea_declaration,
    agendar_reunion_declaration
])