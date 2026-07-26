import subprocess
import sys
import os
import time
import signal

def run():
    root_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.join(root_dir, "scentia-backend")
    frontend_dir = os.path.join(root_dir, "scentia-frontend")

    print("🚀 Iniciando el Backend (FastAPI en http://127.0.0.1:8000)...")
    backend_process = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--reload", "--port", "8000"],
        cwd=backend_dir
    )

    time.sleep(2)  # Dar 2 segundos para que FastAPI inicie

    print("🎨 Iniciando el Frontend (Next.js en http://localhost:3000)...")
    frontend_process = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=frontend_dir
    )

    print("\n✨ ¡Proyecto SCENTIA en ejecución!")
    print(" Press Ctrl+C en esta terminal para detener ambos servicios.\n")

    try:
        backend_process.wait()
        frontend_process.wait()
    except KeyboardInterrupt:
        print("\n🛑 Deteniendo los servicios...")
        backend_process.send_signal(signal.SIGINT)
        frontend_process.send_signal(signal.SIGINT)
        backend_process.wait()
        frontend_process.wait()
        print("✅ Servicios detenidos correctamente.")

if __name__ == "__main__":
    run()