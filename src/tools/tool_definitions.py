
from vertexai.generative_models import Tool, FunctionDeclaration

crear_tiquete_declaration = FunctionDeclaration(
    name="crear_tiquete_helpdesk",
    description="Útil para crear un nuevo tiquete de soporte cuando un usuario reporta un problema.",
    parameters={"type": "object", "properties": {"descripcion": {"type": "string"}, "solicitante": {"type": "string"}, "equipo_asignado": {"type": "string"}, "prioridad": {"type": "string"}}, "required": ["descripcion", "solicitante", "equipo_asignado", "prioridad"]}
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

# Agrupamos todas las declaraciones en una sola configuración de herramientas
all_tools_config = Tool(function_declarations=[
    crear_tiquete_declaration,
    consultar_estado_declaration,
    cerrar_tiquete_declaration,
    reasignar_tiquete_declaration,
    modificar_sla_declaration,
    visualizar_flujo_declaration,
    consultar_metricas_declaration
])
