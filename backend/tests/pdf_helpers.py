"""Minimal PDF writer for tests (WinAnsi text, no fonts embedded)."""

from __future__ import annotations


def build_pdf(pages: list[list[str]]) -> bytes:
    """One text line per list item. Text is written as Latin-1 bytes under /WinAnsiEncoding, which is
    how legacy Vietnamese (.Vn*) fonts end up in real PDFs. Built-in Helvetica has no Vietnamese
    glyphs, so ordinary tests stay ASCII; only the extracted *characters* matter here."""

    def escape(line: str) -> str:
        return line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    objects: list[bytes] = [b"<< /Type /Catalog /Pages 2 0 R >>"]
    kids = " ".join(f"{3 + i * 2} 0 R" for i in range(len(pages)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode())
    font_id = 3 + len(pages) * 2
    for i, lines in enumerate(pages):
        content = "BT /F1 12 Tf 72 740 Td 16 TL " + " ".join(f"({escape(line)}) Tj T*" for line in lines) + " ET"
        stream = content.encode("latin-1")
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {4 + i * 2} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        objects.append(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>")
    out, offsets = b"%PDF-1.4\n", []
    for number, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + obj + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % off for off in offsets)
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objects) + 1, xref)
    return out
