"""
Desktop entry point.

Packaged with PyInstaller this becomes a single .exe: it starts the API on a
free local port, serves the built frontend from the same process, and opens the
user's browser at it. No Python, no Node, no Docker - double-click and it runs.

Data lives in the OS's normal per-user location (%LOCALAPPDATA% on Windows)
rather than next to the executable, so it survives replacing the .exe with a
newer one and works from a read-only folder.
"""
import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path


def data_dir() -> Path:
    """Where the database and downloaded artwork live."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))
    directory = base / "PlayNext"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def bundle_dir() -> Path:
    """Where the bundled files are. PyInstaller unpacks them to a temp dir."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[1]))


def free_port() -> int:
    """Ask the OS for an unused port rather than guessing one that might be busy."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def configure(port: int) -> None:
    """
    Settings are read from the environment, so the desktop build configures
    itself by setting them before the app is imported.
    """
    directory = data_dir()
    os.environ.setdefault("DATABASE_URL", f"sqlite:///{directory / 'playnext.db'}")
    os.environ.setdefault("MEDIA_DIR", str(directory / "media"))
    os.environ.setdefault("PUBLIC_API_URL", f"http://127.0.0.1:{port}")
    os.environ.setdefault("FRONTEND_URL", f"http://127.0.0.1:{port}")
    os.environ.setdefault("CORS_ORIGINS", f"http://127.0.0.1:{port},http://localhost:{port}")

    # a local install still deserves a real secret, generated once and kept
    secret_file = directory / "secret.key"
    if not secret_file.exists():
        import secrets

        secret_file.write_text(secrets.token_urlsafe(48))
    os.environ.setdefault("SECRET_KEY", secret_file.read_text().strip())


def main() -> None:
    port = free_port()
    configure(port)

    # imported after configure(), so the settings above are picked up
    import uvicorn

    from .main import app, prepare_database
    from .static_site import mount_frontend

    prepare_database()
    mount_frontend(app, bundle_dir() / "static")

    url = f"http://127.0.0.1:{port}"
    print(f"PlayNext is running at {url}")
    print("Close this window to quit.")

    # give the server a moment to bind before the browser asks for the page
    threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()

    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")


if __name__ == "__main__":
    main()
