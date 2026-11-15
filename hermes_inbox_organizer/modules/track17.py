"""VI: Client API 17track + các giai đoạn bưu kiện chuẩn hóa (Phase 4).

17track là một bộ tổng hợp theo dõi vận chuyển phổ quát. Chúng ta POLL nó (không
webhook — không cổng vào công khai, cùng ràng buộc khiến Gmail dùng Pub/Sub pull).
Hai lệnh: ``register`` một mã vận đơn (tốn 1 quota khi thành công; miễn phí =
100/tháng), rồi ``gettrackinfo`` để đọc trạng thái mới nhất.

Client trả về một cái nhìn CHUẨN HÓA nên module vận chuyển không bao giờ phụ thuộc
vào JSON chính xác của 17track: ``register`` -> :class:`RegisterResult`;
``get_statuses`` -> ``list[TrackStatus]``. Các giai đoạn là chuỗi
``latest_status.status`` của 17track v2.2. Nằm sau một seam
(:class:`FakeTrack17Client`) nên module được unit-test không cần mạng.

API (v2.2; base xác minh 2026-06-01): ``https://api.17track.net/track/v2.2/``,
header ``17token: <key>``, POST một mảng JSON của ``{"number","carrier"?}``,
<=40 số/lệnh, 3 req/s. Client live dùng ``urllib`` stdlib (không thêm dep) và
chưa được kiểm thử trong unit test (giống client Gmail live). Đường dẫn trường
``track_info`` chính xác + các mã lỗi quota được đánh dấu để xác minh live trong
lần poll đầu tiên.

EN: 17track API client + normalized package stages (Phase 4).

17track is a universal carrier-tracking aggregator. We POLL it (no webhooks — no
public ingress, the same constraint that makes Gmail use Pub/Sub pull). Two
calls: ``register`` a tracking number (costs 1 quota on success; free tier =
100/month), then ``gettrackinfo`` to read its latest status.

The client returns a NORMALIZED view so the shipping module never depends on
17track's exact JSON: ``register`` -> :class:`RegisterResult`; ``get_statuses``
-> ``list[TrackStatus]``. Stages are 17track v2.2's ``latest_status.status``
strings. Behind a seam (:class:`FakeTrack17Client`) so the module is unit-tested
without network.

API (v2.2; base verified 2026-06-01): ``https://api.17track.net/track/v2.2/``,
header ``17token: <key>``, POST a JSON array of ``{"number","carrier"?}``,
<=40 numbers/call, 3 req/s. The live client uses stdlib ``urllib`` (no new dep)
and is untested in units (like the live Gmail client). The exact ``track_info``
field path + quota error codes are flagged for live confirmation on first poll.
"""

from __future__ import annotations

import json
import logging
import urllib.request
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger(__name__)

_BASE = "https://api.17track.net/track/v2.2"
MAX_PER_CALL = 40

# Normalized stages == 17track v2.2 ``latest_status.status`` values.
STAGE_NOT_FOUND = "NotFound"
STAGE_INFO_RECEIVED = "InfoReceived"
STAGE_IN_TRANSIT = "InTransit"
STAGE_OUT_FOR_DELIVERY = "OutForDelivery"
STAGE_AVAILABLE_FOR_PICKUP = "AvailableForPickup"
STAGE_DELIVERY_FAILURE = "DeliveryFailure"
STAGE_DELIVERED = "Delivered"
STAGE_EXCEPTION = "Exception"
STAGE_EXPIRED = "Expired"

# Reaching one of these stops polling the parcel (it won't progress further).
TERMINAL_STAGES = frozenset({STAGE_DELIVERED, STAGE_EXCEPTION, STAGE_EXPIRED})


@dataclass(frozen=True)
class TrackStatus:
    """VI: Trạng thái theo dõi đã chuẩn hóa cho một mã vận đơn.

    EN: Normalized tracking status for one tracking number.
    """

    number: str
    stage: str | None  # a normalized stage, or None when not yet known / not found
    sub_status: str = ""
    carrier: int | None = None


@dataclass(frozen=True)
class RegisterResult:
    """VI: Kết quả đăng ký mã vận đơn với 17track (chấp nhận / từ chối / hết quota).

    EN: Result of registering tracking numbers with 17track (accepted / rejected / quota exhausted).
    """

    accepted: list = field(default_factory=list)  # tracking numbers 17track accepted
    rejected: dict = field(default_factory=dict)  # number -> reason
    quota_exhausted: bool = False


class Track17Client(Protocol):
    """VI: Giao diện client 17track mà module vận chuyển phụ thuộc vào.

    EN: The 17track client interface the shipping module depends on.
    """

    def register(self, numbers: list) -> RegisterResult:
        """VI: Đăng ký (các) mã vận đơn để theo dõi.

        EN: Register tracking numbers for tracking.
        """
        ...

    def get_statuses(self, numbers: list) -> list:
        """VI: Lấy trạng thái theo dõi mới nhất cho (các) mã vận đơn.

        EN: Fetch the latest tracking statuses for tracking numbers.
        """
        ...


class FakeTrack17Client:
    """VI: Client có kịch bản cho test — không dùng mạng.

    ``statuses`` ánh xạ số -> :class:`TrackStatus` (hoặc một chuỗi giai đoạn trần).
    ``register`` chấp nhận mọi thứ không nằm trong ``reject`` và ghi lại các lệnh gọi.

    EN: Scripted client for tests — no network.

    ``statuses`` maps number -> :class:`TrackStatus` (or a bare stage string).
    ``register`` accepts everything not in ``reject`` and records its calls.
    """

    def __init__(self, statuses=None, reject=None, quota_exhausted=False) -> None:
        self._statuses = dict(statuses or {})
        self._reject = set(reject or ())
        self._quota = quota_exhausted
        self.registered: list = []
        self.status_calls: list = []

    def register(self, numbers: list) -> RegisterResult:
        """VI: Mô phỏng đăng ký: chấp nhận mọi số không nằm trong ``reject``.

        EN: Simulate registration: accept everything not in ``reject``.
        """
        if self._quota:
            return RegisterResult(quota_exhausted=True)
        accepted, rejected = [], {}
        for n in numbers:
            if n in self._reject:
                rejected[n] = "rejected"
            else:
                accepted.append(n)
                self.registered.append(n)
        return RegisterResult(accepted=accepted, rejected=rejected)

    def set_status(self, number, stage, sub_status="", carrier=None) -> None:
        """VI: Ghi trạng thái giả cho một mã vận đơn trong kịch bản test.

        EN: Record a scripted status for one tracking number.
        """
        self._statuses[number] = TrackStatus(number, stage, sub_status, carrier)

    def get_statuses(self, numbers: list) -> list:
        """VI: Trả về trạng thái đã kịch bản cho các mã vận đơn được truyền vào.

        EN: Return the scripted statuses for the given tracking numbers.
        """
        self.status_calls.append(list(numbers))
        out = []
        for n in numbers:
            s = self._statuses.get(n)
            if isinstance(s, TrackStatus):
                out.append(s)
            elif isinstance(s, str):
                out.append(TrackStatus(n, s))
            else:
                out.append(TrackStatus(n, None))
        return out


class HttpTrack17Client:
    """VI: Client live trên HTTP API 17track v2.2 (urllib stdlib). Chưa được unit-test.

    EN: Live client over the 17track v2.2 HTTP API (stdlib urllib). Not unit-tested.
    """

    def __init__(self, api_key: str, *, base: str = _BASE, timeout: float = 30.0) -> None:
        self._key = api_key
        self._base = base.rstrip("/")
        self._timeout = timeout

    def _post(self, path: str, payload: list) -> dict:
        data = json.dumps(payload).encode()
        req = urllib.request.Request(
            f"{self._base}/{path}",
            data=data,
            headers={"Content-Type": "application/json", "17token": self._key},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            return json.loads(resp.read().decode() or "{}")

    def register(self, numbers: list) -> RegisterResult:
        """VI: Đăng ký mã vận đơn với 17track qua endpoint register (tốn quota khi thành công).

        EN: Register tracking numbers with 17track via the register endpoint (costs quota on success).
        """
        if not numbers:
            return RegisterResult()
        resp = self._post("register", [{"number": n} for n in numbers[:MAX_PER_CALL]])
        data = resp.get("data") or {}
        accepted = [a.get("number") for a in (data.get("accepted") or []) if a.get("number")]
        rejected: dict = {}
        quota = False
        for r in data.get("rejected") or []:
            num = r.get("number", "")
            err = r.get("error") or {}
            msg = str(err.get("message", "rejected"))
            if "quota" in msg.lower() or "limit" in msg.lower():
                quota = True
            if num:
                rejected[num] = msg
        return RegisterResult(accepted=accepted, rejected=rejected, quota_exhausted=quota)

    def get_statuses(self, numbers: list) -> list:
        """VI: Đọc trạng thái theo dõi mới nhất từ 17track qua endpoint gettrackinfo.

        EN: Read the latest tracking statuses from 17track via the gettrackinfo endpoint.
        """
        if not numbers:
            return []
        resp = self._post("gettrackinfo", [{"number": n} for n in numbers[:MAX_PER_CALL]])
        data = resp.get("data") or {}
        out = []
        for a in data.get("accepted") or []:
            info = a.get("track_info") or {}
            latest = info.get("latest_status") or {}
            out.append(
                TrackStatus(
                    number=a.get("number", ""),
                    stage=latest.get("status"),
                    sub_status=str(latest.get("sub_status", "") or ""),
                    carrier=a.get("carrier"),
                )
            )
        for r in data.get("rejected") or []:
            if r.get("number"):
                out.append(TrackStatus(number=r["number"], stage=None))
        return out
