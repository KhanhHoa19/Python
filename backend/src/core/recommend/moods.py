"""Moods the reader can pick, each mapped to the topic tags (category slugs) that suit it.

A fixed table on purpose: it is easy to explain ("Hồi hộp" = Trinh thám, Kinh dị, Phiêu lưu) and needs no labelling of
every book. apps/web and apps/desktop read the list from the API, so there is one source of truth."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Mood:
    id: str
    label: str
    categories: tuple[str, ...]  # category slugs


MOODS: tuple[Mood, ...] = (
    Mood("thu-gian", "Thư giãn", ("truyen-ngan", "thieu-nhi", "tinh-cam", "tieu-thuyet")),
    Mood("hoi-hop", "Hồi hộp", ("trinh-tham", "kinh-di", "phieu-luu")),
    Mood("suy-ngam", "Suy ngẫm", ("triet-hoc", "tam-ly", "lich-su")),
    Mood("hoc-hoi", "Học hỏi", ("khoa-hoc", "cong-nghe", "kinh-te", "ky-nang-song")),
    Mood("lang-man", "Lãng mạn", ("tinh-cam", "tieu-thuyet")),
    Mood("vui-ve", "Vui vẻ", ("thieu-nhi", "phieu-luu", "truyen-ngan")),
)


def mood_by_id(mood_id: str | None) -> Mood | None:
    return next((m for m in MOODS if m.id == mood_id), None)
