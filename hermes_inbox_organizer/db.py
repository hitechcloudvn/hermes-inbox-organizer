"""VI: Lưu trữ SQLite — kết nối, schema và các accessor có kiểu.

Thay thế trạng thái file phẳng trước đó (history cursor ``cursor-<email>.txt`` và
sổ nháp ``drafted-threads.txt``) bằng một SQLite DB duy nhất, và thêm các bảng vận
hành mà phần hardening còn lại cần (classified messages, thread state). DB nằm ở
``<INBOX_DATA_DIR>/state.db`` — trong volume ``/opt/data`` của Hermes, nên nó tồn
tại qua các lần khởi động lại / ``docker compose up``.

Xử lý kết nối phỏng theo các SQLite plugin của Hermes (``hermes_cli/kanban_db``):
autocommit (``isolation_level=None``), hàng dạng ``sqlite3.Row``, WAL +
``foreign_keys=ON``, và một init ``CREATE TABLE IF NOT EXISTS`` idempotent được
cache theo đường dẫn. Mẫu khóa ghi ``BEGIN IMMEDIATE`` mà kanban dùng để claim
task cũng chính là mẫu mà hàng đợi/thuê job theo tài khoản backed-by-DB tương lai
sẽ dùng.

Module này chỉ dùng ``sqlite3`` stdlib nên unit test chạy mà không cần Hermes.
Thiết kế một-chủ-sở-hữu: các bảng khóa theo ``account`` (email) — không có bảng
users/auth (agent được gate theo chủ sở hữu) và nhãn vẫn là hằng số code.

EN: SQLite persistence — connection, schema, and typed accessors.

Replaces the earlier flat-file state (``cursor-<email>.txt`` history cursors and
the ``drafted-threads.txt`` draft ledger) with one SQLite DB, and adds the
operational tables the rest of the hardening work needs (classified messages,
thread state). The DB lives at ``<INBOX_DATA_DIR>/state.db`` — inside the Hermes
``/opt/data`` volume, so it persists across restarts / ``docker compose up``.

Connection handling mirrors Hermes's own SQLite plugins (``hermes_cli/kanban_db``):
autocommit (``isolation_level=None``), ``sqlite3.Row`` rows, WAL + ``foreign_keys=ON``,
and an idempotent ``CREATE TABLE IF NOT EXISTS`` init cached per path. The
``BEGIN IMMEDIATE`` write-lock pattern kanban uses for task claiming is the same
one the future DB-backed per-account job queue/leasing will use.

The module is pure stdlib ``sqlite3`` so the unit tests run without Hermes.
Single-owner design: tables are keyed by ``account`` (the email) — there is no
users/auth table (the agent is owner-gated) and labels stay code constants.
"""

from __future__ import annotations

import contextlib
import sqlite3
import time
from pathlib import Path
from typing import Any, TypedDict, cast

from .config import get_config

# ── Row shapes ────────────────────────────────────────────────────────────────
# Row-returning accessors hand back plain dicts (one per row), typed with these
# TypedDicts, so call sites get static key-checking + autocomplete on row["col"]
# without taking on an ORM dependency. The DB still uses sqlite3.Row internally
# (``connect`` sets row_factory); :func:`_as_dict`/:func:`_as_dicts` convert at the
# accessor boundary. ``Optional[...]`` marks columns that are NULLable in the schema.
# (Editor-level today — no type checker is wired in CI; see README/dev notes.)


class DraftRequestRow(TypedDict):
    account: str
    thread_id: str
    gmail_draft_id: str | None
    from_addr: str | None
    subject: str | None
    attempts: int
    last_attempt_ms: int | None
    created_at_ms: int


class ThreadStateRow(TypedDict):
    account: str
    thread_id: str
    last_message_id: str
    last_category: str
    last_processed_at_ms: int


class SenderProfileRow(TypedDict):
    account: str
    sender_email: str
    display_name: str | None
    relationship: str | None
    voice_notes: str | None
    tone_hints: str | None
    learned_notes: str | None
    learned_updated_ms: int | None
    draft_count: int
    last_drafted_at_ms: int | None
    source: str | None
    updated_at_ms: int


class DraftOutcomeRow(TypedDict):
    account: str
    thread_id: str
    sender_email: str | None
    gmail_draft_id: str | None
    draft_body: str | None
    draft_created_ms: int | None
    sent_message_id: str | None
    sent_body: str | None
    sent_at_ms: int | None
    outcome: str
    similarity: int | None
    learned: int
    learned_at_ms: int | None
    updated_at_ms: int


class DraftLessonRow(TypedDict):
    lesson_id: int
    account: str
    scope: str
    polarity: str
    rule: str
    norm_rule: str
    evidence_count: int
    active: int
    created_at_ms: int
    last_seen_ms: int


class TrackedPackageRow(TypedDict):
    account: str
    tracking_number: str
    carrier: int | None
    registered: int
    last_stage: str | None
    last_notified_stage: str | None
    terminal: int
    created_at_ms: int
    updated_at_ms: int


class LearnedNoteSummaryRow(TypedDict):
    # A privacy-preserving projection of sender_profiles for the status tool: the
    # LENGTH of the learned note, never its text (avoids echoing fenced content).
    account: str
    sender_email: str
    note_chars: int | None
    updated_ms: int | None


def _as_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    """sqlite3.Row -> plain dict (or None), the single-row accessor boundary."""
    return dict(row) if row is not None else None


def _as_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """sqlite3.Row list -> list of plain dicts, the multi-row accessor boundary."""
    return [dict(r) for r in rows]


_SCHEMA_VERSION = 3

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS accounts (
    account                   TEXT PRIMARY KEY,            -- email; the per-account key everywhere
    history_cursor            TEXT,                        -- Gmail history id (was cursor-<email>.txt)
    watch_expiration_ms       INTEGER,
    last_pull_at_ms           INTEGER,
    paused                    INTEGER NOT NULL DEFAULT 0,
    paused_reason             TEXT,
    openrouter_consent_at_ms  INTEGER,
    cost_usd_micros_today     INTEGER NOT NULL DEFAULT 0,
    cost_window_start_ms      INTEGER,
    updated_at_ms             INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS draft_requests (
    account         TEXT NOT NULL,
    thread_id       TEXT NOT NULL,
    gmail_draft_id  TEXT,                                  -- set once the draft is created (fulfilment = idempotency)
    from_addr       TEXT,                                  -- stored on claim so the retry loop can rebuild the wake
    subject         TEXT,
    attempts        INTEGER NOT NULL DEFAULT 0,            -- dispatch attempts; capped by MAX_DRAFT_ATTEMPTS
    last_attempt_ms INTEGER,                               -- last dispatch time; in-flight window = within RETRY_TTL_MS
    created_at_ms   INTEGER NOT NULL,
    PRIMARY KEY (account, thread_id)
);

CREATE TABLE IF NOT EXISTS classified_messages (
    account              TEXT NOT NULL,
    message_id           TEXT NOT NULL,
    thread_id            TEXT NOT NULL,
    from_addr            TEXT NOT NULL DEFAULT '',
    subject              TEXT NOT NULL DEFAULT '',
    category             TEXT NOT NULL,
    confidence           INTEGER NOT NULL DEFAULT 0,
    source               TEXT NOT NULL DEFAULT 'llm',      -- 'pre' | 'llm'
    llm_input_tokens     INTEGER,
    llm_output_tokens    INTEGER,
    llm_cost_usd_micros  INTEGER,
    classified_at_ms     INTEGER NOT NULL,
    PRIMARY KEY (account, message_id)
);
CREATE INDEX IF NOT EXISTS idx_cm_account_classified_at ON classified_messages (account, classified_at_ms);
CREATE INDEX IF NOT EXISTS idx_cm_account_thread        ON classified_messages (account, thread_id);

CREATE TABLE IF NOT EXISTS thread_state (
    account               TEXT NOT NULL,
    thread_id             TEXT NOT NULL,
    last_message_id       TEXT NOT NULL,
    last_category         TEXT NOT NULL,
    last_processed_at_ms  INTEGER NOT NULL,
    PRIMARY KEY (account, thread_id)
);

-- Generic once-only dedup for notifying modules (e.g. the 2FA module keys on
-- message_id so a Pub/Sub redelivery or the poll reconciler re-draining the
-- same message notifies exactly once). dedup_key MUST NOT contain a secret or
-- PII (never the 2FA code itself) — key on message_id. Mirrors the
-- draft_requests check-then-insert dedup pattern.
CREATE TABLE IF NOT EXISTS module_notified (
    module          TEXT NOT NULL,
    account         TEXT NOT NULL,
    dedup_key       TEXT NOT NULL,
    notified_at_ms  INTEGER NOT NULL,
    PRIMARY KEY (module, account, dedup_key)
);

-- Packages the shipping module is tracking via 17track. Polled (no webhooks:
-- no public ingress). ``last_notified_stage`` advances ONLY after a successful
-- push (so a failed notify re-fires next poll). ``terminal`` (delivered /
-- exception / expired) drops a parcel out of the poll set. Keyed on
-- (account, tracking_number) so repeat emails about the same parcel are no-ops.
CREATE TABLE IF NOT EXISTS tracked_packages (
    account              TEXT NOT NULL,
    tracking_number      TEXT NOT NULL,
    carrier              INTEGER,                      -- 17track carrier id; NULL = auto-detect
    registered           INTEGER NOT NULL DEFAULT 0,   -- 1 once 17track accepted it
    last_stage           TEXT,                         -- normalized stage from the last poll
    last_notified_stage  TEXT,                         -- last stage actually pushed (B3)
    terminal             INTEGER NOT NULL DEFAULT 0,   -- stop polling
    created_at_ms        INTEGER NOT NULL,
    updated_at_ms        INTEGER NOT NULL,
    PRIMARY KEY (account, tracking_number)
);
CREATE INDEX IF NOT EXISTS idx_pkg_active ON tracked_packages (registered, terminal);

-- Per-correspondent voice/relationship profile feeding the drafting brief. Keyed
-- by the normalized sender email (bare, lowercased). Seeded by the sent-mail
-- backfill (source='backfill') and refined by the agent (source='agent'). A new
-- table, so it is created via SCHEMA_SQL on the next connect (no version bump).
CREATE TABLE IF NOT EXISTS sender_profiles (
    account             TEXT NOT NULL,
    sender_email        TEXT NOT NULL,            -- normalized: bare lowercased address
    display_name        TEXT,
    relationship        TEXT,
    voice_notes         TEXT,                     -- how the owner writes to this person (backfill/agent layer)
    tone_hints          TEXT,
    learned_notes       TEXT,                     -- learned-from-edits layer (draft feedback); never overwrites voice_notes
    learned_updated_ms  INTEGER,
    draft_count         INTEGER NOT NULL DEFAULT 0,
    last_drafted_at_ms  INTEGER,
    source              TEXT,                      -- 'backfill' | 'agent' | 'manual'
    updated_at_ms       INTEGER NOT NULL,
    PRIMARY KEY (account, sender_email)
);

-- Draft feedback loop: the draft<->sent pairing ledger + gold-example store. Kept
-- separate from draft_requests so the hot claim/retry row is not widened with large
-- bodies or a second lifecycle. Keyed (account, thread_id). A new table, so it is
-- created via SCHEMA_SQL on the next connect even on an existing DB. ``draft_body``
-- is what WE wrote (captured at inbox_create_draft); ``sent_body`` is what actually
-- went out (owner prose, quotes stripped) = the gold example. ``outcome`` is the
-- classification; ``learned`` flips to 1 once distilled/applied. ``sender_email`` is
-- the normalized inbound correspondent we replied TO.
CREATE TABLE IF NOT EXISTS draft_outcomes (
    account           TEXT NOT NULL,
    thread_id         TEXT NOT NULL,
    sender_email      TEXT,                 -- normalized correspondent we replied TO
    gmail_draft_id    TEXT,
    draft_body        TEXT,                 -- what WE wrote (captured at inbox_create_draft); NULL for capture-all-sent rows
    draft_created_ms  INTEGER,
    sent_message_id   TEXT,                 -- the owner's SENT message on this thread, if any
    sent_body         TEXT,                 -- what actually went out (owner prose, quotes stripped) = the gold example
    sent_at_ms        INTEGER,
    outcome           TEXT NOT NULL DEFAULT 'pending',
                       -- 'pending'|'sent_verbatim'|'sent_edited'|'sent_ignored'|'no_reply'|'sent_no_draft'
    similarity        INTEGER,              -- 0-100 draft<->sent (cheap local metric); NULL when no draft
    learned           INTEGER NOT NULL DEFAULT 0,   -- 1 once distilled/applied
    learned_at_ms     INTEGER,
    updated_at_ms     INTEGER NOT NULL,
    PRIMARY KEY (account, thread_id)
);
CREATE INDEX IF NOT EXISTS idx_do_learn_queue ON draft_outcomes (learned, outcome);
CREATE INDEX IF NOT EXISTS idx_do_examples    ON draft_outcomes (account, sender_email, sent_at_ms);
CREATE INDEX IF NOT EXISTS idx_do_pending     ON draft_outcomes (outcome, draft_created_ms);

-- Draft feedback loop: global learned do/don't rules distilled from draft<->sent
-- deltas. ``norm_rule`` (lowercased/trimmed) is the dedup key; a repeat rule bumps
-- ``evidence_count`` + ``last_seen_ms`` instead of inserting. ``active=0`` is a
-- soft-disable (revert affordance / prune). ``scope`` reserves room for
-- category/sender lessons later; v1 ships 'global' only.
CREATE TABLE IF NOT EXISTS draft_lessons (
    lesson_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    account        TEXT NOT NULL,
    scope          TEXT NOT NULL DEFAULT 'global',  -- room for 'category'/'sender' later
    polarity       TEXT NOT NULL,                   -- 'do' | 'dont'
    rule           TEXT NOT NULL,
    norm_rule      TEXT NOT NULL,                   -- lowercased/trimmed for dedup
    evidence_count INTEGER NOT NULL DEFAULT 1,
    active         INTEGER NOT NULL DEFAULT 1,      -- soft-disable = revert
    created_at_ms  INTEGER NOT NULL,
    last_seen_ms   INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_lesson_dedup ON draft_lessons (account, scope, polarity, norm_rule);
CREATE INDEX IF NOT EXISTS idx_lesson_rank ON draft_lessons (account, active, evidence_count DESC, last_seen_ms DESC);

-- Dashboard connect flow: short-lived PKCE pending state. The web dashboard runs
-- in a SEPARATE process from the gateway/daemon, so the in-memory
-- ``oauth.PendingStore`` the chat connect tools use is unreachable there — the
-- ``code_verifier`` is stashed here between connect/start and connect/complete
-- instead. Single-owner: keyed by the opaque ``state`` only (no sender). Holds NO
-- token/PII, just the short-lived verifier; consumed single-use + swept by TTL. A
-- new table, so it is created via CREATE TABLE IF NOT EXISTS on the next connect
-- (no schema-version bump needed).
CREATE TABLE IF NOT EXISTS oauth_pending (
    state          TEXT PRIMARY KEY,
    verifier       TEXT NOT NULL,
    created_at_ms  INTEGER NOT NULL
);
"""

_INITIALIZED_PATHS: set[str] = set()


def now_ms() -> int:
    """VI: Trả về thời điểm hiện tại tính bằng mili giây từ epoch.

    EN: Return the current epoch time in milliseconds.
    """
    return int(time.time() * 1000)


def default_db_path() -> Path:
    """VI: Đường dẫn tới state.db của plugin lấy từ cấu hình.

    EN: Path to the plugin's state.db from the config.
    """
    return Path(get_config().db_path)


def _apply_wal(conn: sqlite3.Connection) -> None:
    # WAL lets the daemon read while a writer holds the lock. On a WAL-incompatible
    # filesystem (NFS/SMB/FUSE) SQLite silently keeps the existing journal mode —
    # correctness is unaffected, only write concurrency degrades, so we don't fail.
    with contextlib.suppress(sqlite3.OperationalError):
        conn.execute("PRAGMA journal_mode=WAL")


def _migrate(conn: sqlite3.Connection) -> None:
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version >= _SCHEMA_VERSION:
        return
    if version < 2:
        # v2: draft_requests grows retry/idempotency columns. Additive ALTERs so an
        # existing v1 state.db upgrades in place; a fresh DB already has them from
        # SCHEMA_SQL, so add only what's missing. Forward-only + rollback-safe (a v1
        # image sees user_version>=1 and no-ops; the extra columns go unused).
        existing = {r[1] for r in conn.execute("PRAGMA table_info(draft_requests)")}
        for col, decl in (
            ("from_addr", "TEXT"),
            ("subject", "TEXT"),
            ("attempts", "INTEGER NOT NULL DEFAULT 0"),
            ("last_attempt_ms", "INTEGER"),
        ):
            if col not in existing:
                conn.execute(f"ALTER TABLE draft_requests ADD COLUMN {col} {decl}")
    if version < 3:
        # v3: the draft-feedback loop. ``draft_outcomes``/``draft_lessons`` are new
        # tables (created by SCHEMA_SQL on this first touch, so no ALTER needed), but
        # sender_profiles gains the learned-from-edits columns — additive ALTERs so an
        # existing v2 state.db upgrades in place. The guard is REQUIRED: a fresh DB
        # already has these from SCHEMA_SQL above, so an unguarded ALTER would hit
        # "duplicate column" and crash the daemon on boot.
        existing = {r[1] for r in conn.execute("PRAGMA table_info(sender_profiles)")}
        for col, decl in (("learned_notes", "TEXT"), ("learned_updated_ms", "INTEGER")):
            if col not in existing:
                conn.execute(f"ALTER TABLE sender_profiles ADD COLUMN {col} {decl}")
    conn.execute(f"PRAGMA user_version = {_SCHEMA_VERSION}")


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """VI: Mở (và lần chạm đầu tiên: khởi tạo) DB của plugin.

    Kết nối đầu tiên tới một đường dẫn chạy schema + migrations; các kết nối sau
    tới cùng đường dẫn trong tiến trình này bỏ qua qua cache module.

    EN: Open (and on first touch, initialize) the plugin DB.

    The first connection to a given path runs the schema + migrations; later
    connections to the same path in this process skip it via a module cache.
    """
    path = Path(db_path) if db_path is not None else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = str(path.resolve())
    needs_init = resolved not in _INITIALIZED_PATHS

    conn = sqlite3.connect(str(path), isolation_level=None, timeout=30)
    conn.row_factory = sqlite3.Row
    _apply_wal(conn)
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA foreign_keys=ON")

    if needs_init:
        conn.executescript(SCHEMA_SQL)
        _migrate(conn)
        _INITIALIZED_PATHS.add(resolved)
    return conn


# ── Accounts: history cursor (replaces cursor-<email>.txt) ──────────────────────

def get_cursor(conn: sqlite3.Connection, account: str) -> str | None:
    """VI: Trả về history cursor đã lưu của tài khoản, hoặc None.

    EN: Return the account's stored history cursor, or None.
    """
    row = conn.execute(
        "SELECT history_cursor FROM accounts WHERE account = ?", (account,)
    ).fetchone()
    return row["history_cursor"] if row and row["history_cursor"] is not None else None


def set_cursor(conn: sqlite3.Connection, account: str, history_id: str) -> None:
    """VI: Lưu history cursor cho một tài khoản (upsert).

    EN: Store the history cursor for an account (upsert).
    """
    conn.execute(
        """INSERT INTO accounts (account, history_cursor, updated_at_ms)
                VALUES (?, ?, ?)
           ON CONFLICT(account) DO UPDATE SET history_cursor = excluded.history_cursor,
                                              updated_at_ms  = excluded.updated_at_ms""",
        (account, history_id, now_ms()),
    )


def get_account_updated_ms(conn: sqlite3.Connection, account: str) -> int | None:
    """VI: ``accounts.updated_at_ms`` của một tài khoản (None nếu không biết).

    Được :func:`set_cursor` đẩy lên sau mỗi lần drain thành công, nên nó kiêm luôn
    tín hiệu "hộp thư đã được theo dõi tới đây" — sweep no_reply của vòng phản hồi
    nháp đọc nó cho kiểm tra liveness M1 (không đánh dấu sai trong lúc mất token).

    EN: ``accounts.updated_at_ms`` for an account (None if unknown).

    Bumped by :func:`set_cursor` after every successful drain, so it doubles as a
    "the mailbox was watched through here" signal — the draft-feedback no_reply sweep
    reads it for its M1 liveness check (don't false-mark during a token outage).
    """
    row = conn.execute(
        "SELECT updated_at_ms FROM accounts WHERE account = ?", (account,)
    ).fetchone()
    return row["updated_at_ms"] if row is not None else None


# ── Draft requests (replaces the drafted-threads.txt ledger) ────────────────────

def draft_already_requested(conn: sqlite3.Connection, account: str, thread_id: str) -> bool:
    """VI: True nếu đã có một dòng draft_requests cho chuỗi này.

    EN: True if a draft_requests row already exists for this thread.
    """
    return conn.execute(
        "SELECT 1 FROM draft_requests WHERE account = ? AND thread_id = ?",
        (account, thread_id),
    ).fetchone() is not None


def mark_draft_requested(conn: sqlite3.Connection, account: str, thread_id: str) -> None:
    """VI: Ghi dấu đã yêu cầu nháp cho một chuỗi (idempotent).

    EN: Mark a draft as requested for a thread (idempotent).
    """
    conn.execute(
        "INSERT OR IGNORE INTO draft_requests (account, thread_id, created_at_ms) VALUES (?, ?, ?)",
        (account, thread_id, now_ms()),
    )


def set_draft_id(conn: sqlite3.Connection, account: str, thread_id: str, gmail_draft_id: str) -> None:
    """VI: Ghi draft id Gmail đã tạo (idempotency bền vững, không chỉ là dấu đã yêu cầu).

    EN: Record the created Gmail draft id (durable idempotency past the request mark).
    """
    conn.execute(
        """INSERT INTO draft_requests (account, thread_id, gmail_draft_id, created_at_ms)
                VALUES (?, ?, ?, ?)
           ON CONFLICT(account, thread_id) DO UPDATE SET gmail_draft_id = excluded.gmail_draft_id""",
        (account, thread_id, gmail_draft_id, now_ms()),
    )


def get_draft_request(
    conn: sqlite3.Connection, account: str, thread_id: str
) -> DraftRequestRow | None:
    """VI: Dòng draft_requests của một chuỗi, hoặc None.

    EN: The draft_requests row for a thread, or None.
    """
    row = conn.execute(
        "SELECT * FROM draft_requests WHERE account = ? AND thread_id = ?",
        (account, thread_id),
    ).fetchone()
    return cast("DraftRequestRow | None", _as_dict(row))


def claim_draft(
    conn: sqlite3.Connection,
    account: str,
    thread_id: str,
    *,
    ttl_ms: int,
    max_attempts: int,
    now_ms: int,
    from_addr: str = "",
    subject: str = "",
) -> bool:
    """VI: Claim nguyên tử quyền dispatch một nháp cho ``(account, thread_id)``.

    Trả về True cho đúng MỘT caller mỗi cửa sổ đủ điều kiện. Một UPSERT có điều
    kiện duy nhất (phỏng theo :func:`note_once`) để mọi đường dẫn dispatch —
    ``_dedup_wake`` của notify, poll reconciler (cũng đi qua ``_dedup_wake``), và
    vòng lặp retry — đua nhau an toàn mà không cần khóa ngoài:

    * chuỗi hoàn toàn mới                                 -> INSERT (lần 1) -> True
    * chưa hoàn thành, lần thử cũ hơn ``ttl_ms``,
      vẫn dưới ``max_attempts``                           -> UPDATE (attempt +1) -> True
    * đã hoàn thành (``gmail_draft_id`` đã đặt), đang chạy
      (trong ``ttl_ms``), hoặc đã hết lượt (>= max)       -> không đổi        -> False

    ``from_addr``/``subject`` được ghi nhận ở lần claim đầu và chỉ được làm mới
    khi truyền giá trị khác rỗng, để vòng lặp retry dựng lại được wake.

    EN: Atomically claim the right to dispatch a draft for ``(account, thread_id)``.

    Returns True to exactly ONE caller per eligible window. A single conditional
    UPSERT (mirrors :func:`note_once`) so every dispatch path — the notify
    ``_dedup_wake``, the poll reconciler (also routed through ``_dedup_wake``), and
    the retry loop — races safely without relying on an external lock:

    * brand-new thread                                   -> INSERT (attempt 1) -> True
    * unfulfilled, last attempt older than ``ttl_ms``,
      still under ``max_attempts``                       -> UPDATE (attempt +1) -> True
    * fulfilled (``gmail_draft_id`` set), in-flight
      (within ``ttl_ms``), or exhausted (>= max)         -> no change          -> False

    ``from_addr``/``subject`` are captured on the first claim and refreshed only
    when a non-empty value is supplied, so the retry loop can rebuild the wake.
    """
    cur = conn.execute(
        """
        INSERT INTO draft_requests
               (account, thread_id, from_addr, subject, attempts, last_attempt_ms, created_at_ms)
             VALUES (:acct, :tid, :from_addr, :subject, 1, :now, :now)
        ON CONFLICT(account, thread_id) DO UPDATE SET
               attempts        = attempts + 1,
               last_attempt_ms = :now,
               from_addr       = COALESCE(NULLIF(excluded.from_addr, ''), draft_requests.from_addr),
               subject         = COALESCE(NULLIF(excluded.subject, ''), draft_requests.subject)
             WHERE draft_requests.gmail_draft_id IS NULL
               AND draft_requests.attempts < :max
               AND (draft_requests.last_attempt_ms IS NULL
                    OR draft_requests.last_attempt_ms <= :now - :ttl)
        """,
        {
            "acct": account, "tid": thread_id, "from_addr": from_addr, "subject": subject,
            "now": now_ms, "max": max_attempts, "ttl": ttl_ms,
        },
    )
    return cur.rowcount == 1


def unfulfilled_drafts(
    conn: sqlite3.Connection, *, ttl_ms: int, max_attempts: int, now_ms: int
) -> list[DraftRequestRow]:
    """VI: Các dòng đủ điều kiện retry: chưa có nháp, dưới số lần thử tối đa, đã qua cửa sổ ttl.

    EN: Rows eligible for a retry: no draft yet, under max attempts, past the ttl window.
    """
    rows = conn.execute(
        """SELECT * FROM draft_requests
            WHERE gmail_draft_id IS NULL
              AND attempts < ?
              AND (last_attempt_ms IS NULL OR last_attempt_ms <= ? - ?)
            ORDER BY created_at_ms""",
        (max_attempts, now_ms, ttl_ms),
    ).fetchall()
    return cast("list[DraftRequestRow]", _as_dicts(rows))


def exhausted_drafts(conn: sqlite3.Connection, *, max_attempts: int) -> list[DraftRequestRow]:
    """VI: Nháp kẹt: đã đạt số lần thử tối đa mà chưa tạo được nháp (trạng thái bền vững, truy vấn được).

    EN: Stuck drafts: max attempts reached with no draft created (durable, queryable state).
    """
    rows = conn.execute(
        "SELECT * FROM draft_requests WHERE gmail_draft_id IS NULL AND attempts >= ? "
        "ORDER BY created_at_ms",
        (max_attempts,),
    ).fetchall()
    return cast("list[DraftRequestRow]", _as_dicts(rows))


# ── Classified messages ─────────────────────────────────────────────────────────

def record_classified_message(
    conn: sqlite3.Connection,
    *,
    account: str,
    message_id: str,
    thread_id: str,
    category: str,
    from_addr: str = "",
    subject: str = "",
    confidence: int = 0,
    source: str = "llm",
    llm_input_tokens: int | None = None,
    llm_output_tokens: int | None = None,
    llm_cost_usd_micros: int | None = None,
) -> None:
    """VI: Upsert phân loại của một thư (idempotent khi xử lý lại).

    EN: Upsert a message's classification (idempotent on re-processing).
    """
    conn.execute(
        """INSERT INTO classified_messages
               (account, message_id, thread_id, from_addr, subject, category, confidence,
                source, llm_input_tokens, llm_output_tokens, llm_cost_usd_micros, classified_at_ms)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(account, message_id) DO UPDATE SET
               thread_id           = excluded.thread_id,
               from_addr           = excluded.from_addr,
               subject             = excluded.subject,
               category            = excluded.category,
               confidence          = excluded.confidence,
               source              = excluded.source,
               llm_input_tokens    = excluded.llm_input_tokens,
               llm_output_tokens   = excluded.llm_output_tokens,
               llm_cost_usd_micros = excluded.llm_cost_usd_micros,
               classified_at_ms    = excluded.classified_at_ms""",
        (account, message_id, thread_id, from_addr, subject, category, confidence,
         source, llm_input_tokens, llm_output_tokens, llm_cost_usd_micros, now_ms()),
    )


# ── Thread state ────────────────────────────────────────────────────────────────

def upsert_thread_state(
    conn: sqlite3.Connection,
    *,
    account: str,
    thread_id: str,
    last_message_id: str,
    last_category: str,
) -> None:
    """VI: Ghi/cập nhật trạng thái chuỗi: thư cuối cùng + danh mục cuối cùng.

    EN: Upsert the thread state: last message id + last category.
    """
    conn.execute(
        """INSERT INTO thread_state (account, thread_id, last_message_id, last_category, last_processed_at_ms)
                VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(account, thread_id) DO UPDATE SET
               last_message_id      = excluded.last_message_id,
               last_category        = excluded.last_category,
               last_processed_at_ms = excluded.last_processed_at_ms""",
        (account, thread_id, last_message_id, last_category, now_ms()),
    )


def get_thread_state(
    conn: sqlite3.Connection, account: str, thread_id: str
) -> ThreadStateRow | None:
    """VI: Trả về dòng thread_state của một chuỗi, hoặc None.

    EN: Return the thread_state row for a thread, or None.
    """
    row = conn.execute(
        "SELECT * FROM thread_state WHERE account = ? AND thread_id = ?",
        (account, thread_id),
    ).fetchone()
    return cast("ThreadStateRow | None", _as_dict(row))


# ── Sender profiles (voice/relationship for the drafting brief) ───────────────────

def get_sender_profile(
    conn: sqlite3.Connection, account: str, sender_email: str
) -> SenderProfileRow | None:
    """VI: Dòng hồ sơ của một người gửi (đã chuẩn hóa), hoặc None.

    EN: The profile row for a (normalized) sender, or None.
    """
    row = conn.execute(
        "SELECT * FROM sender_profiles WHERE account = ? AND sender_email = ?",
        (account, sender_email),
    ).fetchone()
    return cast("SenderProfileRow | None", _as_dict(row))


def upsert_sender_profile(
    conn: sqlite3.Connection,
    *,
    account: str,
    sender_email: str,
    display_name: str | None = None,
    relationship: str | None = None,
    voice_notes: str | None = None,
    tone_hints: str | None = None,
    source: str | None = None,
) -> None:
    """VI: Chèn hoặc cập nhật hồ sơ người gửi. ``COALESCE`` giữ các trường non-NULL hiện
    có khi một cập nhật một phần truyền None, nên một lần tinh chỉnh sau không bao
    giờ ghi đè dữ liệu trước.

    EN: Insert or update a sender profile. ``COALESCE`` keeps existing non-NULL fields
    when a partial update passes None, so a later refinement never clobbers prior data.
    """
    conn.execute(
        """INSERT INTO sender_profiles
               (account, sender_email, display_name, relationship, voice_notes, tone_hints,
                source, draft_count, updated_at_ms)
               VALUES (:acct, :addr, :dn, :rel, :vn, :th, :src, 0, :now)
           ON CONFLICT(account, sender_email) DO UPDATE SET
               display_name  = COALESCE(:dn, display_name),
               relationship  = COALESCE(:rel, relationship),
               voice_notes   = COALESCE(:vn, voice_notes),
               tone_hints    = COALESCE(:th, tone_hints),
               source        = COALESCE(:src, source),
               updated_at_ms = :now""",
        {"acct": account, "addr": sender_email, "dn": display_name, "rel": relationship,
         "vn": voice_notes, "th": tone_hints, "src": source, "now": now_ms()},
    )


def bump_sender_draft_count(conn: sqlite3.Connection, account: str, sender_email: str) -> None:
    """VI: Tăng draft_count + dập mốc last_drafted_at_ms (no-op nếu chưa có hồ sơ).

    EN: Increment draft_count + stamp last_drafted_at_ms (no-op if no profile exists yet).
    """
    conn.execute(
        """UPDATE sender_profiles
              SET draft_count = draft_count + 1, last_drafted_at_ms = ?, updated_at_ms = ?
            WHERE account = ? AND sender_email = ?""",
        (now_ms(), now_ms(), account, sender_email),
    )


def upsert_learned_notes(
    conn: sqlite3.Connection, account: str, sender_email: str, learned_notes: str
) -> None:
    """VI: Ghi ghi chú giọng văn học-từ-chỉnh-sửa cho một người gửi (lớp đã học có thể kiểm toán).

    Chỉ đụng ``learned_notes`` + ``learned_updated_ms`` — không bao giờ
    ``voice_notes`` (lớp backfill/agent), nên nội dung chưng cất nằm ở một trường
    riêng, có thể hoàn tác. Tạo dòng hồ sơ nếu chưa có để một người gửi ta chưa
    từng backfill vẫn tích lũy được bài học.

    EN: Write the learned-from-edits voice note for a sender (the auditable learned layer).

    Touches ``learned_notes`` + ``learned_updated_ms`` ONLY — never ``voice_notes``
    (the backfill/agent layer), so distilled content stays in a separate, revertible
    field. Creates the profile row if it doesn't exist yet so a sender we've never
    backfilled can still accumulate learnings.
    """
    conn.execute(
        """INSERT INTO sender_profiles
               (account, sender_email, learned_notes, learned_updated_ms, draft_count, updated_at_ms)
               VALUES (:acct, :addr, :ln, :now, 0, :now)
           ON CONFLICT(account, sender_email) DO UPDATE SET
               learned_notes      = :ln,
               learned_updated_ms = :now,
               updated_at_ms      = :now""",
        {"acct": account, "addr": sender_email, "ln": learned_notes, "now": now_ms()},
    )


def clear_learned_notes(conn: sqlite3.Connection, account: str, sender_email: str) -> None:
    """VI: Cơ chế hoàn tác: xóa ghi chú giọng văn đã học (giữ ``voice_notes`` nguyên vẹn).

    EN: Revert affordance: drop the learned voice note (leaves ``voice_notes`` intact).
    """
    conn.execute(
        """UPDATE sender_profiles
              SET learned_notes = NULL, learned_updated_ms = ?, updated_at_ms = ?
            WHERE account = ? AND sender_email = ?""",
        (now_ms(), now_ms(), account, sender_email),
    )


def learned_note_summaries(
    conn: sqlite3.Connection, account: str | None = None, *, limit: int = 100
) -> list[LearnedNoteSummaryRow]:
    """VI: Các người gửi có ghi chú đã học — chỉ ĐỘ DÀI của ghi chú, không bao giờ nội dung.

    Phép chiếu bảo toàn quyền riêng tư cho công cụ status: tránh đưa văn bản chưng
    cất (phái sinh từ nội dung email không đáng tin) lên bề mặt chat — chủ sở hữu
    đọc ghi chú đầy đủ qua công cụ sender-profile. Một tài khoản, hoặc
    (``account=None``) tất cả tài khoản. Mới cập nhật nhất trước.

    EN: Senders that have a learned note — the note's LENGTH only, never its text.

    Privacy-preserving projection for the status tool: surfacing distilled prose
    (which derives from untrusted email content) into a chat surface is avoided —
    the owner reads the full note via the sender-profile tool. One account, or
    (``account=None``) all accounts. Newest-updated first.
    """
    sql = (
        "SELECT account, sender_email, length(learned_notes) AS note_chars, "
        "learned_updated_ms AS updated_ms FROM sender_profiles "
        "WHERE learned_notes IS NOT NULL AND learned_notes != ''"
    )
    params: list = []
    if account:
        sql += " AND account = ?"
        params.append(account)
    sql += " ORDER BY learned_updated_ms DESC LIMIT ?"
    params.append(limit)
    return cast(
        "list[LearnedNoteSummaryRow]", _as_dicts(conn.execute(sql, params).fetchall())
    )


# ── Draft feedback: outcome pairing ledger + gold examples ────────────────────────

def upsert_draft_outcome_draft(
    conn: sqlite3.Connection,
    *,
    account: str,
    thread_id: str,
    sender_email: str,
    gmail_draft_id: str,
    draft_body: str,
) -> None:
    """VI: Ghi/làm mới phía nháp của một dòng outcome (chụp tại inbox_create_draft).

    Upsert có điều kiện (M3/G1): chèn-nếu-vắng luôn chạy, nhưng nhánh ON CONFLICT
    đặt lại ``outcome='pending'`` và ghi đè ``draft_body``/``gmail_draft_id`` CHỈ
    ``WHERE draft_outcomes.outcome = 'pending'``. Vậy một lần ghi soạn-lại/retry
    rơi vào *sau* khi ``on_sent`` đã ghi một lần gửi sẽ không thể ghi đè
    ``sent_body``/outcome đã chụp — ví dụ vàng được bảo toàn.

    EN: Write/refresh the draft side of an outcome row (captured at inbox_create_draft).

    Conditional upsert (M3/G1): insert-if-absent always proceeds, but the ON CONFLICT
    branch resets ``outcome='pending'`` and overwrites ``draft_body``/``gmail_draft_id``
    ONLY ``WHERE draft_outcomes.outcome = 'pending'``. So a re-draft/retry write that
    lands *after* ``on_sent`` already recorded a send cannot clobber the captured
    ``sent_body``/outcome — the gold example survives.
    """
    conn.execute(
        """INSERT INTO draft_outcomes
               (account, thread_id, sender_email, gmail_draft_id, draft_body,
                draft_created_ms, outcome, updated_at_ms)
               VALUES (:acct, :tid, :addr, :did, :body, :now, 'pending', :now)
           ON CONFLICT(account, thread_id) DO UPDATE SET
               sender_email     = excluded.sender_email,
               gmail_draft_id   = excluded.gmail_draft_id,
               draft_body       = excluded.draft_body,
               draft_created_ms = excluded.draft_created_ms,
               outcome          = 'pending',
               updated_at_ms    = excluded.updated_at_ms
             WHERE draft_outcomes.outcome = 'pending'""",
        {"acct": account, "tid": thread_id, "addr": sender_email, "did": gmail_draft_id,
         "body": draft_body, "now": now_ms()},
    )


def record_draft_outcome_sent(
    conn: sqlite3.Connection,
    *,
    account: str,
    thread_id: str,
    sender_email: str,
    sent_message_id: str,
    sent_body: str,
    similarity: int | None,
    outcome: str,
) -> None:
    """VI: Ghi phía đã gửi + outcome (upsert; hỗ trợ các dòng capture-all ``draft_body IS NULL``).

    Dùng cho cả chuỗi đã soạn nháp (dòng đã tồn tại với ``draft_body``) lẫn dòng
    capture-all ``sent_no_draft`` (chèn mới, ``draft_body`` NULL). Phía đã gửi là
    authoritative, nên hàm này ghi đè vô điều kiện — nó chỉ được gọi từ đường dẫn
    ``on_sent`` đơn luồng sau khi ghép cặp.

    EN: Write the sent side + outcome (upsert; supports ``draft_body IS NULL`` capture-all rows).

    Used both for a drafted thread (the row already exists with a ``draft_body``) and
    for a ``sent_no_draft`` capture-all row (inserted fresh, ``draft_body`` NULL). The
    sent side is authoritative, so this overwrites unconditionally — it is only called
    from the single-threaded ``on_sent`` path after pairing.
    """
    conn.execute(
        """INSERT INTO draft_outcomes
               (account, thread_id, sender_email, sent_message_id, sent_body,
                sent_at_ms, outcome, similarity, updated_at_ms)
               VALUES (:acct, :tid, :addr, :smid, :sbody, :now, :outcome, :sim, :now)
           ON CONFLICT(account, thread_id) DO UPDATE SET
               sender_email    = COALESCE(NULLIF(excluded.sender_email, ''), draft_outcomes.sender_email),
               sent_message_id = excluded.sent_message_id,
               sent_body       = excluded.sent_body,
               sent_at_ms      = excluded.sent_at_ms,
               outcome         = excluded.outcome,
               similarity      = excluded.similarity,
               updated_at_ms   = excluded.updated_at_ms""",
        {"acct": account, "tid": thread_id, "addr": sender_email, "smid": sent_message_id,
         "sbody": sent_body, "outcome": outcome, "sim": similarity, "now": now_ms()},
    )


def get_draft_outcome(
    conn: sqlite3.Connection, account: str, thread_id: str
) -> DraftOutcomeRow | None:
    """VI: Dòng draft_outcomes của một chuỗi, hoặc None.

    EN: The draft_outcomes row for a thread, or None.
    """
    row = conn.execute(
        "SELECT * FROM draft_outcomes WHERE account = ? AND thread_id = ?",
        (account, thread_id),
    ).fetchone()
    return cast("DraftOutcomeRow | None", _as_dict(row))


def unlearned_outcomes(conn: sqlite3.Connection, *, limit: int) -> list[DraftOutcomeRow]:
    """VI: Các dòng sẵn sàng chưng cất: đã phân loại (không ``pending``) nhưng chưa ``learned``.

    Hàng đợi chưng cất (và lần retry belt-and-suspenders của sweep cho một lần
    chưng cất ``on_sent`` bị lỗi). Cũ nhất trước để backlog được xử lý theo thứ tự.

    EN: Rows ready to distill: classified (not ``pending``) but not yet ``learned``.

    The distill queue (and the sweep's belt-and-suspenders retry for an ``on_sent``
    distill that failed). Oldest first so a backlog drains in order.
    """
    rows = conn.execute(
        """SELECT * FROM draft_outcomes
            WHERE learned = 0 AND outcome != 'pending'
            ORDER BY updated_at_ms
            LIMIT ?""",
        (limit,),
    ).fetchall()
    return cast("list[DraftOutcomeRow]", _as_dicts(rows))


def pending_outcomes_older_than(
    conn: sqlite3.Connection, *, before_ms: int
) -> list[DraftOutcomeRow]:
    """VI: Các dòng đã soạn ``pending`` có nháp cũ hơn ``before_ms`` (sweep no-reply).

    EN: ``pending`` drafted rows whose draft is older than ``before_ms`` (no-reply sweep).
    """
    rows = conn.execute(
        """SELECT * FROM draft_outcomes
            WHERE outcome = 'pending' AND draft_created_ms IS NOT NULL AND draft_created_ms <= ?
            ORDER BY draft_created_ms""",
        (before_ms,),
    ).fetchall()
    return cast("list[DraftOutcomeRow]", _as_dicts(rows))


def mark_outcome_learned(conn: sqlite3.Connection, account: str, thread_id: str) -> None:
    """VI: Đặt ``learned=1`` + dập mốc ``learned_at_ms`` để hàng đợi chưng cất không chọn lại.

    EN: Flip ``learned=1`` + stamp ``learned_at_ms`` so the distill queue won't re-pick it.
    """
    conn.execute(
        """UPDATE draft_outcomes
              SET learned = 1, learned_at_ms = ?, updated_at_ms = ?
            WHERE account = ? AND thread_id = ?""",
        (now_ms(), now_ms(), account, thread_id),
    )


def mark_outcome_no_reply(conn: sqlite3.Connection, account: str, thread_id: str) -> bool:
    """VI: Đổi một dòng đã soạn còn ``pending`` thành ``no_reply``; True đúng khi nó thực sự đổi.

    Có điều kiện (G1): guard ``WHERE outcome = 'pending'`` nghĩa là một lần gửi mà
    ``on_sent`` ghi giữa lúc sweep đọc và lúc ghi này không bao giờ bị ghi đè (dòng
    đã không còn 'pending' → rowcount 0). Caller chịu trách nhiệm quyết định
    liveness M1 (đang quản lý + không đang kết nối lại + đã drain sau khi soạn)
    trước khi gọi.

    EN: Flip a still-``pending`` drafted row to ``no_reply``; True iff it actually flipped.

    Conditional (G1): the ``WHERE outcome = 'pending'`` guard means a send that
    ``on_sent`` recorded between the sweep's read and this write is never clobbered
    (the row is no longer 'pending' → rowcount 0). The caller owns the M1 liveness
    decision (managed + not reconnecting + drained-after-draft) before calling this.
    """
    cur = conn.execute(
        """UPDATE draft_outcomes
              SET outcome = 'no_reply', updated_at_ms = ?
            WHERE account = ? AND thread_id = ? AND outcome = 'pending'""",
        (now_ms(), account, thread_id),
    )
    return cur.rowcount == 1


def recent_sent_examples(
    conn: sqlite3.Connection, account: str, sender_email: str, *, limit: int
) -> list[DraftOutcomeRow]:
    """VI: Ví dụ vàng cho một người gửi: các dòng có ``sent_body`` khác rỗng, mới nhất trước.

    EN: Gold examples for a sender: rows with a non-empty ``sent_body``, newest first.
    """
    rows = conn.execute(
        """SELECT * FROM draft_outcomes
            WHERE account = ? AND sender_email = ?
              AND sent_body IS NOT NULL AND sent_body != ''
            ORDER BY sent_at_ms DESC
            LIMIT ?""",
        (account, sender_email, limit),
    ).fetchall()
    return cast("list[DraftOutcomeRow]", _as_dicts(rows))


def count_outcomes_by_sender(
    conn: sqlite3.Connection, account: str, sender_email: str
) -> dict[str, int]:
    """VI: Histogram outcome của một người gửi (công cụ status + ngưỡng no_reply).

    EN: Outcome histogram for a sender (status tool + the no_reply threshold).
    """
    rows = conn.execute(
        """SELECT outcome, count(*) AS n FROM draft_outcomes
            WHERE account = ? AND sender_email = ?
            GROUP BY outcome""",
        (account, sender_email),
    ).fetchall()
    return {r["outcome"]: r["n"] for r in rows}


def outcome_histogram(
    conn: sqlite3.Connection, account: str | None = None
) -> dict[str, int]:
    """VI: Số đếm outcome ``{outcome: n}`` cho một tài khoản, hoặc (``account=None``) tất cả tài khoản.

    EN: Outcome counts ``{outcome: n}`` for one account, or (``account=None``) all accounts.
    """
    sql = "SELECT outcome, count(*) AS n FROM draft_outcomes"
    params: list = []
    if account:
        sql += " WHERE account = ?"
        params.append(account)
    sql += " GROUP BY outcome"
    return {r["outcome"]: r["n"] for r in conn.execute(sql, params).fetchall()}


def delete_learned_outcomes_older_than(
    conn: sqlite3.Connection, *, before_ms: int
) -> int:
    """VI: Dọn retention: xóa các outcome đã học (kể cả ví dụ vàng) quá cửa sổ để chặn
    sự phình của ``draft_outcomes``. Trả về số dòng đã xóa.

    EN: Retention prune: drop already-learned outcomes (incl. gold examples) past the
    window to bound ``draft_outcomes`` growth. Returns the number deleted.
    """
    cur = conn.execute(
        "DELETE FROM draft_outcomes WHERE learned = 1 AND updated_at_ms <= ?",
        (before_ms,),
    )
    return cur.rowcount


# ── Draft feedback: global learned lessons ────────────────────────────────────────

def upsert_lesson(
    conn: sqlite3.Connection,
    *,
    account: str,
    scope: str,
    polarity: str,
    rule: str,
) -> None:
    """VI: Chèn một bài học do/don't hoặc, khi ``norm_rule`` trùng, tăng bằng chứng của nó.

    Khóa dedup là ``(account, scope, polarity, norm_rule)`` với ``norm_rule`` là
    ``rule`` đã viết thường/cắt khoảng trắng. Một lần lặp lại cùng bài học làm
    ``evidence_count`` tăng + ``last_seen_ms`` được đẩy lên (để xếp hạng cao hơn)
    thay vì chèn một bản gần-trùng. Dedup cục bộ — không bao giờ tin model là duy
    nhất.

    EN: Insert a do/don't lesson or, on a duplicate ``norm_rule``, bump its evidence.

    Dedup key is ``(account, scope, polarity, norm_rule)`` where ``norm_rule`` is the
    lowercased/trimmed ``rule``. A repeat of the same lesson increments
    ``evidence_count`` + bumps ``last_seen_ms`` (so it ranks higher) rather than
    inserting a near-duplicate. Local dedup — never trust the model to be unique.
    """
    norm = rule.strip().lower()
    conn.execute(
        """INSERT INTO draft_lessons
               (account, scope, polarity, rule, norm_rule, evidence_count, active,
                created_at_ms, last_seen_ms)
               VALUES (:acct, :scope, :pol, :rule, :norm, 1, 1, :now, :now)
           ON CONFLICT(account, scope, polarity, norm_rule) DO UPDATE SET
               evidence_count = evidence_count + 1,
               rule           = excluded.rule,
               active         = 1,
               last_seen_ms   = :now""",
        {"acct": account, "scope": scope, "pol": polarity, "rule": rule, "norm": norm,
         "now": now_ms()},
    )


def top_lessons(
    conn: sqlite3.Connection, account: str, *, limit: int
) -> list[DraftLessonRow]:
    """VI: Các bài học đang active của một tài khoản, xếp theo bằng chứng rồi độ mới (brief + status).

    EN: Active lessons for an account, ranked by evidence then recency (brief + status).
    """
    rows = conn.execute(
        """SELECT * FROM draft_lessons
            WHERE account = ? AND active = 1
            ORDER BY evidence_count DESC, last_seen_ms DESC
            LIMIT ?""",
        (account, limit),
    ).fetchall()
    return cast("list[DraftLessonRow]", _as_dicts(rows))


def all_active_lessons(conn: sqlite3.Connection, *, limit: int) -> list[DraftLessonRow]:
    """VI: Các bài học đang active trên TẤT CẢ tài khoản, xếp theo bằng chứng rồi độ mới
    (cái nhìn không giới hạn của công cụ status). Dùng :func:`top_lessons` để giới
    hạn một tài khoản.

    EN: Active lessons across ALL accounts, ranked by evidence then recency (the status
    tool's unscoped view). Use :func:`top_lessons` to scope to one account.
    """
    rows = conn.execute(
        """SELECT * FROM draft_lessons
            WHERE active = 1
            ORDER BY evidence_count DESC, last_seen_ms DESC
            LIMIT ?""",
        (limit,),
    ).fetchall()
    return cast("list[DraftLessonRow]", _as_dicts(rows))


def prune_lessons(conn: sqlite3.Connection, account: str, *, keep: int) -> int:
    """VI: Đuổi mềm (``active=0``) các bài học active có giá trị thấp nhất vượt ``keep``.

    Tiebreak tất định ``ORDER BY evidence_count ASC, last_seen_ms ASC`` (ổn định khi
    nhiều bài học cùng ``evidence_count=1``). Trả về số bài bị đuổi. Mềm để một bài
    đã dọn có thể được ``upsert_lesson`` kích hoạt lại khi thấy nó lần nữa.

    EN: Soft-evict (``active=0``) the lowest-value active lessons beyond ``keep``.

    Deterministic tiebreak ``ORDER BY evidence_count ASC, last_seen_ms ASC`` (stable
    when many lessons share ``evidence_count=1``). Returns the number evicted. Soft so
    a pruned lesson can be re-activated by ``upsert_lesson`` seeing it again.
    """
    cur = conn.execute(
        """UPDATE draft_lessons SET active = 0
            WHERE lesson_id IN (
                SELECT lesson_id FROM draft_lessons
                 WHERE account = ? AND active = 1
                 ORDER BY evidence_count DESC, last_seen_ms DESC
                 LIMIT -1 OFFSET ?
            )""",
        (account, keep),
    )
    return cur.rowcount


def set_lesson_active(conn: sqlite3.Connection, lesson_id: int, active: int) -> None:
    """VI: Cơ chế hoàn tác: bật/tắt cờ ``active`` của một bài học (1=bật, 0=tắt mềm).

    EN: Revert affordance: toggle a lesson's ``active`` flag (1=on, 0=soft-disabled).
    """
    conn.execute(
        "UPDATE draft_lessons SET active = ? WHERE lesson_id = ?",
        (1 if active else 0, lesson_id),
    )


# ── Module dedup (generic once-only marker) ──────────────────────────────────────

def note_once(conn: sqlite3.Connection, module: str, account: str, dedup_key: str) -> bool:
    """VI: Ghi ``(module, account, dedup_key)`` chỉ lần đầu; True đúng khi mới.

    Check-rồi-chèn nguyên tử (``INSERT OR IGNORE`` → rowcount): trả về True ở lần
    gọi đầu cho một khóa và False ở mọi lần sau, nên một module thông báo chỉ bắn
    đúng một lần kể cả khi cùng thư bị drain lại (Pub/Sub redelivery, poll
    reconciler, reset StaleCursor). ``dedup_key`` không được mang bí mật/PII —
    khóa theo ``message_id`` (hoặc carrier+tracking+stage), không bao giờ là mã.

    EN: Record ``(module, account, dedup_key)`` the first time only; True iff new.

    Atomic check-then-insert (``INSERT OR IGNORE`` → rowcount): returns True on
    the first call for a key and False on every later call, so a notifying module
    fires exactly once even when the same message is re-drained (Pub/Sub
    redelivery, poll reconciler, StaleCursor reset). ``dedup_key`` must not carry
    a secret/PII — key on ``message_id`` (or carrier+tracking+stage), never a code.
    """
    cur = conn.execute(
        "INSERT OR IGNORE INTO module_notified (module, account, dedup_key, notified_at_ms) "
        "VALUES (?, ?, ?, ?)",
        (module, account, dedup_key, now_ms()),
    )
    return cur.rowcount == 1


def was_notified(conn: sqlite3.Connection, module: str, account: str, dedup_key: str) -> bool:
    """VI: True nếu ``note_once`` đã ghi khóa này (kiểm tra chỉ-đọc).

    EN: True if ``note_once`` has already recorded this key (read-only check).
    """
    return conn.execute(
        "SELECT 1 FROM module_notified WHERE module = ? AND account = ? AND dedup_key = ?",
        (module, account, dedup_key),
    ).fetchone() is not None


# ── Tracked packages (shipping module) ───────────────────────────────────────

def add_tracked_package(
    conn: sqlite3.Connection, account: str, tracking_number: str, carrier: int | None = None
) -> bool:
    """VI: Chèn một kiện hàng mới phát hiện; True đúng khi mới (email lặp lại là no-op).

    EN: Insert a newly-detected parcel; True iff new (repeat emails are no-ops).
    """
    cur = conn.execute(
        """INSERT OR IGNORE INTO tracked_packages
               (account, tracking_number, carrier, created_at_ms, updated_at_ms)
               VALUES (?, ?, ?, ?, ?)""",
        (account, tracking_number, carrier, now_ms(), now_ms()),
    )
    return cur.rowcount == 1


def mark_package_registered(
    conn: sqlite3.Connection, account: str, tracking_number: str, carrier: int | None = None
) -> None:
    """VI: Đánh dấu kiện hàng đã được 17track chấp nhận (và ghi carrier đã phân giải).

    EN: Flag a parcel as accepted by 17track (and record the resolved carrier).
    """
    conn.execute(
        """UPDATE tracked_packages
              SET registered = 1,
                  carrier = COALESCE(?, carrier),
                  updated_at_ms = ?
            WHERE account = ? AND tracking_number = ?""",
        (carrier, now_ms(), account, tracking_number),
    )


def count_active_packages(conn: sqlite3.Connection) -> int:
    """VI: Các kiện đã đăng ký, chưa terminal — kích thước tập poll đang sống (cho giới hạn).

    EN: Registered, non-terminal parcels — the live poll set size (for the cap).
    """
    return conn.execute(
        "SELECT count(*) FROM tracked_packages WHERE registered = 1 AND terminal = 0"
    ).fetchone()[0]


def get_active_packages(conn: sqlite3.Connection) -> list[TrackedPackageRow]:
    """VI: Các kiện đã đăng ký, chưa terminal trên tất cả tài khoản (tập poll).

    EN: Registered, non-terminal parcels across all accounts (the poll set).
    """
    rows = conn.execute(
        "SELECT * FROM tracked_packages WHERE registered = 1 AND terminal = 0"
    ).fetchall()
    return cast("list[TrackedPackageRow]", _as_dicts(rows))


def update_package_stage(
    conn: sqlite3.Connection,
    account: str,
    tracking_number: str,
    stage: str,
    *,
    terminal: bool = False,
) -> None:
    """VI: Ghi giai đoạn mới nhất từ poll (và liệu kiện hàng đã terminal chưa).

    EN: Record the latest polled stage (and whether the parcel is now terminal).
    """
    conn.execute(
        """UPDATE tracked_packages
              SET last_stage = ?, terminal = ?, updated_at_ms = ?
            WHERE account = ? AND tracking_number = ?""",
        (stage, 1 if terminal else 0, now_ms(), account, tracking_number),
    )


def set_package_notified_stage(
    conn: sqlite3.Connection, account: str, tracking_number: str, stage: str
) -> None:
    """VI: Ghi giai đoạn ta thực sự đã đẩy (chỉ tiến sau khi gửi thành công).

    EN: Record the stage we actually pushed (advanced only after a successful send).
    """
    conn.execute(
        """UPDATE tracked_packages
              SET last_notified_stage = ?, updated_at_ms = ?
            WHERE account = ? AND tracking_number = ?""",
        (stage, now_ms(), account, tracking_number),
    )


def list_tracked_packages(
    conn: sqlite3.Connection, account: str | None = None, *, include_terminal: bool = False
) -> list[TrackedPackageRow]:
    """VI: Các kiện hàng được theo dõi cho công cụ theo yêu cầu (có thể giới hạn / gồm đã giao).

    EN: Tracked parcels for the on-demand tool (optionally scoped / incl. delivered).
    """
    sql = "SELECT * FROM tracked_packages"
    clauses, params = [], []
    if account:
        clauses.append("account = ?")
        params.append(account)
    if not include_terminal:
        clauses.append("terminal = 0")
    if clauses:
        sql += " WHERE " + " AND ".join(clauses)
    sql += " ORDER BY updated_at_ms DESC"
    return cast("list[TrackedPackageRow]", _as_dicts(conn.execute(sql, params).fetchall()))


# ── OAuth pending (dashboard copy-paste connect; see dashboard_api) ───────────────

def create_oauth_pending(conn: sqlite3.Connection, *, state: str, verifier: str) -> None:
    """VI: Cất một ``verifier`` PKCE cho một kết nối dashboard đang diễn ra, khóa theo ``state``.

    EN: Stash a PKCE ``verifier`` for an in-flight dashboard connect, keyed by ``state``.
    """
    conn.execute(
        "INSERT OR REPLACE INTO oauth_pending (state, verifier, created_at_ms) VALUES (?, ?, ?)",
        (state, verifier, now_ms()),
    )


def take_oauth_pending(
    conn: sqlite3.Connection, state: str, *, ttl_ms: int, now_ms: int
) -> str | None:
    """VI: Tiêu thụ + trả về verifier PKCE cho ``state`` (dùng một lần), ngược lại None.

    Luôn xóa dòng (one shot), và trả về None khi nó thiếu hoặc cũ hơn ``ttl_ms`` —
    để một kết nối cũ/hết hạn không thể hoàn tất. ``now_ms`` là tham số để kiểm
    thử được (phỏng theo :func:`claim_draft`).

    EN: Consume + return the PKCE verifier for ``state`` (single-use), else None.

    Always deletes the row (one shot), and returns None when it is missing or older
    than ``ttl_ms`` — so a stale/expired connect can't be completed. ``now_ms`` is a
    parameter for testability (mirrors :func:`claim_draft`).
    """
    row = conn.execute(
        "SELECT verifier, created_at_ms FROM oauth_pending WHERE state = ?", (state,)
    ).fetchone()
    if row is None:
        return None
    conn.execute("DELETE FROM oauth_pending WHERE state = ?", (state,))
    if now_ms - row["created_at_ms"] > ttl_ms:
        return None
    return row["verifier"]


def sweep_oauth_pending(conn: sqlite3.Connection, *, before_ms: int) -> int:
    """VI: Xóa các dòng pending tạo tại/trước ``before_ms`` (GC theo TTL). Trả về số dòng.

    EN: Delete pending rows created at/before ``before_ms`` (TTL GC). Returns the count.
    """
    return conn.execute(
        "DELETE FROM oauth_pending WHERE created_at_ms <= ?", (before_ms,)
    ).rowcount
