"""File loader and text normalizer for .txt, .md, .pdf (text layer) and .docx documents."""

from __future__ import annotations

import hashlib
import unicodedata
from pathlib import Path


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
        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(f"File not found: {file_path}")

        if path.suffix.lower() not in cls.SUPPORTED_EXTENSIONS:
            raise ValueError(
                f"Unsupported file format '{path.suffix}'. Supported formats: {', '.join(sorted(cls.SUPPORTED_EXTENSIONS))}"
            )

        suffix = path.suffix.lower()
        if suffix == ".pdf":
            content = cls._read_pdf(path)
        elif suffix == ".docx":
            content = cls._read_docx(path)
        else:
            # Try UTF-8 first, fallback to Latin-1
            try:
                content = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                content = path.read_text(encoding="latin-1")

        # NFC keeps Vietnamese diacritics consistent for hashing and TTS.
        cleaned = unicodedata.normalize("NFC", content).strip()
        if not cleaned:
            hint = " It may be a scanned PDF (OCR is not supported)." if suffix == ".pdf" else ""
            raise ValueError(f"The document is empty.{hint}")

        content_hash = compute_content_hash(cleaned)
        return cleaned, path.name, content_hash

    @staticmethod
    def _read_pdf(path: Path) -> str:
        from pypdf import PdfReader
        from pypdf.errors import PyPdfError

        try:
            reader = PdfReader(str(path))
            pages = [(page.extract_text() or "") for page in reader.pages]
        except (PyPdfError, OSError) as exc:
            raise ValueError(f"Cannot read PDF: {exc}") from exc
        return "\n\n".join(p.strip() for p in pages if p.strip())

    @staticmethod
    def _read_docx(path: Path) -> str:
        from docx import Document
        from docx.opc.exceptions import PackageNotFoundError

        try:
            doc = Document(str(path))
        except (PackageNotFoundError, OSError, KeyError) as exc:
            raise ValueError(f"Cannot read DOCX: {exc}") from exc
        return "\n\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())
