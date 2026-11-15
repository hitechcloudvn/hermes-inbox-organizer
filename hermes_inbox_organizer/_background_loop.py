"""VI: Vòng lặp asyncio nền chuyên dụng trên một luồng daemon.

Mẫu đã được chứng minh (lấy từ hermes-chat-recorder): một plugin sở hữu một vòng
lặp sự kiện riêng trên luồng ``daemon=True`` và nối công việc sync→async vào đó
qua ``run_coro_sync``. Dùng ở đây để (a) chạy coroutine của gateway nhằm tiêm
lượt draft tổng hợp từ luồng daemon của chúng ta, và (b) chứa các callback của
subscriber streaming-pull Pub/Sub nếu cần.

``asyncio.run`` không an toàn khi gọi từ bên trong một vòng lặp đang chạy;
``run_coroutine_threadsafe`` chỉ hoạt động từ một luồng KHÔNG phải là luồng sở
hữu vòng lặp — vì vậy cần một luồng chuyên dụng.

EN: Dedicated background asyncio loop on a daemon thread.

Proven pattern (lifted from hermes-chat-recorder): a plugin owns a private
event loop on a ``daemon=True`` thread and bridges sync→async work onto it via
``run_coro_sync``. Used here to (a) run the gateway coroutine for synthetic
draft-turn injection from our daemon thread, and (b) host the Pub/Sub
streaming-pull subscriber's callbacks if needed.

``asyncio.run`` is unsafe from inside a running loop; ``run_coroutine_threadsafe``
works only from a thread that is NOT the loop's own — hence a dedicated thread.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import threading
from collections.abc import Awaitable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")

_instance: BackgroundLoop | None = None
_lock = threading.Lock()


class BackgroundLoop:
    """VI: Vòng lặp asyncio nền chạy trên luồng daemon, cầu nối đồng bộ→bất đồng bộ.

    EN: Background asyncio loop on a daemon thread, bridging sync-to-async work.
    """

    def __init__(self) -> None:
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=self._run, name="inbox-background-loop", daemon=True
        )
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_forever()
        except Exception:  # pragma: no cover - daemon thread
            logger.exception("inbox background loop crashed")
        finally:
            with contextlib.suppress(Exception):  # pragma: no cover
                self._loop.close()

    def run_coro_sync(self, coro: Awaitable[T], *, timeout: float = 120.0) -> T:
        """VI: Chạy một coroutine trên vòng lặp nền và trả về kết quả (chờ tối đa ``timeout`` giây).

        EN: Run a coroutine on the background loop and return its result (waiting up to ``timeout`` seconds).
        """
        if not self._loop.is_running():
            raise RuntimeError("background loop is not running")
        fut = asyncio.run_coroutine_threadsafe(_ensure_coro(coro), self._loop)
        return fut.result(timeout=timeout)

    def is_running(self) -> bool:
        """VI: Cho biết vòng lặp nền còn đang chạy hay không.

        EN: Whether the background loop is still running.
        """
        return self._loop.is_running()


async def _ensure_coro(awaitable: Awaitable[T]) -> T:
    return await awaitable


def get_background_loop() -> BackgroundLoop:
    """VI: Trả về thể hiện ``BackgroundLoop`` dùng chung (tạo lần đầu khi chưa có).

    EN: Return the shared ``BackgroundLoop`` instance (created on first use).
    """
    global _instance
    with _lock:
        if _instance is None:
            _instance = BackgroundLoop()
        return _instance


def _reset_for_tests() -> None:
    global _instance
    with _lock:
        _instance = None
