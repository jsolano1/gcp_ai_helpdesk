import os
from dotenv import load_dotenv

load_dotenv()

# --- Lee la configuración desde las variables de entorno ---
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID")
LOCATION = os.getenv("LOCATION")

# --- CONFIGURACIÓN DE BIGQUERY ---
BIGQUERY_DATASET_ID = "helpdesk_dex"
TICKETS_TABLE_NAME = "tickets"
EVENTOS_TABLE_NAME = "eventos_tiquetes"

# --- CONFIGURACIÓN DEL HELPDESK ---
DATA_ENGINEERING_LEAD = os.getenv("DATA_ENGINEERING_LEAD", "jose.solano@connect.inc")
BI_ANALYST_LEAD = os.getenv("BI_ANALYST_LEAD", "ivan.galindo@connect.inc")