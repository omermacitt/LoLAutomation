"""
Uygulama ikonunu üretir.

`assets/app_icon.png` (runtime) ve `assets/app_icon.ico` (PyInstaller exe) dosyalarını
programatik olarak oluşturur.
"""

from __future__ import annotations

import os
import re
import struct

from PyQt6.QtCore import Qt, QRectF, QPointF, QBuffer, QByteArray, QIODevice
from PyQt6.QtGui import (
    QBrush,
    QColor,
    QImage,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
)


def _draw_icon(size: int) -> QImage:
    """Verilen boyutta kare bir ikon görseli üretir."""
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)

    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

    rect = QRectF(0, 0, size, size)
    radius = size * 0.22

    # Background (dark gradient)
    bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg.setColorAt(0.0, QColor("#0B1026"))
    bg.setColorAt(0.55, QColor("#121B39"))
    bg.setColorAt(1.0, QColor("#4C1D95"))
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QBrush(bg))
    p.drawRoundedRect(rect, radius, radius)

    # Subtle inner highlight
    inner = rect.adjusted(size * 0.06, size * 0.06, -size * 0.06, -size * 0.06)
    shine = QLinearGradient(inner.topLeft(), inner.bottomRight())
    shine.setColorAt(0.0, QColor(255, 255, 255, 26))
    shine.setColorAt(0.6, QColor(255, 255, 255, 6))
    shine.setColorAt(1.0, QColor(0, 0, 0, 0))
    p.setBrush(QBrush(shine))
    p.drawRoundedRect(inner, radius * 0.78, radius * 0.78)

    center = QPointF(size / 2, size / 2)

    # Emblem ring
    outer_r = size * 0.33
    ring_grad = QLinearGradient(
        center.x() - outer_r,
        center.y() - outer_r,
        center.x() + outer_r,
        center.y() + outer_r,
    )
    ring_grad.setColorAt(0.0, QColor("#22D3EE"))  # cyan
    ring_grad.setColorAt(1.0, QColor("#F59E0B"))  # amber
    ring_pen = QPen(QBrush(ring_grad), size * 0.06, Qt.PenStyle.SolidLine)
    ring_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    ring_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(ring_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(center, outer_r, outer_r)

    # Inner disk
    inner_r = size * 0.265
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor(9, 13, 28, 170))
    p.drawEllipse(center, inner_r, inner_r)

    # Rune glyph (simple, high-contrast strokes that scale well)
    stroke_pen = QPen(QColor("#E2E8F0"), size * 0.042, Qt.PenStyle.SolidLine)
    stroke_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    stroke_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(stroke_pen)

    def pt(nx: float, ny: float) -> QPointF:
        return QPointF(center.x() + nx * size, center.y() + ny * size)

    # A rune-like "bolt"
    glyph = QPainterPath()
    glyph.moveTo(pt(-0.08, -0.17))
    glyph.lineTo(pt(0.06, -0.17))
    glyph.lineTo(pt(-0.02, 0.02))
    glyph.lineTo(pt(0.10, 0.02))
    glyph.lineTo(pt(-0.06, 0.19))
    p.drawPath(glyph)

    # A small node dot
    p.setBrush(QColor("#E2E8F0"))
    p.setPen(Qt.PenStyle.NoPen)
    dot_r = size * 0.032
    p.drawEllipse(pt(0.11, -0.12), dot_r, dot_r)

    # Subtle outer glow
    glow_pen = QPen(QColor(34, 211, 238, 45), size * 0.09)
    glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    p.setPen(glow_pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawEllipse(center, outer_r * 0.98, outer_r * 0.98)

    p.end()
    return img


def _image_to_png_bytes(img: QImage) -> bytes:
    """QImage objesini PNG byte dizisine dönüştürür."""
    ba = QByteArray()
    buf = QBuffer(ba)
    buf.open(QIODevice.OpenModeFlag.WriteOnly)
    ok = img.save(buf, "PNG")
    buf.close()
    if not ok:
        raise RuntimeError("Failed to encode PNG bytes")
    return bytes(ba)


def _write_ico(path: str, images: list[tuple[int, bytes]]) -> None:
    """PNG içerikleriyle ICO container yazar (çoklu boyut destekli)."""
    # ICO container with PNG images (recommended modern approach).
    images = [(s, b) for s, b in images if s > 0 and b]
    if not images:
        raise ValueError("No images provided for ICO")

    # Ensure stable ordering.
    images.sort(key=lambda t: t[0])

    count = len(images)
    header = struct.pack("<HHH", 0, 1, count)
    dir_offset = 6 + 16 * count

    entries: list[bytes] = []
    data_chunks: list[bytes] = []
    offset = dir_offset
    for size, png_bytes in images:
        # In ICO, 0 means 256.
        w = size if size < 256 else 0
        h = size if size < 256 else 0
        entry = struct.pack(
            "<BBBBHHII",
            w,
            h,
            0,  # color count
            0,  # reserved
            1,  # planes
            32,  # bit count
            len(png_bytes),
            offset,
        )
        entries.append(entry)
        data_chunks.append(png_bytes)
        offset += len(png_bytes)

    with open(path, "wb") as f:
        f.write(header)
        for e in entries:
            f.write(e)
        for chunk in data_chunks:
            f.write(chunk)


def main() -> None:
    """Repo içindeki `assets/` altına ikon dosyalarını yazar."""
    repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    assets_dir = os.path.join(repo_root, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    png_path = os.path.join(assets_dir, "app_icon.png")
    ico_path = os.path.join(assets_dir, "app_icon.ico")

    # Runtime PNG
    img_256 = _draw_icon(256)
    if not img_256.save(png_path, "PNG"):
        raise RuntimeError(f"Failed to write {png_path}")

    # Multi-size ICO for Windows executables
    sizes = [16, 24, 32, 48, 64, 128, 256]
    ico_images: list[tuple[int, bytes]] = []
    for s in sizes:
        ico_images.append((s, _image_to_png_bytes(_draw_icon(s))))
    _write_ico(ico_path, ico_images)

    # Keep filenames clean on Windows and make it easy to spot in Explorer.
    safe = re.sub(r"[^0-9A-Za-z._-]", "_", os.path.basename(ico_path))
    if safe != os.path.basename(ico_path):
        os.replace(ico_path, os.path.join(assets_dir, safe))

    print(f"Wrote: {png_path}")
    print(f"Wrote: {ico_path}")


if __name__ == "__main__":
    main()
