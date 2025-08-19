import os
from dotenv import load_dotenv

load_dotenv()

GCP_PROJECT_ID = "connectdataai"
LOCATION = "us-central1"

# --- CONFIGURACIÓN DE BIGQUERY ---
BIGQUERY_DATASET_ID = "helpdesk_dex"
TICKETS_TABLE_NAME = "tickets"
EVENTOS_TABLE_NAME = "eventos_tiquetes"

# --- CONFIGURACIÓN DEL HELPDESK (ASIGNACIÓN DE RESPONSABLES) ---
DATA_ENGINEERING_LEAD = "jose.solano@connect.inc"
BI_ANALYST_LEAD = "ivan.galindo@connect.inc"
