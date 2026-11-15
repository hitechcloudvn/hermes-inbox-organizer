"""VI: Agent tool gốc ``inbox_create_draft``.

Đây là nguyên tử ghi ngược mà Hermes gọi *sau* khi đã soạn xong thư trả lời
bằng ngữ cảnh của riêng nó (vault / trí nhớ Honcho / phụ lục chat). Plugin sở
hữu "đôi tay" Gmail; agent sở hữu lời văn.

Các handler của tool theo đúng hợp đồng Hermes thật
(``hermes_cli/plugins.py`` -> ``PluginContext.register_tool``): một callable
nhận dict ``args`` do LLM cung cấp và trả về một **chuỗi** JSON, không bao giờ
raise ra ngoài handler.

EN: The native ``inbox_create_draft`` agent tool.

This is the write-back primitive Hermes calls *after* it has composed a reply
with its own context (vault / Honcho memory / chat transcripts). The plugin
owns the Gmail "hands"; the agent owns the words.

Tool handlers follow the real Hermes contract
(``hermes_cli/plugins.py`` -> ``PluginContext.register_tool``): a callable that
takes the LLM-supplied ``args`` dict and returns a JSON **string**, and never
raises out of the handler.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class GmailDraftWriter(Protocol):
    """VI: Tạo một nháp trả lời Gmail trên một chuỗi và trả về draft id của nó.

    Lớp triển khai thật bọc Gmail API (``drafts.create`` với thư trả lời MIME +
    header idempotency) — "đôi tay" của agent. Cần OAuth thật để chạy, nên các
    test tiêm một bản giả.

    EN: Creates a Gmail draft reply on a thread and returns its draft id.

    The real implementation wraps the Gmail API (``drafts.create`` with a MIME
    reply + an idempotency header) — the agent's "hands." It needs live OAuth to
    exercise, so tests inject a fake.
    """

    def create_draft(self, *, account_id: str, thread_id: str, body: str) -> str:
        """VI: Tạo nháp trả lời trên chuỗi và trả về draft id.

        EN: Create a reply draft on the thread and return its draft id.
        """
        ...


class UnconfiguredWriter:
    """VI: Writer vô dụng dùng khi register() chạy mà không có cấu hình Gmail thật.

    Giữ ``register(ctx)`` an toàn khi gọi trong tests/CI: tool được gắn dây,
    nhưng gọi nó khi chưa cấu hình sẽ thất bại ồn ào thay vì im lặng.

    EN: Inert writer used when register() runs without live Gmail config.

    Keeps ``register(ctx)`` safe to call in tests/CI: the tool is wired, but
    invoking it without configuration fails loudly rather than silently.
    """

    def create_draft(self, *, account_id: str, thread_id: str, body: str) -> str:
        """VI: Luôn raise RuntimeError vì Gmail chưa được cấu hình.

        EN: Always raises RuntimeError because Gmail is not configured.
        """
        raise RuntimeError("Gmail writer not configured")


class LoggingDraftWriter:
    """VI: Writer chẩn đoán: ghi log nháp đã soạn thay vì đụng vào Gmail.

    Cho phép quan sát agent có tạo ra thư trả lời giàu ngữ cảnh và thực sự gọi
    ``inbox_create_draft`` hay không — không cần nối Gmail OAuth/Pub/Sub.

    EN: Diagnostic writer: logs the composed draft instead of touching Gmail.

    Lets us observe whether the agent produces a context-rich reply and actually
    calls ``inbox_create_draft`` — without needing Gmail OAuth/Pub/Sub wired.
    """

    def create_draft(self, *, account_id: str, thread_id: str, body: str) -> str:
        """VI: Ghi log nội dung nháp và trả về id giả "probe-draft".

        EN: Log the draft body and return the placeholder id "probe-draft".
        """
        logger.info(
            "inbox_create_draft PROBE account=%s thread=%s body=%r",
            account_id,
            thread_id,
            body,
        )
        return "probe-draft"


INBOX_CREATE_DRAFT_SCHEMA: dict[str, Any] = {
    "name": "inbox_create_draft",
    "description": (
        "Create a Gmail draft reply on a thread. Call this after you have "
        "composed the reply text in the user's voice. Drafts are never sent."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": "string",
                "description": "Connected Gmail account id.",
            },
            "thread_id": {
                "type": "string",
                "description": "Gmail thread id to reply on.",
            },
            "body": {"type": "string", "description": "The reply body text."},
        },
        "required": ["account_id", "thread_id", "body"],
    },
}


# Seam: account_id -> writer (live GmailDraftWriter, or a LoggingDraftWriter
# fallback when no account is connected). None => not connected.
ResolveWriter = Callable[[str], GmailDraftWriter | None]
# Seams that close the draft ledger loop (both optional; default no-op so existing
# call sites are unaffected and tests inject fakes).
RecordDraft = Callable[[str, str, str], Any]       # (account_id, thread_id, draft_id) -> persist
LookupDraft = Callable[[str, str], str | None]  # (account_id, thread_id) -> existing draft id | None
# (account_id, thread_id, body, draft_id) -> persist the draft body for the feedback loop
RecordOutcome = Callable[[str, str, str, str], Any]


def make_inbox_create_draft_handler(
    resolve_writer: ResolveWriter,
    *,
    record_draft: RecordDraft | None = None,
    lookup_draft: LookupDraft | None = None,
    record_outcome: RecordOutcome | None = None,
):
    """VI: Dựng closure handler của tool quanh một bộ phân giải account->writer.

    ``record_draft`` ghi lại draft id Gmail đã tạo/cập nhật để sổ của daemon
    được đóng kín (``draft_requests.gmail_draft_id``); lỗi ghi sổ chỉ được log,
    không bao giờ raise (hợp đồng tool). ``lookup_draft`` trả về draft id hiện
    có cho chuỗi để một lần soạn lại CẬP NHẬT nó thay vì tạo bản trùng.
    ``record_outcome`` là điểm ghi lại của vòng phản hồi nháp: được gọi với
    ``(account_id, thread_id, body, draft_id)`` ngay sau ``record_draft`` để nội
    dung nháp được lưu cho việc chấm delta về sau; lỗi cũng chỉ được log và
    không bao giờ raise. Cả ba mặc định là None (no-op) — production nối chúng
    vào DB; các call site và test hiện tại không bị ảnh hưởng.

    EN: Build the tool handler closure over an account->writer resolver.

    ``record_draft`` persists the created/updated Gmail draft id so the daemon's
    ledger is closed (``draft_requests.gmail_draft_id``); a recorder failure is
    logged, never raised (tool contract). ``lookup_draft`` returns an existing
    draft id for the thread so a re-draft UPDATES it rather than creating a
    duplicate. ``record_outcome`` is the draft-feedback-loop capture point: called
    with ``(account_id, thread_id, body, draft_id)`` right after ``record_draft``
    so the draft body is persisted for later delta scoring; a failure is also
    logged and never raised. All three default to None (no-op) — production wires
    them to the DB; existing call sites and tests are unaffected.
    """

    def handler(args: dict, **_kwargs: Any) -> str:
        """VI: Xử lý lời gọi inbox_create_draft: tạo/cập nhật nháp Gmail và ghi sổ.

        EN: Handle the inbox_create_draft call: create/update the Gmail draft and record it.
        """
        a = args or {}
        account_id = a.get("account_id", "")
        thread_id = a.get("thread_id", "")
        body = a.get("body", "")
        if not account_id or not thread_id or not body:
            return json.dumps(
                {"error": "account_id, thread_id and body are required"}
            )
        writer = resolve_writer(account_id)
        if writer is None:
            return json.dumps({"error": f"account not connected: {account_id!r}"})
        try:
            existing = lookup_draft(account_id, thread_id) if lookup_draft else None
            update = getattr(writer, "update_draft", None)
            if existing and update is not None:
                draft_id = update(
                    account_id=account_id, thread_id=thread_id, body=body, draft_id=existing
                )
            else:
                draft_id = writer.create_draft(
                    account_id=account_id, thread_id=thread_id, body=body
                )
        except Exception as exc:  # contract: never raise out of a tool handler
            return json.dumps({"error": f"draft creation failed: {exc}"})
        if record_draft is not None:
            try:
                record_draft(account_id, thread_id, draft_id)
            except Exception:  # recording must never break the tool
                logger.exception(
                    "inbox_create_draft: failed to record draft id for thread %s", thread_id
                )
        if record_outcome is not None:
            try:
                record_outcome(account_id, thread_id, body, draft_id)
            except Exception:  # recording must never break the tool
                logger.exception(
                    "inbox_create_draft: failed to record outcome for thread %s", thread_id
                )
        return json.dumps({"ok": True, "draft_id": draft_id, "thread_id": thread_id})

    return handler
