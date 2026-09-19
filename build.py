"""PyInstaller build script for Lume (pure PySide6).

Produces a single-folder distribution that runs on Windows, macOS and Linux:

    python build.py          # clean + build
    python build.py clean    # remove build artifacts only

The frozen app is self-contained: the icon font and app icon in ``assets/``
and the PPT template in ``templates/`` are bundled next to the executable.
The Windows executable and the macOS ``.app`` receive the platform-native icon.
"""

import os
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, "dist")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
SPEC_FILE = os.path.join(PROJECT_DIR, "Lume.spec")
ICON_DIR = os.path.join(PROJECT_DIR, "assets", "icons")
MASTER_ICON = os.path.join(ICON_DIR, "baka.png")   # master artwork
ICON = os.path.join(ICON_DIR, "baka.ico")          # derived, Windows
ICNS = os.path.join(ICON_DIR, "baka.icns")         # derived, macOS bundle
ICON_SCRIPT = os.path.join(PROJECT_DIR, "scripts", "make_icons.py")

# Non-Python data bundled with the executable (source -> path inside bundle).
# The Python packages (ui/, backend/) are picked up automatically by PyInstaller.
DATA_DIRS = ["assets", "templates"]

# Modules PyInstaller cannot discover automatically.
HIDDEN_IMPORTS = [
    "pymupdf",
]

IS_WINDOWS = sys.platform == "win32"


def ensure_icons():
    """Derive baka.ico / baka.icns from the master PNG when missing or stale."""
    if not os.path.exists(MASTER_ICON):
        print(f"[WARN] master artwork not found: {MASTER_ICON}")
        return
    master_mtime = os.path.getmtime(MASTER_ICON)
    stale = [
        path for path in (ICON, ICNS)
        if not os.path.exists(path) or os.path.getmtime(path) < master_mtime
    ]
    if not stale:
        return
    print("[ICON] regenerating derived icons:", ", ".join(os.path.basename(p) for p in stale))
    result = subprocess.run([sys.executable, ICON_SCRIPT], cwd=PROJECT_DIR)
    if result.returncode != 0:
        print("[WARN] icon generation failed; continuing with existing files")


def platform_icon():
    """Native icon file for PyInstaller, or None when the OS has no concept."""
    if IS_WINDOWS:
        return ICON if os.path.exists(ICON) else None
    if sys.platform == "darwin":
        # PyInstaller only accepts .icns for macOS bundles; skip the icon
        # rather than failing the build when it is unavailable.
        return ICNS if os.path.exists(ICNS) else None
    return None  # Linux: the icon is a runtime window hint, not an ELF resource


def clean():
    for path in (DIST_DIR, BUILD_DIR):
        if os.path.exists(path):
            shutil.rmtree(path)
    if os.path.exists(SPEC_FILE):
        os.remove(SPEC_FILE)
    print("[CLEAN] Removed build artifacts")


def build():
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onedir",
        "--noconfirm",
        "--name", "Lume",
        "--windowed",
        "--clean",
    ]

    for name in DATA_DIRS:
        src = os.path.join(PROJECT_DIR, name)
        if os.path.isdir(src):
            cmd += ["--add-data", f"{src}{os.pathsep}{name}"]

    icon = platform_icon()
    if icon:
        cmd += ["--icon", icon]

    for module in HIDDEN_IMPORTS:
        cmd += ["--hidden-import", module]

    if IS_WINDOWS:
        # winreg is only available (and only needed) on Windows.
        cmd += ["--hidden-import", "winreg"]

    cmd.append(os.path.join(PROJECT_DIR, "main.py"))

    print(f"[BUILD] {' '.join(cmd)}")
    if subprocess.run(cmd, cwd=PROJECT_DIR).returncode != 0:
        print("[ERROR] Build failed")
        sys.exit(1)

    if sys.platform == "darwin":
        app_path = os.path.join(DIST_DIR, "Lume.app")
        print(f"[DONE] App bundle built at: {app_path}")
        print(f"       Run: open {app_path}")
    else:
        exe_name = "Lume.exe" if IS_WINDOWS else "Lume"
        out_dir = os.path.join(DIST_DIR, "Lume")
        print(f"[DONE] App built at: {out_dir}")
        print(f"       Run: {os.path.join(out_dir, exe_name)}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
    else:
        clean()
        ensure_icons()
        build()
