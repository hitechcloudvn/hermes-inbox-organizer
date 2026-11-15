"""VI: 8 danh mục đánh số kiểu Fyxer + luật bỏ qua hộp thư đến (chuyển từ bản TS gốc).

Nhãn hiển thị dạng "1: To Respond" … "8: Marketing". Chỉ To Respond + FYI ở lại
hộp thư đến; 3–8 bỏ qua hộp thư đến (lưu trữ). Trình xử lý thư đã gửi sau đó chuyển
các chuỗi sang Actioned (bạn đã trả lời) hoặc Awaiting Reply (bạn đã gửi và đang chờ).

EN: The 8 Fyxer-style numbered categories + skip-inbox rules (ported from the TS baseline).

Labels render as "1: To Respond" … "8: Marketing". Only To Respond + FYI stay in
the inbox; 3–8 skip the inbox (archive). The sent-handler later moves threads to
Actioned (you replied) or Awaiting Reply (you sent and are waiting).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Category:
    """VI: Danh mục phân loại email gồm thứ tự, tên, cờ bỏ qua hộp thư và cờ chỉ do trình xử lý thư đã gửi gán.

    EN: An email category: sort order, name, skip-inbox flag, and a sent-only flag applied by the sent-handler.
    """

    sort_order: int
    name: str  # bare name, e.g. "To Respond"
    skip_inbox: bool
    sent_only: bool = False  # applied ONLY by the sent-handler, never by the classifier


CATEGORIES: list[Category] = [
    Category(1, "To Respond", False),
    Category(2, "FYI", False),
    Category(3, "Comment", True),
    Category(4, "Notification", True),
    Category(5, "Meeting Update", True),
    Category(6, "Awaiting Reply", True, sent_only=True),
    Category(7, "Actioned", True, sent_only=True),
    Category(8, "Marketing", True),
]

CATEGORY_NAMES: list[str] = [c.name for c in CATEGORIES]

# Categories the classifier may assign to INBOUND mail (excludes the sent-side
# states Awaiting Reply / Actioned, which only the sent-handler applies).
CLASSIFIER_CATEGORIES: list[Category] = [c for c in CATEGORIES if not c.sent_only]
CLASSIFIER_CATEGORY_NAMES: list[str] = [c.name for c in CLASSIFIER_CATEGORIES]


def label_name(c: Category) -> str:
    """VI: Tên nhãn Gmail kèm tiền tố số để buộc thứ tự trên thanh bên.

    EN: Gmail label name with the numeric prefix that forces sidebar ordering.
    """
    return f"{c.sort_order}: {c.name}"


def category_by_name(name: str) -> Category | None:
    """VI: Tra cứu danh mục theo tên thuần ("To Respond") hoặc tên có số ("1: To Respond").

    EN: Resolve a bare ("To Respond") or numbered ("1: To Respond") name.
    """
    bare = name.split(":", 1)[-1].strip() if ":" in name else name.strip()
    for c in CATEGORIES:
        if c.name.lower() == bare.lower():
            return c
    return None
