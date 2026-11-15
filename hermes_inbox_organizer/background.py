"""VI: Daemon hộp thư liên tục — chạy trong tiến trình bên trong Hermes.

Đã chứng minh khả thi qua ``hermes-chat-recorder`` (``_background_loop.py``: một
vòng lặp asyncio bền vững trên luồng ``daemon=True``) và ``plugins/google_meet``
có sẵn trong repo (trình quản lý tiến trình + kết nối thời gian thực). Một plugin
có thể sở hữu công việc dài hạn được khởi động từ ``register()``.

Daemon tiêu thụ các thông báo thay đổi của Gmail qua Pub/Sub **streaming pull** —
một kết nối *ra ngoài* dài hạn, nên KHÔNG có webhook công khai, không có tunnel
Cloudflare, và không cần xác minh OIDC cho các POST của Google (tất cả đều là yêu
cầu của push). Nó phân loại từng thư mới bằng bộ phân loại cục bộ rẻ tiền, gắn
nhãn, và với các thư "To Respond" thì nhờ agent soạn nháp (qua trigger callback).

``MessageSource`` là một seam: nguồn thật là ``PubSubMessageSource`` (streaming
pull), nhưng các bài test điều khiển một nguồn giả để logic định tuyến chạy được
mà không cần GCP thật. Subscriber Pub/Sub sở hữu luồng nền riêng, mô phỏng cách
client ``google.cloud.pubsub_v1`` thật giao các callback.

EN: The continual inbox daemon — runs in-process inside Hermes.

Proven viable by ``hermes-chat-recorder`` (``_background_loop.py``: a persistent
asyncio loop on a ``daemon=True`` thread) and the in-tree ``plugins/google_meet``
(process managers + realtime connections). A plugin may own long-lived work
started from ``register()``.

The daemon consumes Gmail change notifications via Pub/Sub **streaming pull** —
an *outbound* long-lived connection, so there is NO public webhook, no Cloudflare
tunnel, and no OIDC verification of Google's POSTs (all required by push). It
classifies each new message with the cheap local classifier, applies a label,
and for "To Respond" messages asks the agent to draft (via the trigger callback).

``MessageSource`` is a seam: the real source is ``PubSubMessageSource`` (streaming
pull), but tests drive a fake source so the routing logic runs without live GCP.
The Pub/Sub subscriber owns its own background thread, mirroring how the real
``google.cloud.pubsub_v1`` client delivers callbacks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

logger = logging.getLogger(__name__)

TO_RESPOND = "1: To Respond"


@dataclass(frozen=True)
class InboundMessage:
    """VI: Một thư đến được giải mã từ thông báo thay đổi của Gmail.

    EN: One inbound message decoded from a Gmail change notification.
    """

    account_id: str
    message_id: str
    thread_id: str
    sender: str
    subject: str
    label_ids: tuple[str, ...] = ()


# A source pushes inbound messages to a callback (mirrors pubsub_v1.subscribe).
OnMessage = Callable[[InboundMessage], object]  # return (a label, or None) is ignored by the source


class MessageSource(Protocol):
    """VI: Giao diện nguồn thư đến — đẩy từng ``InboundMessage`` vào một callback.

    EN: Inbound-message source interface, pushing each ``InboundMessage`` to a callback.
    """

    def start(self, on_message: OnMessage) -> None:
        """VI: Bắt đầu nguồn thư đến và gọi ``on_message`` với mỗi thư mới.

        EN: Start the inbound source, invoking ``on_message`` for each new message.
        """
        ...

    def stop(self) -> None:
        """VI: Dừng nguồn thư đến.

        EN: Stop the inbound source.
        """
        ...


class NullSource:
    """VI: Nguồn trơ để ``daemon.start()`` an toàn khi chưa cấu hình (tests/CI).

    EN: Inert source so ``daemon.start()`` is safe when unconfigured (tests/CI).
    """

    def start(self, on_message: OnMessage) -> None:
        """VI: Không làm gì cả — nguồn trơ không bao giờ đẩy thư.

        EN: Do nothing — the inert source never pushes messages.
        """
        return None

    def stop(self) -> None:
        """VI: Không làm gì cả — nguồn trơ không có gì để dừng.

        EN: Do nothing — the inert source has nothing to stop.
        """
        return None


Classifier = Callable[[InboundMessage], str]  # returns a category label name
ApplyLabel = Callable[[InboundMessage, str], None]
OnToRespond = Callable[[InboundMessage], None]


class InboxDaemon:
    """VI: Nối một nguồn thư vào quy trình phân loại -> gắn nhãn -> có thể soạn nháp.

    ``handle`` chỉ thuần định tuyến (không tự I/O gì ngoài các callback được tiêm)
    và là phần lõi được unit-test. ``start``/``stop`` ủy quyền cho nguồn, mà bản
    triển khai thật sở hữu kết nối/luồng liên tục.

    EN: Wires a message source to the classify -> label -> maybe-draft routing.

    ``handle`` is pure routing (no I/O of its own beyond the injected callbacks)
    and is the unit-tested core. ``start``/``stop`` delegate to the source, whose
    real implementation owns the continual connection/thread.
    """

    def __init__(
        self,
        *,
        source: MessageSource,
        classifier: Classifier,
        apply_label: ApplyLabel,
        on_to_respond: OnToRespond,
    ) -> None:
        self._source = source
        self._classifier = classifier
        self._apply_label = apply_label
        self._on_to_respond = on_to_respond
        self._pending: list[str] = []

    def handle(self, msg: InboundMessage) -> str:
        """VI: Phân loại một thư đến, gắn nhãn, và đánh thức bước soạn nháp khi là To Respond.

        EN: Classify an inbound message, apply its label, and wake the draft step for To Respond.
        """
        category = self._classifier(msg)
        self._apply_label(msg, category)
        if category == TO_RESPOND:
            if msg.thread_id not in self._pending:
                self._pending.append(msg.thread_id)
            # A draft-trigger failure (e.g. gateway not captured yet) must not
            # crash classification/labeling — it stays pending and is retried.
            try:
                self._on_to_respond(msg)
            except Exception:
                logger.exception(
                    "inbox daemon: draft trigger failed for thread %s", msg.thread_id
                )
        return category

    def pending(self) -> list[str]:
        """VI: Các thread id đang chờ soạn nháp (điều khiển cú hích pre_llm_call).

        EN: Thread ids awaiting a draft (drives the pre_llm_call nudge).
        """
        return list(self._pending)

    def clear_pending(self, thread_id: str) -> None:
        """VI: Loại bỏ một thread id khỏi danh sách chờ soạn nháp nếu có.

        EN: Remove a thread id from the pending-draft list if present.
        """
        if thread_id in self._pending:
            self._pending.remove(thread_id)

    def start(self) -> None:
        """VI: Khởi động daemon bằng cách ủy quyền cho nguồn thư.

        EN: Start the daemon by delegating to the message source.
        """
        self._source.start(self.handle)
        logger.info("inbox daemon started")

    def stop(self) -> None:
        """VI: Dừng daemon bằng cách dừng nguồn thư.

        EN: Stop the daemon by stopping the message source.
        """
        self._source.stop()


class PubSubMessageSource:
    """VI: Nguồn thật: Gmail watch() -> chủ đề Pub/Sub, tiêu thụ qua streaming pull.

    Streaming pull là một kết nối ra ngoài; client google chạy các callback trên
    luồng nền riêng của nó (``StreamingPullFuture``). Việc giải mã một thông báo
    thành các ``InboundMessage`` (history.list kể từ historyId đã lưu, định tuyến
    theo nhãn) cần thông tin xác thực thật, nên nó nằm ở đây sau ``start()`` và
    không được unit test kiểm tra.

    EN: Real source: Gmail watch() -> Pub/Sub topic, consumed via streaming pull.

    Streaming pull is an outbound connection; the google client runs callbacks on
    its own background thread (``StreamingPullFuture``). Decoding a notification
    into ``InboundMessage``s (history.list since the stored historyId, routed by
    label) needs live creds, so it lives here behind ``start()`` and is not
    exercised by unit tests.
    """

    def __init__(self, project_id: str, subscription_id: str) -> None:
        self._project_id = project_id
        self._subscription_id = subscription_id
        self._future = None

    def start(self, on_message: OnMessage) -> None:
        """VI: Bắt đầu streaming pull và chuyển mỗi thông báo Pub/Sub thành các ``InboundMessage``.

        EN: Start streaming pull, turning each Pub/Sub notification into ``InboundMessage``s.
        """
        from google.cloud import pubsub_v1  # lazy: no dep needed for unit tests

        subscriber = pubsub_v1.SubscriberClient()
        path = subscriber.subscription_path(self._project_id, self._subscription_id)

        def _callback(pubsub_msg) -> None:
            try:
                for inbound in self._decode(pubsub_msg):
                    on_message(inbound)
                pubsub_msg.ack()
            except Exception:
                logger.exception("pubsub: decode/handle failed; nacking")
                pubsub_msg.nack()

        self._future = subscriber.subscribe(path, callback=_callback)
        logger.info("pubsub streaming pull started on %s", path)

    def _decode(self, pubsub_msg):  # pragma: no cover - needs live Gmail
        raise NotImplementedError(
            "history.list decode needs live creds"
        )

    def stop(self) -> None:
        """VI: Hủy đăng ký streaming pull nếu đang chạy.

        EN: Cancel the streaming-pull subscription if one is running.
        """
        if self._future is not None:
            self._future.cancel()
            self._future = None
