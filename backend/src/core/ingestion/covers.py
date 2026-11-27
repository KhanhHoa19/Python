"""Book covers: the first page of a PDF, a generated cover, or an image the user uploads. All end up as JPEG files."""

from __future__ import annotations

import colorsys
import io
import logging
import re
import unicodedata
import uuid
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError

from src.core.config import get_settings

logger = logging.getLogger(__name__)

COVER_WIDTH, COVER_HEIGHT = 400, 533  # 3:4, like a book
MAX_COVER_UPLOAD_BYTES = 2 * 1024 * 1024
COVER_NAME = re.compile(r"^[0-9a-f]{32}\.jpg$")
_JPEG_QUALITY = 85


class CoverError(ValueError):
    """The uploaded image cannot be used."""


# ---------------------------------------------------------------------------------- storage

def cover_dir() -> Path:
    path = Path(get_settings().cover_dir).resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_cover(jpeg: bytes) -> str:
    """Store a JPEG under an unguessable name and return that name (what books.cover_path holds)."""
    name = f"{uuid.uuid4().hex}.jpg"
    (cover_dir() / name).write_bytes(jpeg)
    return name


def cover_path(name: str) -> Path | None:
    """The file of a stored cover, or None for a bad name (no path tricks) or a missing file."""
    if not COVER_NAME.fullmatch(name):
        return None
    path = cover_dir() / name
    return path if path.is_file() else None


def delete_cover(name: str | None) -> None:
    if name and COVER_NAME.fullmatch(name):
        (cover_dir() / name).unlink(missing_ok=True)


def cover_url(name: str | None) -> str | None:
    return f"/api/covers/{name}" if name else None


# ---------------------------------------------------------------------------------- making images

def _to_jpeg(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, "JPEG", quality=_JPEG_QUALITY, optimize=True)
    return buffer.getvalue()


def _fit_cover(image: Image.Image) -> Image.Image:
    """Scale and centre-crop to exactly COVER_WIDTH x COVER_HEIGHT."""
    image = image.convert("RGB")
    scale = max(COVER_WIDTH / image.width, COVER_HEIGHT / image.height)
    resized = image.resize((max(COVER_WIDTH, round(image.width * scale)), max(COVER_HEIGHT, round(image.height * scale))),
                           Image.Resampling.LANCZOS)
    left, top = (resized.width - COVER_WIDTH) // 2, (resized.height - COVER_HEIGHT) // 2
    return resized.crop((left, top, left + COVER_WIDTH, top + COVER_HEIGHT))


def normalize_uploaded_cover(data: bytes) -> bytes:
    """Validate an uploaded JPEG/PNG (<= 2 MB) and return it as a 400x533 JPEG."""
    if len(data) > MAX_COVER_UPLOAD_BYTES:
        raise CoverError("Cover image exceeds 2 MB.")
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ("JPEG", "PNG"):
                raise CoverError("Cover must be a JPEG or PNG image.")
            image.load()
            return _to_jpeg(_fit_cover(image))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise CoverError("Cover is not a valid image.") from exc


def render_pdf_cover(pdf_path: str | Path) -> bytes | None:
    """The first page of a PDF as a cover, or None if it cannot be drawn (the caller then makes a default one)."""
    try:
        import pymupdf

        with pymupdf.open(str(pdf_path)) as document:
            if document.page_count == 0:
                return None
            page = document[0]
            zoom = COVER_WIDTH / max(page.rect.width, 1)
            pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
            image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
        return _to_jpeg(_fit_cover(image))
    except Exception as exc:  # a broken PDF must never stop the book from being added
        logger.warning("Could not render a PDF cover: %s", exc)
        return None


def hue_for(title: str) -> int:
    """Stable hue (0-359) for a title: the same colour on every screen and in every generated cover."""
    value = 0
    for char in unicodedata.normalize("NFC", title):
        value = (value * 31 + ord(char)) % 3600
    return int(value / 10 + 0.5) % 360


def _hsl(hue: float, saturation: float, lightness: float) -> tuple[int, int, int]:
    red, green, blue = colorsys.hls_to_rgb((hue % 360) / 360, lightness, saturation)
    return round(red * 255), round(green * 255), round(blue * 255)


def _font(bold: bool, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """DejaVu Sans ships with Matplotlib and has every Vietnamese letter; no font file to add to the project."""
    try:
        import matplotlib

        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(str(Path(matplotlib.get_data_path()) / "fonts" / "ttf" / name), size)
    except (ImportError, OSError):
        return ImageFont.load_default()


def _wrap(text: str, font: ImageFont.FreeTypeFont | ImageFont.ImageFont, width: int, max_lines: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        trial = f"{current} {word}".strip()
        if current and font.getlength(trial) > width:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(" .,;") + "…"
    return lines


def generate_default_cover(title: str, author: str = "", hue: int | None = None) -> bytes:
    """A plain cover: colour from the title (or the category), the title in large letters, the author below."""
    base = hue_for(title) if hue is None else hue
    top, bottom = _hsl(base, 0.55, 0.42), _hsl(base + 35, 0.6, 0.24)
    image = Image.new("RGB", (COVER_WIDTH, COVER_HEIGHT))
    draw = ImageDraw.Draw(image)
    for y in range(COVER_HEIGHT):  # vertical gradient
        t = y / (COVER_HEIGHT - 1)
        draw.line([(0, y), (COVER_WIDTH, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom, strict=True)))
    draw.rectangle([0, 0, 14, COVER_HEIGHT], fill=_hsl(base, 0.5, 0.18))  # the spine
    draw.rectangle([44, 70, 124, 76], fill=(255, 255, 255))  # a small rule above the title

    title_font, author_font = _font(True, 36), _font(False, 22)
    y = 100
    for line in _wrap(title.strip() or "Tài liệu", title_font, COVER_WIDTH - 90, 6):
        draw.text((44, y), line, font=title_font, fill=(255, 255, 255))
        y += 48
    author = author.strip()
    if author and author.lower() != "unknown":
        lines = _wrap(author, author_font, COVER_WIDTH - 90, 2)
        y = COVER_HEIGHT - 56 - 30 * (len(lines) - 1)
        for line in lines:
            draw.text((44, y), line, font=author_font, fill=(255, 255, 255, 220))
            y += 30
    return _to_jpeg(image)
