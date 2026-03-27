from __future__ import annotations

import io
import struct
from pathlib import Path

from PyQt6.QtCore import QByteArray, QBuffer, QRectF, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QImage, QPainter
from PyQt6.QtSvg import QSvgRenderer


ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT / "assets"
SVG_PATH = ASSETS_DIR / "icon.svg"
ICO_PATH = ASSETS_DIR / "icon.ico"
PNG_SIZES = [16, 32, 48, 256]


def render_png(size: int, renderer: QSvgRenderer) -> bytes:
    image = QImage(size, size, QImage.Format.Format_ARGB32)
    image.fill(Qt.GlobalColor.transparent)

    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, size, size))
    painter.end()

    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    image.save(buffer, b"PNG")
    return bytes(buffer.data())


def write_ico(png_chunks: list[tuple[int, bytes]]) -> None:
    header = struct.pack("<HHH", 0, 1, len(png_chunks))
    directory = bytearray()
    offset = 6 + len(png_chunks) * 16
    payload = bytearray()

    for size, png_data in png_chunks:
        width = 0 if size >= 256 else size
        height = 0 if size >= 256 else size
        directory.extend(
            struct.pack(
                "<BBBBHHII",
                width,
                height,
                0,
                0,
                1,
                32,
                len(png_data),
                offset,
            )
        )
        payload.extend(png_data)
        offset += len(png_data)

    ICO_PATH.write_bytes(header + directory + payload)


def main() -> None:
    app = QGuiApplication.instance() or QGuiApplication([])
    del app

    renderer = QSvgRenderer(str(SVG_PATH))
    if not renderer.isValid():
        raise RuntimeError(f"Invalid SVG: {SVG_PATH}")

    png_chunks: list[tuple[int, bytes]] = []
    for size in PNG_SIZES:
        png_data = render_png(size, renderer)
        png_chunks.append((size, png_data))
        (ASSETS_DIR / f"icon-{size}.png").write_bytes(png_data)

    write_ico(png_chunks)


if __name__ == "__main__":
    main()
