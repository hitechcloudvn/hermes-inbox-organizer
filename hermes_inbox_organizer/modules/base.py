"""VI: Hợp đồng module — cách các module tính năng móc vào luồng email.

Một *module* là một đơn vị tự chứa, có thể bật/tắt (ví dụ: bản tổng hợp chưa
đọc, notifier 2FA, trình theo dõi vận chuyển) cắm vào luồng phân loại tự động
mà lõi không cần biết về nó. Hợp đồng là **lai**:

* **quan sát** theo mặc định — ``on_inbound`` / ``on_sent`` chạy SAU khi lõi đã
  phân loại, gắn nhãn và lưu bền vững một thư. Chúng chỉ có tác dụng phụ (thông
  báo / theo dõi / lưu trữ) và được dispatch NGOÀI khóa runtime trên một worker
  pool, nên một module chậm hoặc lỗi không thể làm đình trễ hay phá vỡ phân loại.
* **ảnh hưởng** theo opt-in — ``classify_override`` chạy trong pha QUYẾT ĐỊNH,
  *dưới* khóa runtime, và có thể trả về một danh mục để ghi đè bộ phân loại mặc
  định. Nó PHẢI rẻ và thuần (chỉ regex/parse, không I/O). Trả về ``None`` để
  hoãn cho bộ phân loại mặc định; một danh mục không hợp lệ/không xác định bị
  registry từ chối và cũng hoãn.

Các module cũng có thể đóng góp **tools** của agent và các job hẹn giờ **periodic**.

Các sự kiện mang dữ liệu THUẦN (dict thư đã parse), không bao giờ ``service``
Gmail trực tiếp hay kết nối DB của drainer — nên một module làm I/O tự mở một
``db.connect()`` ngắn hạn trên worker thread của nó (kết nối của drainer là
single-threaded), và unit test dựng các sự kiện như dataclass thuần không cần
mock Gmail/Hermes.

EN: The module contract — how feature modules hook into the email flow.

A *module* is a self-contained, optionally-enabled unit (e.g. the unread rollup,
the 2FA notifier, the shipping tracker) that plugs into the autonomous triage
flow without the core having to know about it. The contract is **hybrid**:

* **observe** by default — ``on_inbound`` / ``on_sent`` fire AFTER the core has
  classified, labelled, and persisted a message. They are side-effect only
  (notify / track / persist) and are dispatched OFF the runtime lock on a worker
  pool, so a slow or failing module can't stall or break triage.
* **influence** by opt-in — ``classify_override`` runs in the DECISION phase,
  *under* the runtime lock, and may return a category to override the default
  classifier. It MUST be cheap and pure (regex/parse only, no I/O). Returning
  ``None`` defers to the default classifier; an invalid/unknown category is
  rejected by the registry and also defers.

Modules may also contribute agent **tools** and **periodic** timer jobs.

Events carry plain DATA (the already-parsed message dict), never the live Gmail
``service`` or the drain's DB connection — so a module that does I/O opens its
own short-lived ``db.connect()`` on its worker thread (the drain's connection is
single-threaded), and unit tests build events as plain dataclasses with no
Gmail/Hermes mocking.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class InboundEvent:
    """VI: Một thư đến đã được phân loại + gắn nhãn (pha thông báo).

    EN: One inbound message that was classified + labelled (notification phase).
    """

    account_id: str
    message_id: str
    thread_id: str
    parsed: dict  # parse_message() output — headers + body/snippet + label_ids
    category: str  # the bare category actually applied (e.g. "To Respond", "Notification")


@dataclass(frozen=True)
class SentEvent:
    """VI: Một trong những thư ĐÃ GỬI của chủ sở hữu, sau khi sent-handler đã chuyển chuỗi của nó.

    EN: One of the owner's SENT messages, after the sent-handler moved its thread.
    """

    account_id: str
    message_id: str
    thread_id: str
    parsed: dict
    target_category: str  # "Actioned" | "Awaiting Reply"


@dataclass(frozen=True)
class ToolSpec:
    """VI: Một công cụ agent mà module đóng góp (đăng ký qua ``ctx.register_tool``).

    EN: An agent tool a module contributes (registered via ``ctx.register_tool``).
    """

    name: str
    schema: dict
    handler: Callable[..., Any]
    description: str = ""
    toolset: str = "inbox"
    emoji: str | None = None


@dataclass(frozen=True)
class PeriodicJob:
    """VI: Một job hẹn giờ mà module đóng góp; runtime lặp ``run_once`` mỗi
    ``interval_s`` trên một daemon thread. ``run_once`` phải chạy một lượt có
    giới hạn và bỏ qua các tài khoản không còn được quản lý (phản chiếu bộ
    reconciler của chính runtime).

    EN: A timer job a module contributes; the runtime loops ``run_once`` every
    ``interval_s`` on a daemon thread. ``run_once`` must do one bounded pass and
    skip accounts no longer managed (mirrors the runtime's own reconciler).
    """

    name: str
    interval_s: float
    run_once: Callable[[], None]


class Module:
    """VI: Lớp cơ sở cho các module hộp thư — kế thừa và ghi đè chỉ những gì bạn cần.

    Thuộc tính lớp:
      * ``name``     — định danh ổn định (khóa dedup, log). Hãy ghi đè nó.
      * ``priority`` — số nhỏ chạy trước cho ``classify_override`` (mặc định 100).

    Hợp đồng instance (tất cả tùy chọn; mặc định là trơ):
      * ``enabled``           — cổng cấu hình; module bị tắt bị bỏ qua hoàn toàn.
      * ``classify_override`` — pha QUYẾT ĐỊNH, dưới khóa, thuần/không-I/O.
      * ``on_inbound``/``on_sent`` — pha THÔNG BÁO, được offload, có thể làm I/O.
      * ``tools``/``periodic``     — các đóng góp được nối khi đăng ký/khởi động.

    EN: Base class for inbox modules — subclass and override only what you need.

    Class attributes:
      * ``name``     — stable identifier (dedup keys, logs). Override it.
      * ``priority`` — lower runs earlier for ``classify_override`` (default 100).

    Instance contract (all optional; defaults are inert):
      * ``enabled``           — config gate; a disabled module is skipped entirely.
      * ``classify_override`` — DECISION phase, under the lock, pure/no-I/O.
      * ``on_inbound``/``on_sent`` — NOTIFICATION phase, offloaded, may do I/O.
      * ``tools``/``periodic``     — contributions wired at registration/start.
    """

    name: str = "module"
    priority: int = 100

    @property
    def enabled(self) -> bool:
        """VI: Trả về True nếu module được bật và nên được chạy.

        EN: Return True when the module is enabled and should run.
        """
        return True

    # -- decision phase (under the runtime lock — keep it cheap, no I/O) --------
    def classify_override(self, parsed: dict) -> str | None:
        """VI: Trả về một danh mục để ghi đè bộ phân loại mặc định, hoặc None.

        EN: Return a bare category to override the default classifier, or None.
        """
        return None

    # -- notification phase (offloaded off the lock — I/O allowed) --------------
    def on_inbound(self, event: InboundEvent) -> None:
        """VI: Hook pha thông báo cho một thư đến đã phân loại + gắn nhãn (mặc định không làm gì).

        EN: Notification-phase hook for a classified + labelled inbound message (default no-op).
        """
        return None

    def on_sent(self, event: SentEvent) -> None:
        """VI: Hook pha thông báo cho một thư đã gửi của chủ sở hữu (mặc định không làm gì).

        EN: Notification-phase hook for one of the owner's sent messages (default no-op).
        """
        return None

    # -- contributions ----------------------------------------------------------
    def tools(self) -> list[ToolSpec]:
        """VI: Trả về các công cụ agent mà module đóng góp (mặc định: không có).

        EN: Return the agent tools the module contributes (default: none).
        """
        return []

    def periodic(self) -> list[PeriodicJob]:
        """VI: Trả về các job hẹn giờ mà module đóng góp (mặc định: không có).

        EN: Return the timer jobs the module contributes (default: none).
        """
        return []
