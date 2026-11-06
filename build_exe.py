"""Script to package CodeCafe Signals as a standalone Windows executable (.exe).
Run: uv run python build_exe.py
"""
import subprocess
import sys

def build():
    print("Installing PyInstaller if needed...")
    subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir",
        "--name", "CodeCafeSignalsPlatform",
        "--add-data", "web;web",
        "--add-data", "models;models",
        "--hidden-import", "uvicorn.logging",
        "--hidden-import", "uvicorn.loops",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols",
        "--hidden-import", "uvicorn.protocols.http",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        "--hidden-import", "uvicorn.lifespans",
        "--hidden-import", "uvicorn.lifespans.on",
        "dashboard_server.py"
    ]
    print("Building standalone executable package...")
    subprocess.run(cmd, check=True)
    print("Build complete! Output folder: dist/CodeCafeSignalsPlatform/CodeCafeSignalsPlatform.exe")

if __name__ == "__main__":
    build()

