"""Hard Vietnamese cases for the sentence splitter (plan task 2.5: at least 20)."""

from __future__ import annotations

import unicodedata

import pytest

from src.core.ingestion.parser import split_into_chapters_and_sentences, tokenize_sentences

# (id, input text, expected sentences)
CASES = [
    ("basic", "Hôm nay trời đẹp. Chúng ta đi chơi!", ["Hôm nay trời đẹp.", "Chúng ta đi chơi!"]),
    ("decimal-point", "Số pi xấp xỉ 3.14. Đó là số vô tỉ.", ["Số pi xấp xỉ 3.14.", "Đó là số vô tỉ."]),
    ("decimal-comma", "Giá là 3,5 triệu đồng. Rẻ thật.", ["Giá là 3,5 triệu đồng.", "Rẻ thật."]),
    ("thousands-dots", "Tôi trả 1.000.000 đồng. Hết tiền.", ["Tôi trả 1.000.000 đồng.", "Hết tiền."]),
    ("tp-space", "Tôi sống ở TP. Hồ Chí Minh. Trời nóng.", ["Tôi sống ở TP. Hồ Chí Minh.", "Trời nóng."]),
    ("tp-hcm", "Anh ấy đến TP.HCM hôm qua. Cô ấy ở lại.", ["Anh ấy đến TP.HCM hôm qua.", "Cô ấy ở lại."]),
    (
        "pgs-ts",
        "PGS.TS. Nguyễn Văn A giảng bài. Sinh viên nghe.",
        ["PGS.TS. Nguyễn Văn A giảng bài.", "Sinh viên nghe."],
    ),
    (
        "titles",
        "GS. Trần Văn B và ThS. Lê Thị C tham dự. BS. Phạm D khám bệnh.",
        ["GS. Trần Văn B và ThS. Lê Thị C tham dự.", "BS. Phạm D khám bệnh."],
    ),
    ("ellipsis-then-capital", "Chờ đã… Rồi anh ấy nói tiếp.", ["Chờ đã…", "Rồi anh ấy nói tiếp."]),
    ("ellipsis-then-lower", "Chờ đã… rồi anh ấy nói tiếp.", ["Chờ đã… rồi anh ấy nói tiếp."]),
    ("three-dots-then-lower", "Anh ấy ngập ngừng... rồi bỏ đi.", ["Anh ấy ngập ngừng... rồi bỏ đi."]),
    ("ellipsis-at-end", "Anh ấy im lặng…", ["Anh ấy im lặng…"]),
    ("question-exclaim", "Bạn khỏe không? Tôi khỏe! Cảm ơn.", ["Bạn khỏe không?", "Tôi khỏe!", "Cảm ơn."]),
    ("interrobang", "Thật sao?! Không thể tin được.", ["Thật sao?!", "Không thể tin được."]),
    (
        "straight-quotes",
        'Anh nói: "Tôi đi ngay." Rồi anh bỏ đi.',
        ['Anh nói: "Tôi đi ngay."', "Rồi anh bỏ đi."],
    ),
    (
        "curly-quotes",
        "Cô hỏi: “Anh đi đâu?” Anh không trả lời.",
        ["Cô hỏi: “Anh đi đâu?”", "Anh không trả lời."],
    ),
    (
        "dialogue-dashes",
        "- Anh đi đâu?\n- Tôi về nhà.\n- Khi nào?",
        ["- Anh đi đâu?", "- Tôi về nhà.", "- Khi nào?"],
    ),
    (
        "numbered-list",
        "1. Giới thiệu\n2. Nội dung\n3. Kết luận",
        ["1. Giới thiệu", "2. Nội dung", "3. Kết luận"],
    ),
    ("section-number", "1.2. Mục tiêu của đề tài\nĐề tài nghiên cứu tiếng Việt.",
     ["1.2. Mục tiêu của đề tài", "Đề tài nghiên cứu tiếng Việt."]),
    ("letter-heading", "A. Tổng quan\nPhần này giới thiệu.", ["A. Tổng quan", "Phần này giới thiệu."]),
    (
        "vv-continues",
        "Mua rau, củ, quả, v.v. và nhiều thứ khác.",
        ["Mua rau, củ, quả, v.v. và nhiều thứ khác."],
    ),
    ("vv-ends-sentence", "Mua rau, củ, v.v. Sau đó về nhà.", ["Mua rau, củ, v.v.", "Sau đó về nhà."]),
    ("page-abbreviation", "Xem tr. 25 để biết thêm. Hết.", ["Xem tr. 25 để biết thêm.", "Hết."]),
    (
        "million-abbreviation",
        "Giá khoảng 5 tr. đồng một tháng. Khá rẻ.",
        ["Giá khoảng 5 tr. đồng một tháng.", "Khá rẻ."],
    ),
    (
        "wrapped-lowercase",
        "Kinh tế Việt Nam đang phát\ntriển rất nhanh trong những\nnăm gần đây.",
        ["Kinh tế Việt Nam đang phát triển rất nhanh trong những năm gần đây."],
    ),
    (
        "wrapped-after-comma",
        "Ông đến Hà Nội,\nHải Phòng và Đà Nẵng.",
        ["Ông đến Hà Nội, Hải Phòng và Đà Nẵng."],
    ),
    ("heading-then-paragraph", "Giới thiệu\n\nĐây là phần mở đầu.", ["Giới thiệu", "Đây là phần mở đầu."]),
    ("extra-whitespace", "Xin   chào các bạn.​ Hẹn gặp lại.", ["Xin chào các bạn.", "Hẹn gặp lại."]),
    (
        "english-abbreviations-still-work",
        "Dr. Watson visited Mr. Holmes at 221B Baker St. in London. They talked e.g. about cases.",
        ["Dr. Watson visited Mr. Holmes at 221B Baker St. in London.", "They talked e.g. about cases."],
    ),
]


@pytest.mark.parametrize(("text", "expected"), [c[1:] for c in CASES], ids=[c[0] for c in CASES])
def test_vietnamese_sentence_splitting(text: str, expected: list[str]) -> None:
    assert tokenize_sentences(text) == expected


def test_at_least_twenty_hard_cases_are_covered() -> None:
    assert len(CASES) >= 20


def test_decomposed_unicode_is_normalised_to_nfc() -> None:
    decomposed = unicodedata.normalize("NFD", "Tiếng Việt đẹp.")
    assert decomposed != "Tiếng Việt đẹp."
    assert tokenize_sentences(decomposed) == ["Tiếng Việt đẹp."]


def test_empty_and_whitespace_only_input() -> None:
    assert tokenize_sentences("") == []
    assert tokenize_sentences("  \n\n \t ") == []


# ---------------------------------------------------------------- long sentences


def test_long_sentence_splits_at_commas_but_never_inside_a_decimal_number() -> None:
    clause = "học sinh giỏi đạt điểm trung bình 8,5 ở tất cả các môn học chính"
    sentence = f"Năm nay {clause}, {clause}, {clause}, {clause}."
    assert len(sentence.split()) > 35

    chunks = tokenize_sentences(sentence, max_clause_words=35)

    assert len(chunks) > 1
    assert all(len(c.split()) <= 35 for c in chunks)
    assert not any(c.endswith("8,") for c in chunks)  # "8,5" must stay together
    assert " ".join(chunks).count("8,5") == 4


def test_long_sentence_without_punctuation_is_hard_split_by_words() -> None:
    sentence = " ".join(["từ"] * 100) + "."
    chunks = tokenize_sentences(sentence, max_clause_words=35)
    assert len(chunks) == 3
    assert all(len(c.split()) <= 35 for c in chunks)


def test_oversized_clause_between_commas_is_still_split() -> None:
    big_clause = " ".join(["chữ"] * 60)
    chunks = tokenize_sentences(f"Mở đầu ngắn, {big_clause}, kết thúc ngắn.", max_clause_words=35)
    assert all(len(c.split()) <= 35 for c in chunks)
    assert chunks[0].startswith("Mở đầu ngắn")


def test_character_limit_splits_long_text_for_providers_with_small_request_limits() -> None:
    sentence = "Một hai ba bốn năm sáu, bảy tám chín mười mười một, mười hai mười ba mười bốn mười lăm."
    chunks = tokenize_sentences(sentence, max_clause_words=35, max_chars=40)
    assert len(chunks) > 1
    assert all(len(c) <= 40 for c in chunks)
    assert " ".join(chunks).replace(",", "") == sentence.replace(",", "")


# ---------------------------------------------------------------- chapters


def test_vietnamese_chapter_headings_are_detected() -> None:
    doc = (
        "Chương 1: Mở đầu\n\nNội dung một. Nội dung hai.\n\n"
        "CHƯƠNG II\n\nNội dung ba.\n\n"
        "Bài 3: Hàm\n\nNội dung bốn."
    )
    chapters = split_into_chapters_and_sentences(doc)
    assert [c["title"] for c in chapters] == ["Chương 1: Mở đầu", "CHƯƠNG 2", "Bài 3: Hàm"]  # Roman numerals become Arabic
    assert [len(c["sentences"]) for c in chapters] == [2, 1, 1]


def test_a_normal_sentence_starting_with_phan_is_not_a_heading() -> None:
    doc = "Phần lớn học sinh thích môn này vì nó rất thú vị. Họ học chăm chỉ."
    chapters = split_into_chapters_and_sentences(doc)
    assert len(chapters) == 1
    assert chapters[0]["sentences"][0].startswith("Phần lớn học sinh")


# ---------------------------------------------------------------- typos found in a real book


def test_missing_space_after_a_sentence_end_is_repaired() -> None:
    assert tokenize_sentences("Tôi không thích lối sống ở Anh quốc.Nhưng lý do chính là rượu.") == [
        "Tôi không thích lối sống ở Anh quốc.", "Nhưng lý do chính là rượu.",
    ]
    assert tokenize_sentences("Anh nói.Cô có tin không?Tôi tin.") == ["Anh nói.", "Cô có tin không?", "Tôi tin."]


@pytest.mark.parametrize(
    "text",
    ["Xem www.Google.com để biết thêm.", "Gửi thư tới an.Nguyen@mail.vn nhé.", "Tải tại http://x.vn/a.Bc ngay.",
     "Số pi là 3.14 và PGS.TS. Nam đến.", "Dr.Watson đã đến.", "Mrs.Hudson đã đến."],
)
def test_missing_space_repair_leaves_addresses_numbers_and_titles_alone(text: str) -> None:
    assert len(tokenize_sentences(text)) == 1


def test_space_before_punctuation_is_removed() -> None:
    assert tokenize_sentences("Phải mất trọn một đêm mới làm được việc . Rồi ngủ ,  hết !") == [
        "Phải mất trọn một đêm mới làm được việc.", "Rồi ngủ, hết!",
    ]


# ---------------------------------------------------------------- parts, tables of contents (a real omnibus book)


OMNIBUS = """MỤC LỤC

ABBEY GRANGE 3
HỘI TÓC HUNG 73
THUNG LŨNG KHỦNG KHIẾP 157
Phần thứ nhất TẤN BI KỊCH Ở LÂU ĐÀI BIRLSTONE.
Chương 7 Giải đáp 198
Phần thứ hai NHỮNG NGƯỜI TIÊN PHONG 207

ABBEY GRANGE

Vào một buổi sáng lạnh lẽo, tôi bỗng thức giấc vì có ai lay mạnh vai tôi.

HỘI TÓC HUNG

Ông Wilson đến gặp Holmes vào một chiều thu.

THUNG LŨNG KHỦNG KHIẾP

Phần thứ nhất

TẤN BI KỊCH Ở LÂU ĐÀI BIRLSTONE

Chương I

TIN BÁO

Holmes không đụng đến bữa điểm tâm.

Chương 2

Ông Dona đến vào sáng hôm sau.

Phần thứ hai

NHỮNG NGƯỜI TIÊN PHONG

Chương 1

CON NGƯỜI ẤY

Ngày 4 tháng 2 năm 1875 tuyết phủ đầy các đường đèo.

Chương 2

Một con tàu đang ì ạch leo lên đèo.
"""


def test_chapters_of_two_parts_do_not_look_repeated() -> None:
    titles = [c["title"] for c in split_into_chapters_and_sentences(OMNIBUS)]
    assert len(titles) == len(set(titles)), titles  # no two entries read the same
    assert "Phần thứ nhất · Chương 1 · TIN BÁO" in " | ".join(t.replace("THUNG LŨNG KHỦNG KHIẾP · ", "") for t in titles)
    assert any(t.endswith("Phần thứ hai · Chương 2") for t in titles)


def test_table_of_contents_lines_are_not_chapters_and_its_titles_split_the_stories() -> None:
    titles = [c["title"] for c in split_into_chapters_and_sentences(OMNIBUS)]
    assert not any(t.endswith(("198", "207")) for t in titles)  # "Chương 7 Giải đáp 198" is a TOC line
    assert "ABBEY GRANGE" in titles and "HỘI TÓC HUNG" in titles  # each story is its own chapter
    assert titles[0] == "Mở đầu"  # the table of contents itself stays in the preface


def test_roman_and_arabic_chapter_numbers_agree() -> None:
    from src.core.ingestion.parser import tidy_heading

    assert tidy_heading("Chương I") == "Chương 1" and tidy_heading("CHƯƠNG XIV: Biển") == "CHƯƠNG 14: Biển"
    assert tidy_heading("Chương 2") == "Chương 2" and tidy_heading("Chapter Dream") == "Chapter Dream"
