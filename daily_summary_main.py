from flask import Flask
from src.tasks.summary_task import send_daily_summaries

app = Flask(__name__)

@app.route("/", methods=["POST"])
def handle_request():
    """
    Punto de entrada para la invocación desde Cloud Scheduler.
    """
    try:
        send_daily_summaries()
        print("✅ Ejecución de resúmenes completada exitosamente.")
        return "Resúmenes enviados correctamente.", 200
    except Exception as e:
        print(f"🔴 Error crítico al ejecutar el envío de resúmenes: {e}")
        return "Error interno al procesar la solicitud.", 500

if __name__ == "__main__":
    print("▶️  Ejecutando la tarea de resúmenes manualmente para pruebas...")
    send_daily_summaries()