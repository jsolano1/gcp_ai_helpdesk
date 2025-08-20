
import os
import base64
import json
import requests
from email.mime.text import MIMEText
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv()
GOOGLE_CHAT_WEBHOOK_URL = os.getenv("GOOGLE_CHAT_WEBHOOK_URL")

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/chat.messages"
]

def get_authenticated_service():
    """Autentica al usuario y devuelve un objeto de servicio de Gmail."""
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    
    try:
        service = build("gmail", "v1", credentials=creds)
        return service
    except HttpError as error:
        print(f"Ocurrió un error al construir el servicio de Gmail: {error}")
        return None

def enviar_notificacion_email(destinatario: str, asunto: str, cuerpo_html: str):
    """
    Crea y envía un correo electrónico usando la API de Gmail.
    """
    try:
        service = get_authenticated_service()
        message = MIMEText(cuerpo_html, 'html')
        message["To"] = destinatario
        message["From"] = "me" 
        message["Subject"] = asunto

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {"raw": encoded_message}

        send_message = service.users().messages().send(userId="me", body=create_message).execute()
        print(f"✅ Correo de notificación enviado a {destinatario}. Message ID: {send_message['id']}")
        return True
    except HttpError as error:
        print(f"🔴 Error al enviar el correo: {error}")
        return False
    except Exception as e:
        print(f"🔴 Error inesperado en el envío de correo: {e}")
        return False

def enviar_notificacion_chat(mensaje: str):
    """
    Envía un mensaje simple a un espacio de Google Chat usando un webhook.
    """
    if not GOOGLE_CHAT_WEBHOOK_URL:
        print("⚠️  Advertencia: No se ha configurado la URL del webhook de Google Chat en el archivo .env")
        return False
        
    try:
        mensaje_json = {"text": mensaje}
        headers = {'Content-Type': 'application/json; charset=UTF-8'}
        
        response = requests.post(GOOGLE_CHAT_WEBHOOK_URL, headers=headers, data=json.dumps(mensaje_json))
        
        if response.status_code == 200:
            print(f"✅ Notificación enviada a Google Chat.")
            return True
        else:
            print(f"🔴 Error al enviar notificación a Google Chat. Estado: {response.status_code}, Respuesta: {response.text}")
            return False

    except Exception as e:
        print(f"🔴 Error inesperado en el envío de mensaje de Chat: {e}")
        return False