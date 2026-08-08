"""Local persistence for AI model configs and app settings."""

import json
import os
import sys
import tempfile
from pathlib import Path

DEFAULT_CONFIG = {"ocr_host": "127.0.0.1", "ocr_port": "1224"}


def _get_app_dir():
    """Prefer the app directory (portable), fall back to the OS data dir.

    The fallback matters on macOS app bundles and system-wide installs where
    the executable directory is not writable.
    """
    candidates = []
    if getattr(sys, "frozen", False):
        executable = Path(sys.executable).resolve()
        if sys.platform == "darwin" and executable.parent.name == "MacOS":
            candidates.append(str(executable.parents[3]))
        else:
            candidates.append(str(executable.parent))
    else:
        candidates.append(os.path.dirname(os.path.dirname(__file__)))

    for base in candidates:
        if os.path.isdir(base) and os.access(base, os.W_OK):
            return base

    from PySide6.QtCore import QStandardPaths

    fallback = os.path.join(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.GenericDataLocation),
        "Lume",
    )
    os.makedirs(fallback, exist_ok=True)
    return fallback


APP_DIR = _get_app_dir()
DATA_DIR = os.path.join(APP_DIR, "data")
DATA_FILE = os.path.join(DATA_DIR, "models.json")
CONFIG_FILE = os.path.join(DATA_DIR, "config.json")


def _write_json(path, value):
    directory = os.path.dirname(path)
    fd, temp_path = tempfile.mkstemp(prefix=".lume-", suffix=".tmp", dir=directory)
    try:
        if os.name != "nt":
            os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(value, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_path, path)
        if os.name != "nt":
            os.chmod(path, 0o600)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise


def _read_json(path, fallback):
    ensure_data_dir()
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return fallback


def ensure_data_dir():
    os.makedirs(DATA_DIR, exist_ok=True)
    if os.name != "nt":
        os.chmod(DATA_DIR, 0o700)
    if not os.path.exists(DATA_FILE):
        _write_json(DATA_FILE, [])
    if not os.path.exists(CONFIG_FILE):
        _write_json(CONFIG_FILE, DEFAULT_CONFIG)
    if os.name != "nt":
        os.chmod(DATA_FILE, 0o600)
        os.chmod(CONFIG_FILE, 0o600)


def load_models():
    return _read_json(DATA_FILE, [])


def save_models(models):
    ensure_data_dir()
    _write_json(DATA_FILE, models)


def load_config():
    config = dict(DEFAULT_CONFIG)
    config.update(_read_json(CONFIG_FILE, {}))
    return config


def save_config(config):
    ensure_data_dir()
    _write_json(CONFIG_FILE, config)
