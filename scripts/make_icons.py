"""Derive every platform icon format from the master artwork.

The master is ``assets/icons/baka.png`` (square, RGBA, transparent background).
Windows wants ``.ico`` and macOS bundles want ``.icns``; both are plain
containers around the same PNG pixels, so they are generated here without any
third-party imaging library::

    python scripts/make_icons.py

Outputs (next to the master):

* ``baka.ico``   multi-size icon (16/24/32/48/64/128/256) for Windows
* ``baka.icns``  macOS bundle icon (32/64/128/256/512)

``build.py`` runs this automatically when the master is newer than the derived
files, so editing the artwork is enough.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
from pathlib import Path

# Pure image processing needs no window; the offscreen backend also keeps this
# working on headless machines (CI, servers) where no display is available.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QBuffer, QIODevice, Qt  # noqa: E402
from PySide6.QtGui import QGuiApplication, QImage  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = PROJECT_DIR / "assets" / "icons" / "baka.png"
DEFAULT_OUT = DEFAULT_SOURCE.parent

ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
ICNS_TYPES = {"ic11": 32, "ic12": 64, "ic07": 128, "ic08": 256, "ic09": 512}


def render(source: QImage, size: int) -> QImage:
    """Scale the artwork onto a transparent square canvas of ``size``."""
    canvas = QImage(size, size, QImage.Format.Format_ARGB32)
    canvas.fill(Qt.GlobalColor.transparent)
    scaled = source.scaled(
        size, size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    left = (size - scaled.width()) // 2
    top = (size - scaled.height()) // 2
    from PySide6.QtGui import QPainter

    painter = QPainter(canvas)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawImage(left, top, scaled)
    painter.end()
    return canvas


def png_bytes(image: QImage) -> bytes:
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    if not image.save(buffer, "PNG"):
        raise SystemExit("[ERROR] failed to encode PNG")
    data = bytes(buffer.data())
    buffer.close()
    return data


def write_ico(path: Path, images: list[QImage]) -> None:
    """Write a PNG-based .ico (supported by Windows Vista and newer)."""
    payloads = [png_bytes(image) for image in images]
    header = struct.pack("<HHH", 0, 1, len(images))  # reserved, type=icon, count
    offset = len(header) + 16 * len(images)
    entries, blobs = b"", b""
    for image, payload in zip(images, payloads, strict=True):
        side = image.width()
        entries += struct.pack(
            "<BBBBHHII",
            0 if side >= 256 else side,  # 0 means 256 in the ICO directory
            0 if side >= 256 else side,
            0, 0, 1, 32, len(payload), offset,
        )
        blobs += payload
        offset += len(payload)
    path.write_bytes(header + entries + blobs)


def write_icns(path: Path, blocks: list[tuple[str, bytes]]) -> None:
    chunks = [b"icns", b"\0\0\0\0"]  # total size patched in below
    for kind, payload in blocks:
        chunks.append(kind.encode("ascii") + struct.pack(">I", len(payload) + 8) + payload)
    data = b"".join(chunks)
    path.write_bytes(data[:4] + struct.pack(">I", len(data)) + data[8:])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    QGuiApplication.instance() or QGuiApplication(sys.argv)

    source_path = args.source
    out_dir = args.out or source_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    master = QImage(str(source_path))
    if master.isNull():
        raise SystemExit(f"[ERROR] cannot read icon source: {source_path}")
    master = master.convertToFormat(QImage.Format.Format_ARGB32)
    print(f"[ICON] source {source_path.name} {master.width()}x{master.height()}")

    sizes = [render(master, size) for size in ICO_SIZES]
    ico_path = out_dir / "baka.ico"
    write_ico(ico_path, sizes)
    print(f"[ICON] {ico_path.name}  {'/'.join(str(s) for s in ICO_SIZES)}")

    icns_path = out_dir / "baka.icns"
    write_icns(icns_path, [(kind, png_bytes(render(master, size)))
                           for kind, size in ICNS_TYPES.items()])
    print(f"[ICON] {icns_path.name}  {'/'.join(str(s) for s in ICNS_TYPES.values())}")


if __name__ == "__main__":
    main()
