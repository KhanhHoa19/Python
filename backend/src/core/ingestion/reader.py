"""File loader and text normalizer for .txt, .md, .pdf (text layer) and .docx documents."""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path

from src.core.ingestion.cleaner import merge_pages, normalize_text, remove_page_furniture
from src.core.ingestion.legacy_vietnamese import decode_legacy_text, looks_like_vietware


def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 hash of document text."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class DocumentReader:
    """Handles file reading, encoding handling, and format validation."""

    SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown", ".text", ".pdf", ".docx"}

    @classmethod
    def load_document(cls, file_path: str | Path) -> tuple[str, str, str]:
        """
        Load document from disk, validate format, and return (content, filename, content_hash).

        Raises:
            FileNotFoundError: If the target file does not exist.
            ValueError: If file is empty or has an unsupported format.
        """
        content, filename, content_hash, _ = cls.load_with_headings(file_path)
        return content, filename, content_hash

    @classmethod
    def load_with_headings(cls, file_path: str | Path) -> tuple[str, str, str, list[str]]:
        """Like `load_document`, plus the chapter titles found in the file's own outline
        (PDF bookmarks, Word "Heading 1"). The titles are hints for the chapter splitter."""
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.suffix.lower() not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{path.suffix}'. Supported formats: {', '.join(sorted(cls.SUPPORTED_EXTENSIONS))}"
            )

        suffix = path.suffix.lower()
        headings: list[str] = []
        if suffix == ".pdf":
            content, headings = cls._read_pdf(path)
        elif suffix == ".docx":
            content, headings = cls._read_docx(path)
        else:
            # Try UTF-8 first, fallback to Latin-1
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="latin-1")
        if suffix != ".pdf" and looks_like_vietware(content):
            content = decode_legacy_text(content)  # text typed in an old .Vn* font

        # NFC, invisible characters and whitespace normalised: consistent hashing and TTS input.
        cleaned = normalize_text(content)
        if not cleaned:
            hint = " It may be a scanned PDF (OCR is not supported)." if suffix == ".pdf" else ""
            raise ValueError(f"The document is empty.{hint}")

        content_hash = compute_content_hash(cleaned)
        return cleaned, path.name, content_hash, headings

    @staticmethod
    def _read_pdf(path: Path) -> tuple[str, list[str]]:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError

        try:
            reader = PdfReader(str(path))
            pages = [(page.extract_text() or "").strip() for page in reader.pages]
            titles = _outline_titles(reader)
        except (PyPdfError, OSError) as exc:
            raise ValueError(f"Cannot read PDF: {exc}") from exc
        legacy = looks_like_vietware("\n".join(pages))
        if legacy:
            # Old Word file printed with a VietWare (.VnTime, .VnNCentury...) font: the text layer
            # holds Latin-1 look-alikes, so decode it before anything else looks at the text.
            pages = [decode_legacy_text(page) for page in pages]
        # Running headers/footers/page numbers removed; pages joined by one newline so a sentence
        # that continues on the next page can be re-joined by the sentence splitter.
        # Outline titles may be in the legacy encoding too; offer both spellings, the splitter keeps
        # only those that really equal a line of the text.
        headings = titles + [decode_legacy_text(t) for t in titles] if legacy else titles
        return merge_pages(remove_page_furniture(pages)), headings

    @staticmethod
    def _read_docx(path: Path) -> tuple[str, list[str]]:
        from docx import Document
        from docx.opc.exceptions import PackageNotFoundError

        try:
            doc = Document(str(path))
        except (PackageNotFoundError, OSError, KeyError) as exc:
            raise ValueError(f"Cannot read DOCX: {exc}") from exc
        text = "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
        headings = [
            p.text.strip() for p in doc.paragraphs
            if p.text.strip() and p.style is not None and (p.style.name or "").lower() == "heading 1"
        ]
        return text, headings


def _outline_titles(reader: object) -> list[str]:
    """Titles of the PDF's bookmarks at the first level that has at least two entries (a book whose only
    top-level bookmark is its own title is read one level deeper). Empty if there is no usable outline."""
    levels: list[list[str]] = []

    def walk(items: object, depth: int) -> None:
        for item in items:  # type: ignore[attr-defined]
            if isinstance(item, list):
                walk(item, depth + 1)
                continue
            title = getattr(item, "title", None)
            if title and str(title).strip():
                while len(levels) <= depth:
                    levels.append([])
                levels[depth].append(unicodedata.normalize("NFC", str(title)).strip())

    try:
        walk(reader.outline, 0)  # type: ignore[attr-defined]
    except (AttributeError, KeyError, TypeError, ValueError, RecursionError):
        return []
    return next((titles for titles in levels[:3] if len(titles) >= 2), [])
