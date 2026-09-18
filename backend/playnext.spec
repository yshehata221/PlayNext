# PyInstaller build spec for the desktop app.
#
#   cd backend
#   pyinstaller playnext.spec
#
# Expects the built frontend to already be at backend/static (the CI workflow
# builds it first). One file, no console flag removed on purpose: the window
# shows the local URL and any errors, which is worth more than looking tidy.
from PyInstaller.utils.hooks import collect_submodules

datas = [
    ("static", "static"),           # the built frontend
    ("migrations", "migrations"),   # alembic needs its scripts at runtime
    ("alembic.ini", "."),
]

hiddenimports = (
    collect_submodules("uvicorn")
    + collect_submodules("passlib")
    + ["app.demo", "app.seed", "sqlalchemy.dialects.sqlite", "psycopg", "email_validator"]
)

a = Analysis(
    ["desktop_main.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pytest"],
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="PlayNext",
    icon="icon.ico" if __import__("os").path.exists("icon.ico") else None,
    console=True,
    upx=False,
    onefile=True,
)
