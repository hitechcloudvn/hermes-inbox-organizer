"""VI: Client đọc Gmail — đôi mắt của agent trên hộp thư đến.

Các công cụ đọc lấy về chuỗi/thư để agent soạn thư trả lời từ nội dung email
thực. ``GoogleGmailReader`` bọc Gmail API (google-api-python-client) và cần
OAuth creds thật. Giao thức ``GmailReader`` + bộ phân giải
``account_id -> reader`` là các seam, để các công cụ đọc được kiểm thử đơn vị
bằng một reader giả — không cần creds.

``parse_message`` giải mã một message resource của Gmail thành một dict gọn
gàng, thân thiện với agent (headers + phần thân văn bản thuần).

EN: Gmail read client — the agent's eyes on the inbox.

The read tools fetch threads/messages so the agent can compose a reply from the
actual email content. ``GoogleGmailReader`` wraps the Gmail API
(google-api-python-client) and needs live OAuth creds. The
``GmailReader`` protocol + the ``account_id -> reader`` resolver are seams, so
the read tools are unit-tested with a fake reader — no creds required.

``parse_message`` decodes a Gmail message resource into a compact, agent-friendly
dict (headers + plaintext body).
"""

from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Any, Protocol


def _b64url_decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode(
        "utf-8", "replace"
    )


def _header(headers: list[dict], name: str) -> str:
    for h in headers or []:
        if str(h.get("name", "")).lower() == name.lower():
            return str(h.get("value", ""))
    return ""


def parse_addr(value: str) -> str:
    """VI: Email thuần, viết thường, lấy từ giá trị header ('Alice <a@b.com>' -> 'a@b.com').

    Khóa chuẩn hóa cho sender_profiles + khớp lịch sử. Chuỗi rỗng nếu giá trị
    không có địa chỉ email phân tích được.

    EN: Bare, lowercased email from a header value ('Alice <a@b.com>' -> 'a@b.com').

    The normalized key for sender_profiles + history matching. Empty string if the
    value has no parseable address.
    """
    from email.utils import parseaddr

    return parseaddr(value or "")[1].strip().lower()


def _extract_plain(payload: dict) -> str:
    if payload.get("mimeType") == "text/plain":
        data = (payload.get("body") or {}).get("data")
        if data:
            return _b64url_decode(data)
    for part in payload.get("parts") or []:
        found = _extract_plain(part)
        if found:
            return found
    return ""


def parse_message(msg: dict, *, body_limit: int = 4000) -> dict:
    """VI: Message resource của Gmail -> dict gọn cho agent.

    ``internal_date`` (thời điểm nhận chính thức của Gmail, epoch **ms**) và
    ``label_ids`` được đưa ra cho bộ lọc cửa sổ chính xác của bản tổng hợp và
    ánh xạ nhãn->danh mục; cả hai mặc định là giá trị rỗng vô hại để các caller
    hiện tại (parse phần thân đầy đủ không có ``internalDate``/``labelIds``) không
    bị ảnh hưởng.

    Các header danh sách thư hàng loạt được đưa ra cho bộ phân loại marketing
    dạng giá trị dẫn xuất (boolean ``list_unsubscribe``/``one_click_unsubscribe``
    + ``precedence`` đã chuẩn hóa); các parse định dạng metadata, vốn bỏ qua các
    header đó, mặc định chúng vô hại.

    EN: Gmail message resource -> compact dict for the agent.

    ``internal_date`` (Gmail's authoritative receive time, epoch **ms**) and
    ``label_ids`` are surfaced for the rollup's exact-window filter and
    label->category mapping; both default to a benign empty value so existing
    callers (full-body parses without ``internalDate``/``labelIds``) are
    unaffected.

    Bulk-mail list headers are surfaced for the marketing classifier as derived
    values (``list_unsubscribe``/``one_click_unsubscribe`` booleans + a
    normalized ``precedence``); metadata-format parses, which omit those
    headers, default them benign.
    """
    payload = msg.get("payload") or {}
    headers = payload.get("headers") or []
    try:
        internal_date = int(msg.get("internalDate") or 0)
    except (TypeError, ValueError):
        internal_date = 0
    return {
        "id": msg.get("id", ""),
        "thread_id": msg.get("threadId", ""),
        "from": _header(headers, "from"),
        "to": _header(headers, "to"),
        "cc": _header(headers, "cc"),
        "subject": _header(headers, "subject"),
        "date": _header(headers, "date"),
        "snippet": msg.get("snippet", ""),
        "body": _extract_plain(payload)[:body_limit],
        "internal_date": internal_date,
        "label_ids": list(msg.get("labelIds") or []),
        # Booleans/normalized tokens (never raw header text) so classifier
        # prompts can cite these without echoing untrusted content.
        "list_unsubscribe": bool(_header(headers, "list-unsubscribe")),
        "one_click_unsubscribe": bool(_header(headers, "list-unsubscribe-post")),
        "precedence": _header(headers, "precedence").strip().lower(),
    }


class GmailReader(Protocol):
    """VI: Giao thức truy cập Gmail (chuỗi, thư, nhãn) mà các công cụ đọc sử dụng.

    EN: The Gmail access protocol (threads, messages, labels) used by the read tools.
    """

    def get_thread(self, thread_id: str) -> dict:
        """VI: Lấy một chuỗi theo thread_id.

        EN: Fetch a thread by its thread id.
        """
        ...
    def list_messages(self, query: str, max_results: int) -> list[dict]:
        """VI: Liệt kê tối đa max_results thư khớp truy vấn Gmail.

        EN: List up to max_results messages matching a Gmail query.
        """
        ...
    def list_messages_page(
        self, query: str, max_results: int, page_token: str | None = None
    ) -> dict:
        """VI: Liệt kê một trang thư khớp truy vấn, kèm token phân trang.

        EN: List one page of messages matching a query, with the page token.
        """
        ...
    def get_message(self, message_id: str, format: str = "full") -> dict:
        """VI: Lấy một thư theo message_id với định dạng chỉ định.

        EN: Fetch a single message by id in the requested format.
        """
        ...
    def list_labels(self) -> list[dict]:
        """VI: Liệt kê mọi nhãn trong hộp thư.

        EN: List all labels in the mailbox.
        """
        ...


# Seam: account_id -> reader, or None when the account isn't connected yet.
ResolveReader = Callable[[str], GmailReader | None]


def reader_from_token(tok: Any) -> GoogleGmailReader:
    """VI: Xây một reader trực tiếp từ AccountToken đã lưu (creds tự động làm mới).

    Import google lười; cần cài deps [live]. Không được kiểm thử đơn vị.

    EN: Build a live reader from a stored AccountToken (auto-refreshing creds).

    Lazy google imports; needs the [live] deps installed. Not unit-tested.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        None,
        refresh_token=tok.refresh_token,
        client_id=tok.client_id,
        client_secret=tok.client_secret,
        token_uri=tok.token_uri,
        scopes=list(tok.scopes),
    )
    return GoogleGmailReader(build("gmail", "v1", credentials=creds))


class GoogleGmailReader:
    """VI: Reader trực tiếp trên Gmail API. Cần OAuth creds; không được kiểm thử đơn vị.

    EN: Live reader over the Gmail API. Needs OAuth creds; not unit-tested.
    """

    def __init__(self, service: Any) -> None:
        self._svc = service  # googleapis gmail "users" resource

    def get_thread(self, thread_id: str) -> dict:
        """VI: Lấy một chuỗi ở định dạng đầy đủ theo thread_id.

        EN: Fetch a full-format thread by its thread id.
        """
        return (
            self._svc.users()
            .threads()
            .get(userId="me", id=thread_id, format="full")
            .execute()
        )

    def list_messages(self, query: str, max_results: int) -> list[dict]:
        """VI: Liệt kê các thư khớp truy vấn Gmail (tối đa max_results).

        EN: List messages matching a Gmail query (up to max_results).
        """
        resp = (
            self._svc.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_results)
            .execute()
        )
        return resp.get("messages", []) or []

    def list_messages_page(
        self, query: str, max_results: int, page_token: str | None = None
    ) -> dict:
        """VI: Một trang của messages.list, envelope thô.

        Trả về ``{messages, nextPageToken, resultSizeEstimate}`` để caller có
        thể phân trang + tính tín hiệu cắt bớt (``list_messages`` trả về list
        sẽ loại token/estimate).

        EN: One page of a messages.list, raw envelope.

        Returns ``{messages, nextPageToken, resultSizeEstimate}`` so the caller
        can page + compute a truncation signal (the list-returning
        ``list_messages`` drops the token/estimate).
        """
        return (
            self._svc.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=max_results,
                pageToken=page_token,
            )
            .execute()
        )

    def get_message(self, message_id: str, format: str = "full") -> dict:
        """VI: Lấy một thư theo message_id với định dạng chỉ định (đầy đủ theo mặc định).

        EN: Fetch a message by id in the given format (full by default).
        """
        kwargs: dict[str, Any] = {"userId": "me", "id": message_id, "format": format}
        if format == "metadata":
            # Headers we actually use; trims the payload (no body). "To" is needed by
            # the sent-mail backfill to rank recipients (Gmail omits unlisted headers);
            # the rollup/list paths simply ignore it.
            kwargs["metadataHeaders"] = ["From", "To", "Subject", "Date"]
        return self._svc.users().messages().get(**kwargs).execute()

    def list_labels(self) -> list[dict]:
        """VI: Mọi nhãn của hộp thư (chỉ đọc). Dùng để ánh xạ label_ids -> danh mục.

        EN: All labels for the mailbox (read-only). Used to map label_ids -> category.
        """
        return (
            self._svc.users()
            .labels()
            .list(userId="me")
            .execute()
            .get("labels", [])
            or []
        )


def service_from_token(tok: Any) -> Any:
    """VI: Xây một Gmail API service tự động làm mới từ AccountToken đã lưu.

    EN: Build an auto-refreshing Gmail API service from a stored AccountToken.
    """
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials(
        None,
        refresh_token=tok.refresh_token,
        client_id=tok.client_id,
        client_secret=tok.client_secret,
        token_uri=tok.token_uri,
        scopes=list(tok.scopes),
    )
    return build("gmail", "v1", credentials=creds)


def build_reply_headers(thread: dict, account_email: str) -> dict:
    """VI: Suy ra các header trả lời từ một chuỗi: mục tiêu = thư cuối cùng không phải từ chúng ta.

    EN: Derive reply headers from a thread: target = last message not from us.
    """
    msgs = thread.get("messages", []) or []
    target = None
    for m in reversed(msgs):
        hdrs = (m.get("payload") or {}).get("headers") or []
        if account_email.lower() not in _header(hdrs, "from").lower():
            target = m
            break
    if target is None and msgs:
        target = msgs[-1]
    hdrs = (target.get("payload") or {}).get("headers") or [] if target else []
    subject = _header(hdrs, "subject")
    msg_id = _header(hdrs, "message-id")
    references = _header(hdrs, "references")
    return {
        "to": _header(hdrs, "from"),
        "subject": subject if subject.lower().startswith("re:") else f"Re: {subject}",
        "in_reply_to": msg_id,
        "references": (f"{references} {msg_id}".strip() if references else msg_id),
    }


class GmailDraftWriter:
    """VI: Tạo một nháp trả lời Gmail thật trên một chuỗi ('đôi tay'). Cần creds thật.

    Tạo một nháp mỗi lần gọi; tính idempotent được thực thi phía trên bởi sổ nháp
    (bảng ``draft_requests`` — xem ``db.py`` / ``draft_trigger``).

    EN: Creates a real Gmail draft reply on a thread (the 'hands'). Needs live creds.

    Creates a draft per call; idempotency is enforced upstream by the draft
    ledger (the ``draft_requests`` table — see ``db.py`` / ``draft_trigger``).
    """

    def __init__(self, service: Any, account_email: str) -> None:
        self._svc = service
        self._email = account_email

    def _build_reply_raw(self, thread_id: str, body: str) -> str:
        """Build the base64url MIME reply for a thread (shared by create + update)."""
        import base64
        from email.mime.text import MIMEText

        thread = (
            self._svc.users()
            .threads()
            .get(
                userId="me",
                id=thread_id,
                format="metadata",
                metadataHeaders=["From", "To", "Subject", "Message-ID", "References"],
            )
            .execute()
        )
        h = build_reply_headers(thread, self._email)
        mime = MIMEText(body, "plain", "utf-8")
        mime["From"] = self._email
        mime["To"] = h["to"]
        mime["Subject"] = h["subject"]
        if h["in_reply_to"]:
            mime["In-Reply-To"] = h["in_reply_to"]
            mime["References"] = h["references"]
        return base64.urlsafe_b64encode(mime.as_bytes()).decode()

    def create_draft(self, *, account_id: str, thread_id: str, body: str) -> str:
        """VI: Tạo một nháp trả lời MIME trên chuỗi và trả về draft id.

        EN: Create a MIME reply draft on the thread and return its draft id.
        """
        raw = self._build_reply_raw(thread_id, body)
        resp = (
            self._svc.users()
            .drafts()
            .create(userId="me", body={"message": {"raw": raw, "threadId": thread_id}})
            .execute()
        )
        return resp.get("id", "")

    def update_draft(self, *, account_id: str, thread_id: str, body: str, draft_id: str) -> str:
        """VI: Thay thế nội dung một nháp hiện có (``drafts.update``).

        Được gọi khi sổ đã lưu draft id cho chuỗi, để một lần soạn lại
        (retry / re-wake) ghi đè nháp duy nhất thay vì tạo bản trùng trên chuỗi.

        EN: Replace an existing draft's body (``drafts.update``).

        Called when the ledger already holds a draft id for the thread, so a
        re-draft (retry / re-wake) overwrites the one draft instead of creating a
        duplicate on the thread.
        """
        raw = self._build_reply_raw(thread_id, body)
        resp = (
            self._svc.users()
            .drafts()
            .update(userId="me", id=draft_id, body={"message": {"raw": raw, "threadId": thread_id}})
            .execute()
        )
        return resp.get("id", draft_id)


def writer_from_token(tok: Any) -> GmailDraftWriter:
    """VI: Xây một GmailDraftWriter từ AccountToken đã lưu.

    EN: Build a GmailDraftWriter from a stored AccountToken.
    """
    return GmailDraftWriter(service_from_token(tok), tok.email)
