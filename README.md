# 🤖 Agente Connect con IA

Este proyecto implementa un chatbot inteligente ("Bladi") que actúa como un agente de soporte de Nivel 0 y Nivel 1. Construido sobre Google Cloud Platform, el bot se integra con Google Chat para interactuar con los usuarios, gestiona la lógica de tiquetes en BigQuery y utiliza Vertex AI para sus capacidades de lenguaje natural y búsqueda semántica.

## ✨ Características Principales

-   **Interfaz Conversacional en Google Chat:** Los usuarios pueden crear, consultar, reasignar y cerrar tiquetes de soporte directamente desde Google Chat.
-   **Agente de Nivel 0 (Base de Conocimiento):** Antes de crear un tiquete, el bot utiliza **Vertex AI Vector Search** para buscar en una base de conocimiento y responder preguntas frecuentes de forma instantánea.
-   **Gestión Inteligente de Tiquetes:**
    -   **Análisis de Prioridad:** El bot analiza el lenguaje del usuario para asignar una prioridad (alta, media, baja).
    -   **Enrutamiento por Equipo:** Asigna automáticamente los tiquetes al equipo correcto (Data Engineering o Data Analyst / BI).
    -   **SLA Dinámico:** Consulta una tabla de configuración en BigQuery para asignar el SLA correcto basado en la prioridad y el departamento.
-   **Integración con Asana:** Permite convertir incidencias en tareas planificables en un proyecto de Asana, ideal para nuevas funcionalidades.
-   **Agendamiento de Reuniones:** Facilita la coordinación generando enlaces de Google Calendar pre-configurados para reuniones de seguimiento.
-   **Visualización de Flujos:** Genera infografías visuales del historial de un tiquete utilizando modelos de generación de imágenes de Vertex AI.
-   **Notificaciones Multicanal:** Mantiene a los usuarios informados a través de notificaciones en Google Chat y por correo electrónico.
-   **Sistema de Tareas Programadas:** Envía resúmenes diarios de tiquetes abiertos a los administradores (vista global en Chat) y a los usuarios (vista personal por email).

## 🏛️ Arquitectura en Google Cloud

El proyecto está construido 100% sobre servicios gestionados de Google Cloud para asegurar escalabilidad y bajo mantenimiento.

-   **Compute:** **Cloud Run** aloja la aplicación principal de Flask, que sirve como el backend del bot y el receptor de webhooks.
-   **Base de Datos:** **BigQuery** se utiliza como el sistema de registro principal, almacenando el historial de tiquetes, eventos, y tablas de configuración.
-   **Inteligencia Artificial:**
    -   **Vertex AI (Modelos de Lenguaje):** El modelo `gemini-2.5-flash` potencia el diálogo, el razonamiento y la capacidad de usar herramientas.
    -   **Vertex AI (Vector Search):** Proporciona la capacidad de búsqueda semántica para la base de conocimiento.
    -   **Vertex AI (Modelos de Embedding):** El modelo `text-embedding-005` convierte el texto en vectores para la base de conocimiento.
-   **Almacenamiento:** **Cloud Storage** se usa para alojar los archivos de la base de conocimiento (`.json`) y las imágenes generadas para los flujos de tiquetes.
-   **Programación:** **Cloud Scheduler** invoca un endpoint en la aplicación de Cloud Run para ejecutar tareas recurrentes, como el envío de resúmenes diarios.
-   **Interfaz:** **Google Chat API** es el canal de comunicación principal con los usuarios.


## 🚀 Cómo Desplegar

1.  **Clonar el Repositorio:**
    ```bash
    git clone [URL-DE-TU-REPO]
    cd gcp_ai_helpdesk
    ```
2.  **Configurar Variables de Entorno:**
    Crea un archivo `.env` en la raíz del proyecto y añade todas las variables necesarias (GCP_PROJECT_ID, tokens de API, IDs de Vector Search, etc.).
3.  **Construir y Desplegar en Cloud Run:**
    El proyecto está configurado para ser desplegado automáticamente a través de un trigger de Cloud Build conectado a tu repositorio de Git. Simplemente haz `push` a la rama principal para iniciar un nuevo despliegue.

## 🛠️ Cómo Usar el Bot

Una vez desplegado y configurado en un espacio de Google Chat, puedes interactuar con él usando lenguaje natural:

-   **Crear un tiquete:** "Hola, tengo un problema con un pipeline de datos que no está cargando."
-   **Consultar estado:** "¿Cuál es el estado del tiquete DEX-20250826-1FA8?"
-   **Convertir a tarea:** "El tiquete DEX-123 en realidad es una nueva funcionalidad. Conviértelo a tarea para fin de mes."
-   **Agendar reunión:** (Después de convertir a tarea) "Sí, por favor, agenda la reunión."
-   **Pregunta a la base de conocimiento:** "¿Cómo puedo acceder a los dashboards de Looker?"

---
Hecho con ❤️ y IA en Google Cloud.
