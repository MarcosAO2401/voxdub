import os
import webbrowser
import threading
from voxdub.api import app
import uvicorn


def _open_browser(host: str, port: int):
    # Mejor esfuerzo: abre la UI sola tras levantar el server.
    url = f"http://{host}:{port}"
    threading.Timer(2.0, lambda: webbrowser.open_new(url)).start()


if __name__ == "__main__":
    host = os.environ.get("VOXDUB_HOST", "127.0.0.1")
    port = int(os.environ.get("VOXDUB_PORT", "8000"))
    _open_browser(host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
