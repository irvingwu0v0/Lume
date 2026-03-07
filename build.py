"""PyInstaller build script for Lume (RinUI/PySide6) — single-folder distribution."""

import os
import sys
import shutil
import subprocess

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
ICON = os.path.join(PROJECT_DIR, "baka.ico")
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")


def clean():
    for d in [DIST_DIR, BUILD_DIR]:
        if os.path.exists(d):
            shutil.rmtree(d)
    spec = os.path.join(PROJECT_DIR, "Lume.spec")
    if os.path.exists(spec):
        os.remove(spec)
    print("[CLEAN] Removed build artifacts")


def build():
    ui_dir = os.path.join(PROJECT_DIR, "ui")
    backend_dir = os.path.join(PROJECT_DIR, "backend")
    templates_dir = os.path.join(PROJECT_DIR, "templates")
    ppt_template = os.path.join(templates_dir, "ppt_template.pptx")

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--noconfirm",
        "--name", "Lume",
        "--noconsole",
        "--clean",
        "--add-data", f"{ui_dir}{os.pathsep}ui",
        "--add-data", f"{backend_dir}{os.pathsep}backend",
        "--add-data", f"{templates_dir}{os.pathsep}templates",
        "--hidden-import", "darkdetect",
        "--hidden-import", "winreg",
        "--hidden-import", "fitz",
        "--hidden-import", "PySide6.QtWebSockets",
    ]

    if os.path.exists(ppt_template):
        cmd += ["--add-data", f"{ppt_template}{os.pathsep}templates"]

    if os.path.exists(ICON):
        cmd += ["--icon", ICON]
        cmd += ["--add-data", f"{ICON}{os.pathsep}."]

    # Entry point
    cmd.append(os.path.join(PROJECT_DIR, "main.py"))

    print(f"[BUILD] {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=PROJECT_DIR)
    if result.returncode != 0:
        print("[ERROR] Build failed")
        sys.exit(1)

    dist_app = os.path.join(DIST_DIR, "Lume")
    print(f"[DONE] App built at: {dist_app}")
    print(f"       Run: {os.path.join(dist_app, 'Lume.exe')}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
    else:
        clean()
        build()
