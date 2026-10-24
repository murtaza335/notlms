# PyInstaller spec: one self-contained executable named "notlms".
# Build from the repo root:  pyinstaller packaging/notlms.spec
import os

ROOT = os.path.abspath(os.path.join(SPECPATH, ".."))

a = Analysis(
    [os.path.join(SPECPATH, "entry.py")],
    pathex=[ROOT],
    datas=[(os.path.join(ROOT, "notlms", "ui", "index.html"), "notlms/ui")],
    excludes=["tkinter", "unittest", "pydoc"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="notlms",
    console=True,  # keeps the launch link visible and gives a way to quit (Ctrl+C / close window)
    upx=False,
)
