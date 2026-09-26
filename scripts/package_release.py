"""Package a PyInstaller build into a portable, version-stamped zip archive.

Usage
-----
    python scripts/package_release.py                    # platform auto-detected
    python scripts/package_release.py --platform Linux
    python scripts/package_release.py --date 20261002

The archive keeps the top-level folder (``Lume/`` or ``Lume.app``) so users can
simply unzip and run.  Created archives land in ``release/``.
"""

import argparse
import datetime
import os
import shutil
import subprocess
import sys

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIST = os.path.join(PROJECT_DIR, "dist")
DEFAULT_OUT = os.path.join(PROJECT_DIR, "release")


def detect_platform():
    if sys.platform.startswith("win"):
        return "Windows"
    if sys.platform == "darwin":
        return "macOS"
    return "Linux"


def human_size(num_bytes):
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def make_archive(payload, archive_base):
    """Zip ``payload`` keeping its top-level folder.

    macOS ``.app`` bundles contain symlinks and (ad-hoc) code signatures, which
    ``shutil.make_archive`` would flatten; ``ditto`` is the only archiver that
    round-trips them, so it is used whenever it is available.
    """
    archive = archive_base + ".zip"
    if shutil.which("ditto"):
        result = subprocess.run([
            "ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
            payload, archive,
        ])
        if result.returncode == 0:
            return archive
        print("[WARN] ditto failed, falling back to zipfile")

    return shutil.make_archive(
        archive_base, "zip",
        root_dir=os.path.dirname(payload),
        base_dir=os.path.basename(payload),
    )


def find_payload(dist_dir):
    """Return the folder to archive: the .app bundle on macOS, else dist/Lume."""
    candidates = [os.path.join(dist_dir, "Lume.app"), os.path.join(dist_dir, "Lume")]
    for path in candidates:
        if os.path.isdir(path):
            return path
    raise SystemExit(
        f"[ERROR] no build output found in {dist_dir}; run `python build.py` first"
    )


def main():
    parser = argparse.ArgumentParser(description="Zip a Lume build for release")
    parser.add_argument("--platform", default=None, help="Windows / Linux / macOS")
    parser.add_argument("--date", default=None, help="YYYYMMDD (default: today)")
    parser.add_argument("--dist", default=DEFAULT_DIST)
    parser.add_argument("--out", default=DEFAULT_OUT)
    args = parser.parse_args()

    platform = args.platform or detect_platform()
    date = args.date or datetime.date.today().strftime("%Y%m%d")
    os.makedirs(args.out, exist_ok=True)

    payload = find_payload(args.dist)
    base_name = os.path.join(args.out, f"Lume_{platform}_{date}")
    archive = make_archive(payload, base_name)

    print(f"[DONE] {archive}  ({human_size(os.path.getsize(archive))})")
    return archive


if __name__ == "__main__":
    main()
