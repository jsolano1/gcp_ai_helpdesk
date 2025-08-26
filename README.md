# ​ ConnectAI: Plataforma Multi-Agente de Soporte Corporativo

<div align="center">
Una plataforma de **IA para soporte interno** , diseñada para automatizar procesos y elevar la eficiencia operativa.
</div>

---

##  Índice
- [Visión de Negocio](#visión-de-negocio)  
- [Alcance y Funcionalidades](#alcance-y-funcionalidades)  
- [Visión Técnica](#visión-técnica)  
- [Metodología y Gobierno del Código](#metodología-y-gobierno-del-código)  
- [Estructura del Proyecto](#estructura-del-proyecto)  
- [Instalación y Despliegue](#instalación-y-despliegue)  
- [Uso y Ejemplos](#uso-y-ejemplos)  
- [Créditos](#créditos)

---

## Visión de Negocio

###  El Problema
- Mejorsas Soporte: preguntas repetidas y tickets manuales.  
- Comunicación fragmentada: correos y mensajes dificultan la coordinación.  
- Costos elevados y pérdida de foco en tareas estratégicas.

###  La Solución: Agentes Autónomos
- **Bladi**, el agente inicial, centraliza el soporte.  
- Futuros agentes especializados: Finanzas, RRHH, Ventas, Reporting.  
- Todos orquestados por un agente maestro.

###  Propuesta de Valor
| Beneficio               | Impacto Clave |
|-------------------------|----------------|
| Reducción de Costos     | Automatiza hasta el **80 %** del soporte Nivel 0 y 1 |
| Eficiencia Operativa    | Desvía a los equipos hacia tareas estratégicas |
| Experiencia del Empleado| Respuestas inmediatas y sin fricciones |
| Escalabilidad           | Agentes adicionales sin reescritura del sistema |

---

## Alcance y Funcionalidades

- **Interfaz**: Conversacional, dentro de Google Chat.  
- **Auto-servicio N0**: Búsqueda semántica con Vertex AI Vector Search.  
- **Gestión de Tiquetes**:
  - Razonamiento de prioridad y enrutamiento con **Gemini 2.5-flash**.  
  - SLAs dinámicos mediante **BigQuery**.  
- **Integraciones**:
  - **Asana**: convierte tiquetes en tareas ya planificadas.  
  - **Google Calendar**: agenda reuniones automáticas.  
- **Multimodalidad**: infografías de flujo generadas automáticamente.  
- **Notificaciones**: chat + email, además de resúmenes diarios (admin y usuario).

---

## Visión Técnica

- **Compute**: Backend Flask en **Cloud Run**.  
- **Base de datos**: historial y configuración en **BigQuery**.  
- **Capa de IA**:
  - Modelos: *Gemini 2.5-flash* (razonamiento), *text-embedding-005* para embeddings.  
  - Vector Search para conocimiento; generación de imágenes para visuales.  
- **Almacenamiento**: artefactos en **Cloud Storage**.  
- **Scheduler**: disparo de tareas con **Cloud Scheduler**.  
- **Memoria conversacional**: almacenada en **Firestore**.

---

## Metodología y Gobierno del Código

- **Metodología Agile (Scrum)**:
  - Sprints de 2 semanas, con daily, planning, revisión y demo.  
  - Backlog gestionado en Asana o Jira.

- **Git Flow**:
  - `main`: producción.  
  - `develop`: integración continua.  
  - `feature/<name>`: nuevas funcionalidades.  
  - `hotfix/<name>`: correcciones urgentes.

- **Estilo de Código**:
  - Python 3.12, con formateo automatizado (`black`, `isort`) y lint (`flake8`).  
  - Nomenclatura:
    - `snake_case` para funciones/variables  
    - `PascalCase` para clases  
    - `UPPER_SNAKE_CASE` para constantes

---

## Estructura del Proyecto

``` bash
gcp_ai_helpdesk/
├── .gitignore
├── Dockerfile
├── README.md
├── main.py
├── requirements.txt
└── src/
    ├── config.py
    ├── logic.py
    ├── services/
    ├── tasks/
    ├── tools/
└── utils/
```


- **services/**: lógica externa (Asana, KB, notificaciones).  
- **tasks/**: scripts para resúmenes programados.  
- **tools/**: herramientas disponibles para el modelo IA.  
- **utils/**: utilidades reutilizables (p. ej. cliente BigQuery).

---

## Instalación y Despliegue

1. Clona el repositorio:
   ```bash
   git clone https://github.com/jsolano1/gcp_ai_helpdesk.git
   cd gcp_ai_helpdesk
   ````
2. Configura variables de entorno local en .env:

``` env
GEMINI_CHAT_MODEL="gemini-2.5-flash"
GEMINI_TASK_MODEL="gemini-2.5-PRO"
IMAGEN_MODEL="imagen-4.0-generate-001"
EMBEDDING_MODEL_NAME="text-embedding-005"
GOOGLE_CHAT_WEBHOOK_URL="https://chat.googleapis.com/....."
GCS_BUCKET_NAME="dex-helpdesk-flujos"
BREVO_API_KEY="xsmtpsib-......"
ASANA_PERSONAL_ACCESS_TOKEN="2/12086949524531......."
ASANA_PROJECT_GID="1204402129492806"
ASANA_LEAD_DATA_ENGINEERING_GID="1200014366404278"
#ASANA_LEAD_TI_GID="1205224117672129"
ASANA_LEAD_BI_ANALYST_GID="1205224117672129"
```

3. Despliega usando Cloud Run:

```bash
githubActions
```

## Uso y Ejemplos

### Interactúa con Bladi en Google Chat:

**Base de Conocimiento:**
“¿Cómo puedo solicitar acceso a los dashboards de Looker?”

**Crear Tiquete:**
“Hola, tengo un problema con el pipeline de ventas.”

**Consultar estado:**
“¿Cuál es el estado del tiquete DEX-20250826-1FA8?”

**Convertir a Tarea:**
“El tiquete DEX-123 es una nueva funcionalidad. Conviértelo a tarea.”

**Agendar Reunión:**
“Sí, por favor, agenda la reunión con hola.test@connect.inc”

**Visualizar Historial:**
“Muéstrame el flujo completo del tiquete DEX-20250826-1FA8.”
