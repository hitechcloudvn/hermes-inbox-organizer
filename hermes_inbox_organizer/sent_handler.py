"""VI: Di chuyển một chuỗi khi người dùng GỬI: Actioned hoặc Awaiting Reply.

Khi có thư SENT ta hỏi: giờ bạn có đang chờ người kia không? Bạn chỉ
*Actioned* khi đã đóng một chuỗi bị gắn cờ ("1: To Respond") bằng một câu trả
lời kết thúc không còn yêu cầu mở nào (vd. "Cảm ơn, đã nhận"). Trong mọi trường
hợp khác — thư của bạn đặt câu hỏi/đưa yêu cầu, hoặc là một thư gửi mới — bạn
ở trạng thái *Awaiting Reply*. Trả lời luôn xóa cờ "To Respond" vào (bạn không
còn nợ *họ* một phản hồi). Cả hai nhãn đều lưu trữ (skip inbox); áp dụng ở cấp
chuỗi.

EN: Move a thread when the user SENDS: Actioned or Awaiting Reply.

On a SENT message we ask: are you now waiting on the other person? You're
*Actioned* only when you closed out a flagged thread ("1: To Respond") with a
terminal reply that has no open ask (e.g. "Thanks, got it"). In every other case
— your message asks a question/makes a request, or it's a fresh outbound — you're
*Awaiting Reply*. Replying always clears the inbound "To Respond" flag (you no
longer owe *them* a response). Both labels archive (skip inbox); applied
thread-level.
"""

from __future__ import annotations

from typing import Any

from .config import get_config
from .gmail import parse_message
from .labels import category_by_name, label_name
from .modules.base import SentEvent

# Phrases that signal the sender expects a response even without a "?".
_REPLY_CUES = (
    "could you",
    "can you",
    "would you",
    "will you",
    "let me know",
    "any update",
    "when can",
    "when will",
    "get back to me",
    "what do you think",
    "please advise",
    "please confirm",
    "please send",
    "circle back",
    "look forward to hearing",
)


def _label_id(label_ids: dict[str, str], bare_name: str) -> str | None:
    cat = category_by_name(bare_name)
    return label_ids.get(label_name(cat)) if cat else None


def _new_text(body: str) -> str:
    """Just what the user wrote — drop quoted history + signature so an open
    question in the *quoted* original can't masquerade as your own ask."""
    out: list[str] = []
    for ln in (body or "").splitlines():
        s = ln.strip()
        if s.startswith(">"):  # quoted history
            break
        if s in ("--", "-- "):  # signature delimiter
            break
        if s.startswith("On ") and s.rstrip().endswith("wrote:"):  # reply attribution
            break
        out.append(ln)
    return "\n".join(out)


def sent_awaits_reply(body: str) -> bool:
    """VI: True nếu thư vừa gửi của bạn còn câu hỏi/yêu cầu mở (bạn đang chờ trả lời).

    Heuristic văn bản rẻ trên phần không được trích dẫn: một "?" hoặc một dấu
    hiệu yêu cầu. Khi mơ hồ, nghiêng về Awaiting Reply (hướng an toàn, hữu hình).

    EN: True if your just-sent message has an open question/request (you await a reply).

    Cheap text heuristic over the non-quoted portion: a "?" or a request cue.
    Errs toward Awaiting Reply (the safe, visible direction) on ambiguity.
    """
    text = _new_text(body)
    if "?" in text:
        return True
    low = text.lower()
    return any(cue in low for cue in _REPLY_CUES)


def handle_sent(
    *,
    message_id: str,
    account_id: str,
    service: Any,
    label_ids: dict[str, str],
    registry: Any = None,
) -> str:
    """VI: Trả về danh mục được áp cho chuỗi ("Actioned"/"Awaiting Reply").

    Khi có ``registry`` module, kích hoạt ``registry.dispatch_sent`` (observer
    được offload) sau khi chuỗi được di chuyển. ``registry=None`` giữ hành vi cũ
    để việc định tuyến được unit-test không cần module.

    Khi hệ thống nhãn bị tắt (``INBOX_LABELS_ENABLED=0``) việc di chuyển chuỗi bị
    bỏ qua, nhưng SentEvent (mang đích đã tính) vẫn được dispatch để observer —
    vd. vòng phản hồi bản nháp — tiếp tục học từ thư đã gửi.

    EN: Returns the bare category applied to the thread ("Actioned"/"Awaiting Reply").

    When a module ``registry`` is given, fires ``registry.dispatch_sent`` (offloaded
    observers) after the thread is moved. ``registry=None`` preserves the legacy
    behavior so the routing is unit-tested without modules.

    With the label system disabled (``INBOX_LABELS_ENABLED=0``) the thread move is
    skipped, but the SentEvent (carrying the computed target) still dispatches so
    observers — e.g. the draft-feedback loop — keep learning from sent mail.
    """
    msg = (
        service.users().messages().get(userId="me", id=message_id, format="full").execute()
    )
    thread_id = msg.get("threadId")
    if not thread_id:
        return ""
    parsed = parse_message(msg)

    # The presence check needs the thread only when the To Respond label id is
    # known (with the label system disabled, label_ids is empty — skip the read).
    to_respond = _label_id(label_ids, "To Respond")
    to_respond_present = False
    if to_respond:
        thread = (
            service.users().threads().get(userId="me", id=thread_id, format="minimal").execute()
        )
        present: set[str] = set()
        for m in thread.get("messages", []) or []:
            present.update(m.get("labelIds") or [])
        to_respond_present = to_respond in present
    awaits = sent_awaits_reply(parsed.get("body", ""))

    # Actioned only when you closed a flagged thread with no open ask of your own;
    # if your reply asks something (or it's a fresh outbound) you're Awaiting Reply.
    target_name = "Actioned" if (to_respond_present and not awaits) else "Awaiting Reply"

    if get_config().labels_enabled:
        target_id = _label_id(label_ids, target_name)
        if not target_id:
            return ""

        # Clear every other category across the thread (To Respond included — you've
        # replied, so you no longer owe *them* a response) so no stale category like an
        # earlier "2: FYI" lingers beside the new state. Archive too (skip inbox).
        remove = ["INBOX"] + [lid for lid in label_ids.values() if lid != target_id]
        service.users().threads().modify(
            userId="me",
            id=thread_id,
            body={"addLabelIds": [target_id], "removeLabelIds": remove},
        ).execute()
    if registry is not None:
        registry.dispatch_sent(
            SentEvent(
                account_id=account_id,
                message_id=message_id,
                thread_id=thread_id,
                parsed=parsed,
                target_category=target_name,
            )
        )
    return target_name
