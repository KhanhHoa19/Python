"""Text cleaner: Unicode/whitespace normalisation, wrapped lines, PDF headers/footers."""

from __future__ import annotations

import unicodedata
from pathlib import Path

from src.core.ingestion.cleaner import (
    join_wrapped_lines,
    merge_pages,
    normalize_text,
    remove_page_furniture,
)
from src.core.ingestion.parser import split_into_chapters_and_sentences
from src.core.ingestion.reader import DocumentReader
from tests.pdf_helpers import build_pdf

# ---------------------------------------------------------------- normalize_text


def test_normalize_uses_nfc_and_strips_invisible_characters() -> None:
    raw = unicodedata.normalize("NFD", "Việt Nam​ đẹp­ quá")
    assert normalize_text(raw) == "Việt Nam đẹp quá"


def test_normalize_collapses_spaces_and_blank_lines() -> None:
    assert normalize_text("a   b \t c  \r\n\r\n\r\n\r\nd") == "a b c\n\nd"


def test_normalize_removes_dotted_leaders_but_keeps_ellipses() -> None:
    assert normalize_text("ABBEY GRANGE..................................... 3") == "ABBEY GRANGE 3"
    assert normalize_text("Chờ đã... rồi nói. Hết…") == "Chờ đã... rồi nói. Hết…"


def test_normalize_drops_decorative_separator_lines() -> None:
    assert normalize_text("Đoạn một.\n* * *\n-----\n=====\nĐoạn hai.") == "Đoạn một.\nĐoạn hai."


# ---------------------------------------------------------------- join_wrapped_lines


def test_join_when_next_line_is_lowercase() -> None:
    assert join_wrapped_lines("đang phát\ntriển nhanh.") == "đang phát triển nhanh."


def test_join_after_comma_even_if_next_is_capitalised() -> None:
    assert join_wrapped_lines("Ông đến Hà Nội,\nHải Phòng.") == "Ông đến Hà Nội, Hải Phòng."


def test_do_not_join_after_sentence_end() -> None:
    assert join_wrapped_lines("Câu một.\nCâu hai.") == "Câu một.\nCâu hai."


def test_do_not_join_list_items_or_dialogue_lines() -> None:
    text = "- Anh đi đâu\n- tôi về nhà\n1. mục một\n2. mục hai"
    assert join_wrapped_lines(text) == text


def test_blank_lines_stay_paragraph_boundaries() -> None:
    assert join_wrapped_lines("đang phát\n\ntriển") == "đang phát\n\ntriển"


def test_full_width_line_joins_a_capitalised_continuation() -> None:
    wide = "Hội đồng quản trị công ty đã quyết định mở rộng sản xuất tại"
    text = "\n".join([f"{wide}\nHà Nội và Hải Phòng trong năm tới." for _ in range(4)])
    joined = join_wrapped_lines(text)
    assert joined.count("tại Hà Nội") == 4


def test_table_of_contents_lines_stay_separate_in_a_long_document() -> None:
    """Measured on the TOC alone every line looks 'full width'; the whole document says otherwise."""
    from src.core.ingestion.parser import split_into_chapters_and_sentences

    toc = "\n".join(["MỤC LỤC", "ABBEY GRANGE 3", "CUỘC PHƯU LƯU CỦA SÁU PHO TƯỢNG NAPOLEON 27",
                     "DẢI BĂNG LỐM ĐỐM 47", "HỘI TÓC HUNG 73", "KẺ DỊ DẠNG 93"])
    body_line = "Vào một buổi sáng lạnh lẽo và buốt giá của mùa đông năm một nghìn tám trăm chín mươi bảy, tôi"
    body = "\n".join(f"{body_line}\ntỉnh dậy lúc sáng sớm. Câu số {i}." for i in range(10))
    sentences = [s for c in split_into_chapters_and_sentences(f"{toc}\n\n{body}") for s in c["sentences"]]
    assert "CUỘC PHƯU LƯU CỦA SÁU PHO TƯỢNG NAPOLEON 27" in sentences
    assert "DẢI BĂNG LỐM ĐỐM 47" in sentences


def test_short_capitalised_line_is_kept_as_a_heading() -> None:
    body = "Đây là một đoạn văn khá dài nằm trên một dòng đầy đủ chiều rộng của trang giấy."
    text = f"{body}\n{body}\n{body}\nTổng kết\n{body}"
    assert "Tổng kết" in join_wrapped_lines(text).split("\n")


# ---------------------------------------------------------------- page furniture


def _pages(body_lines: list[list[str]], header: str = "Giáo trình Python", footer: str = "Trang {n}") -> list[str]:
    return [
        "\n".join([header, *body, footer.format(n=i + 1)]) for i, body in enumerate(body_lines)
    ]


def test_repeated_header_and_numbered_footer_are_removed() -> None:
    pages = _pages([["Nội dung trang một."], ["Nội dung trang hai."], ["Nội dung trang ba."], ["Nội dung trang bốn."]])
    cleaned = remove_page_furniture(pages)
    assert cleaned == [f"Nội dung trang {w}." for w in ("một", "hai", "ba", "bốn")]


def test_bare_page_numbers_are_removed_from_page_edges_only() -> None:
    pages = ["Nội dung A\n1", "Nội dung B\n2", "Nội dung C\n3", "Nội dung D\n4"]
    assert remove_page_furniture(pages) == ["Nội dung A", "Nội dung B", "Nội dung C", "Nội dung D"]
    embedded = ["Có 3 mục\nHết A", "Có 5 mục\nHết B", "Hai mục\nHết C", "Bốn mục\nHết D"]
    assert remove_page_furniture(embedded) == embedded  # digits inside real text are not page numbers


def test_a_line_seen_on_few_pages_is_content_not_furniture() -> None:
    pages = _pages([["Chương 1"], ["Nội dung"], ["Nội dung"], ["Nội dung"]], header="Tiêu đề chung")
    cleaned = remove_page_furniture(pages)
    assert "Chương 1" in cleaned[0]
    assert all("Tiêu đề chung" not in p for p in cleaned)


def test_documents_with_fewer_than_three_pages_are_left_alone() -> None:
    pages = _pages([["A."], ["B."]])
    assert remove_page_furniture(pages) == pages


def test_merge_pages_lets_a_sentence_continue_across_a_page_break() -> None:
    text = merge_pages(["Kinh tế đang phát", "triển nhanh chóng."])
    assert join_wrapped_lines(text) == "Kinh tế đang phát triển nhanh chóng."


# ---------------------------------------------------------------- real PDF end to end


def test_pdf_loader_removes_furniture_and_rejoins_sentence_split_across_pages(tmp_path: Path) -> None:
    pages = [
        ["Giao trinh Python", "Bai hoc dau tien. Kinh te dang phat", "Trang 1"],
        ["Giao trinh Python", "trien nhanh trong nhung nam gan day. Cau thu ba.", "Trang 2"],
        ["Giao trinh Python", "Noi dung trang ba.", "Trang 3"],
        ["Giao trinh Python", "Noi dung trang bon.", "Trang 4"],
    ]
    pdf = tmp_path / "giao_trinh.pdf"
    pdf.write_bytes(build_pdf(pages))

    text, _, _ = DocumentReader.load_document(pdf)
    sentences = [s for c in split_into_chapters_and_sentences(text) for s in c["sentences"]]

    assert sentences == [
        "Bai hoc dau tien.",
        "Kinh te dang phat trien nhanh trong nhung nam gan day.",
        "Cau thu ba.",
        "Noi dung trang ba.",
        "Noi dung trang bon.",
    ]
    assert not any("Giao trinh" in s or s.startswith("Trang") for s in sentences)
