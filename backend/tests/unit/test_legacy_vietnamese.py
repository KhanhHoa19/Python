"""Legacy Vietnamese fonts (VietWare .Vn*): decoding, detection and split-syllable repair.

The RAW strings below are copied from the text layer of a real PDF printed with the VnNCentury2
font (a Vietnamese translation of Sherlock Holmes); EXPECTED strings are what a reader sees.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.ingestion.legacy_vietnamese import (
    decode_legacy_text,
    decode_vietware,
    looks_like_vietware,
    repair_split_syllables,
)
from src.core.ingestion.parser import split_into_chapters_and_sentences
from src.core.ingestion.reader import DocumentReader
from tests.pdf_helpers import build_pdf

# ---------------------------------------------------------------- real samples (raw, expected)
REAL_LINES = [
    ("THUNG LUÄNG KHUÃNG KHIÏËP", "THUNG LŨNG KHỦNG KHIẾP"),
    ("MUÅC LUÅC", "MỤC LỤC"),
    ("CUÖÅC PHÛU LÛU CUÃA SAÁU PHO TÛÚÅNG NAPOLEON", "CUỘC PHƯU LƯU CỦA SÁU PHO TƯỢNG NAPOLEON"),
    ("DAÃI BÙNG LÖËM ÀÖËM", "DẢI BĂNG LỐM ĐỐM"),
    ("HÖÅI TOÁC HUNG", "HỘI TÓC HUNG"),
    ("KEÃ DÕ DAÅNG", "KẺ DỊ DẠNG"),
    ("NHÛÄNG NGHIÏÅP CHUÃ ÚÃ REIGATE", "NHỮNG NGHIỆP CHỦ Ở REIGATE"),
    ("NGÛÚÂI KHAÁCH TROÅ ÀÛÚÅC HÛÚÃNG BÖÍNG LÖÅC", "NGƯỜI KHÁCH TRỌ ĐƯỢC HƯỞNG BỔNG LỘC"),
    ("Phêìn thûá nhêët TÊËN BI KÕCH ÚÃ LÊU ÀAÂI BIRLSTONE.", "Phần thứ nhất TẤN BI KỊCH Ở LÂU ĐÀI BIRLSTONE."),
    ("Holmes xem kyä thanh sùæt vaâ xaác naån nhên.", "Holmes xem kỹ thanh sắt và xác nạn nhân."),
    (
        "- Laäo kia hùèn phaãi coá sûác lûåc phi thûúâng, laäo  Randall böë êëy - anh nhêån xeát.",
        "- Lão kia hẳn phải có sức lực phi thường, lão  Randall bố ấy - anh nhận xét.",
    ),
    (
        "- Àuáng thïë - Hopkins àaáp - chuáng töi àaä thu thêåp  àûúåc möåt vaâi thöng tin vïì laäo vaâ biïët roä "
        "laäo laâ keã hïët sûác cöåc cùçn.",
        "- Đúng thế - Hopkins đáp - chúng tôi đã thu thập  được một vài thông tin về lão và biết rõ lão là kẻ hết "
        "sức cộc cằn.",
    ),
    (
        "- Toám cöí laäo ta, chùæc àöëi vúái öng seä chùèng coá gò khoá khùn.",
        "- Tóm cổ lão ta, chắc đối với ông sẽ chẳng có gì khó khăn.",
    ),
    ("choãng chiïëc thanh cúâi  than bõ cong laåi vò cuá giaáng maånh vaâo àêìu.",
     "chỏng chiếc thanh cời  than bị cong lại vì cú giáng mạnh vào đầu."),
    # the five single-glyph "i" tones, from words the book uses constantly
    ("chñnh thñch chóó mó nghôa vò bõ", "chính thích chỉỉ mỉ nghĩa vì bị"),
]


@pytest.mark.parametrize(("raw", "expected"), REAL_LINES, ids=[r[0][:28] for r in REAL_LINES])
def test_real_sentences_decode_to_readable_vietnamese(raw: str, expected: str) -> None:
    assert decode_vietware(raw) == expected


# ---------------------------------------------------------------- the mapping, class by class


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # plain vowel + horn vowels: á sắc, â huyền, ã hỏi, ä ngã, å nặng
        ("aá aâ aã aä aå", "á à ả ã ạ"),
        ("uá uâ uã uä uå", "ú ù ủ ũ ụ"),
        ("úá úâ úã úä úå", "ớ ờ ở ỡ ợ"),
        ("ûá ûâ ûã ûä ûå", "ứ ừ ử ữ ự"),
        # circumflex â ê ô (written ê ï ö): ë sắc, ì huyền, í hỏi, î ngã, å nặng
        ("êë êì êí êî êå", "ấ ầ ẩ ẫ ậ"),
        ("ïë ïì ïí ïî ïå", "ế ề ể ễ ệ"),
        ("öë öì öí öî öå", "ố ồ ổ ỗ ộ"),
        # breve ă (written ù): æ sắc, ç huyền, è hỏi, é ngã, å nặng
        ("ùæ ùç ùè ùé ùå", "ắ ằ ẳ ẵ ặ"),
        # letters, upper case, and the single-glyph i tones
        ("à ù ê ï ö ú û", "đ ă â ê ô ơ ư"),
        ("À Ù Ê Ï Ö Ú Û", "Đ Ă Â Ê Ô Ơ Ư"),
        ("ñ ò ó ô õ", "í ì ỉ ĩ ị"),
        ("Ñ Ò Ó Ô Õ", "Í Ì Ỉ Ĩ Ị"),
        ("AÁ AÂ AÃ AÄ AÅ", "Á À Ả Ã Ạ"),
    ],
)
def test_every_tone_class(raw: str, expected: str) -> None:
    assert decode_vietware(raw) == expected


def test_ascii_text_is_unchanged() -> None:
    plain = "Hello, world! 3.14 (ok) and Holmes and Watson."
    assert decode_vietware(plain) == plain


def test_real_unicode_vietnamese_must_never_be_decoded_blindly() -> None:
    """decode_vietware turns 'à' into 'đ', which is right for legacy fonts and wrong for Unicode text.
    The reader therefore only calls it after looks_like_vietware() says the text is legacy."""
    unicode_text = UNICODE_VIETNAMESE * 3
    assert not looks_like_vietware(unicode_text)
    assert decode_vietware("và") == "vđ"  # the reason the detection gate exists


def test_a_tone_mark_with_no_vowel_before_it_is_left_alone() -> None:
    assert decode_vietware("n å") == "n å" and decode_vietware("å") == "å"


def test_extractor_space_between_letter_and_tone_is_removed() -> None:
    assert decode_vietware("hiï åu") == "hiệu" and decode_vietware("mö åt") == "một"


# ---------------------------------------------------------------- split syllables


@pytest.mark.parametrize(
    ("split", "fixed"),
    [
        ("t ôi", "tôi"), ("t rong khi", "trong khi"), ("vụ n ày coi", "vụ này coi"),
        ("cho ng ười đến", "cho người đến"),          # "ng" belongs to the NEXT word, not to "cho"
        ("nê n tôi", "nên tôi"), ("đế n High Street", "đến High Street"),
        ("khôn g thể", "không thể"), ("miệ ng tôi", "miệng tôi"), ("ô ng chồng", "ông chồng"),
        ("c ố ý", "cố ý"), ("lắng n ghe mọi", "lắng nghe mọi"), ("đ ược báo", "được báo"),
    ],
)
def test_stray_spaces_inside_syllables_are_removed(split: str, fixed: str) -> None:
    assert repair_split_syllables(split) == fixed


@pytest.mark.parametrize(
    "text",
    ["bạn có khỏe không", "Holmes và Watson", "Hobson's Patch", "số 5 m dài", "Xin chào, tôi là A. B. Nam", "t"],
)
def test_normal_text_is_not_touched_by_the_repair(text: str) -> None:
    assert repair_split_syllables(text) == text


def test_repair_is_idempotent() -> None:
    once = repair_split_syllables("cho ng ười nê n tôi")
    assert repair_split_syllables(once) == once


# ---------------------------------------------------------------- detection

LEGACY_PARAGRAPH = " ".join(raw for raw, _ in REAL_LINES[9:14]) * 2
UNICODE_VIETNAMESE = (
    "Hôm nay trời đẹp, chúng tôi cùng nhau đi dạo trong công viên. Những chiếc lá vàng rơi nhẹ nhàng trên "
    "con đường nhỏ, người già ngồi đọc báo, trẻ em chạy nhảy vui đùa. Tôi nghĩ rằng đây là một buổi sáng "
    "tuyệt vời để bắt đầu công việc nghiên cứu về ngôn ngữ và văn hóa của đất nước chúng ta."
)
FRENCH = (
    "Noël est une fête où la famille se réunit pour partager un repas naïf mais délicieux. Je suis sûr que "
    "tu aimeras la forêt couverte de neige, où les enfants construisent un bonhomme de neige près du château. "
    "Mon frère, très âgé, raconte toujours la même histoire de son enfance à la campagne. "
) * 2
GERMAN = (
    "Die Kinder spielen draußen im Garten, während die Mütter Kuchen backen und über die Ärzte reden. "
    "Wir können morgen früh aufstehen, um über die Brücke zu gehen und die schönen Länder zu besuchen. "
) * 3
SWEDISH = (
    "Vi åker till sjön på sommaren för att fiska och bada. Hon är glad över att vi får åka båt i år. "
    "Barnen leker på ängen medan mormor lagar mat över öppen eld. "
) * 3


def test_legacy_text_is_detected() -> None:
    assert looks_like_vietware(LEGACY_PARAGRAPH)


@pytest.mark.parametrize("text", [UNICODE_VIETNAMESE * 3, FRENCH, GERMAN, SWEDISH, "ngắn", ""], ids=["vi", "fr", "de", "sv", "short", "empty"])
def test_other_text_is_not_mistaken_for_legacy(text: str) -> None:
    assert not looks_like_vietware(text)


def test_decoded_text_is_no_longer_detected_as_legacy() -> None:
    assert not looks_like_vietware(decode_legacy_text(LEGACY_PARAGRAPH))


# ---------------------------------------------------------------- reader end to end


def test_txt_in_a_legacy_font_is_decoded_on_load(tmp_path: Path) -> None:
    path = tmp_path / "cu.txt"
    path.write_text("\n".join(raw for raw, _ in REAL_LINES[9:14]) * 2, encoding="utf-8")
    text, _, _ = DocumentReader.load_document(path)
    assert "Holmes xem kỹ thanh sắt và xác nạn nhân." in text and "ö" not in text


def test_legacy_pdf_is_decoded_cleaned_and_split_into_sentences(tmp_path: Path) -> None:
    """Four pages like the real book: running header with page number, body in legacy encoding,
    a table-of-contents style leader line, and a sentence that continues on the next page."""
    header = "THUNG LUÄNG KHUÃNG KHIÏËP {n}"
    bodies = [
        [REAL_LINES[9][0], REAL_LINES[10][0], REAL_LINES[11][0], "CUÖÅC PHÛU LÛU ............................ 27"],
        [REAL_LINES[12][0], REAL_LINES[13][0], "- Khöng khoá chuát naâo, chuáng töi àaä theo"],
        ["doäi laäo ta suöët àïm.", REAL_LINES[9][0], REAL_LINES[11][0]],
        [REAL_LINES[10][0], REAL_LINES[12][0]],
    ]
    pages = [[header.format(n=i + 1), *body] for i, body in enumerate(bodies)]
    pdf = tmp_path / "sherlock.pdf"
    pdf.write_bytes(build_pdf(pages))

    text, _, _ = DocumentReader.load_document(pdf)
    sentences = [s for c in split_into_chapters_and_sentences(text) for s in c["sentences"]]

    assert "Holmes xem kỹ thanh sắt và xác nạn nhân." in sentences
    assert "THUNG LŨNG KHỦNG KHIẾP" not in text            # running header removed on every page
    assert "ö" not in text and "å" not in text            # nothing left undecoded
    assert "CUỘC PHƯU LƯU 27" in text and "....." not in text  # dotted leader collapsed
    # the sentence cut by the page break is whole again
    assert any(s.endswith("chúng tôi đã theo dõi lão ta suốt đêm.") for s in sentences), sentences
