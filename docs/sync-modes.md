# Sync — streaming pull + polling reconciler

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

Plugin có **một** thiết kế đồng bộ duy nhất (không có công tắc push-vs-polling, không webhook). Gmail `watch()` xuất thông báo thay đổi tới một Pub/Sub topic; plugin tiêu thụ chúng qua một subscription **streaming pull** — một kết nối gRPC *outbound*, nên không có HTTPS endpoint công khai, không có Cloudflare tunnel, và không cần xác minh OIDC.

### Vòng lặp

1. **Watch** — khi khởi động, mỗi tài khoản bật `watch()` trên `INBOX` + `SENT`
   (`runtime.start`). Một thread gia hạn (`inbox-watch-renewal`) bật lại trước khi
   hết hạn ~7 ngày để việc đồng bộ không bao giờ dừng một cách im lặng.
2. **Pull** — một subscriber streaming-pull nhận các thông báo
   (`FlowControl(max_messages=1)` + một reentrant lock để callback không thể
   drain hai lần). Mỗi thông báo kích hoạt một lần drain.
3. **Drain** — `drain_history` kéo lịch sử Gmail *kể từ cursor đã lưu*, phân loại +
   gắn nhãn cho mỗi thư INBOX mới, và xử lý các thư SENT
   (Actioned / Awaiting Reply). Cursor (`accounts.history_cursor` trong
   `state.db`) chỉ tiến tới **sau khi** một lần drain thành công, nên nếu crash nó
   sẽ drain lại thay vì bỏ qua (at-least-once).

### Reconciler (tại sao không thư nào bị mất)

Streaming pull là best-effort — Gmail có thể bỏ hoặc trì hoãn một thông báo. Vì vậy
một thread reconciler polling (`inbox-poll-reconciler`) drain lại mỗi tài khoản từ
cursor đã lưu mỗi `POLL_INTERVAL_S` (mặc định **300s**), được tuần tự hóa với các
thông báo trực tiếp qua cùng một lock. Nó dựa trên cursor nên không bao giờ xử lý
lại — nó chỉ bắt lại những gì mà một push bị bỏ lỡ đã để sót.

Hiệu ứng ròng: push cho phép phân loại gần thời gian thực (tính bằng giây);
reconciler đảm bảo bắt kịp trong vòng ~5 phút kể cả khi một push bị mất.

### Cursor cũ (stale)

Nếu cursor đã lưu cũ hơn thời gian giữ lịch sử của Gmail (~1 tuần không đồng bộ),
`drain_history` ném `StaleCursor` và lần drain sẽ đặt lại tiến về history id mới
nhất thay vì báo lỗi.

### Thông tin xác thực

- **OAuth** token theo từng tài khoản (cho `watch()` + lịch sử + ghi nhãn/draft),
  được mã hóa AES-GCM khi lưu trữ.
- Một service-account key **`pubsub.subscriber`** hẹp cho subscription
  streaming-pull (KHÔNG phải domain-wide delegation, KHÔNG phải tài khoản push
  OIDC). Xem [google-bootstrap.md](./google-bootstrap.md).

---

## 🇬🇧 English

The plugin has **one** sync design (no push-vs-polling toggle, no webhook). Gmail
`watch()` publishes change notifications to a Pub/Sub topic; the plugin consumes
them via a **streaming pull** subscription — an *outbound* gRPC connection, so
there's no public HTTPS endpoint, no Cloudflare tunnel, and no OIDC verification.

### The loop

1. **Watch** — on startup each account arms `watch()` on `INBOX` + `SENT`
   (`runtime.start`). A renewal thread (`inbox-watch-renewal`) re-arms before the
   ~7-day expiry so sync never silently stops.
2. **Pull** — a streaming-pull subscriber receives notifications
   (`FlowControl(max_messages=1)` + a reentrant lock so callbacks can't
   double-drain). Each notification triggers a drain.
3. **Drain** — `drain_history` pulls Gmail history *since the stored cursor*,
   classifies + labels each new INBOX message, and handles SENT messages
   (Actioned / Awaiting Reply). The cursor (`accounts.history_cursor` in
   `state.db`) advances **only after** a successful drain, so a crash re-drains
   rather than skips (at-least-once).

### The reconciler (why no mail is lost)

Streaming pull is best-effort — Gmail can drop or delay a notification. So a
polling reconciler thread (`inbox-poll-reconciler`) re-drains every account from
its stored cursor every `POLL_INTERVAL_S` (default **300s**), serialized with
live notifications via the same lock. It's cursor-based, so it never
reprocesses — it just catches whatever a missed push left behind.

Net effect: pushes give near-real-time triage (seconds); the reconciler
guarantees eventual catch-up within ~5 minutes even if a push is lost.

### Stale cursor

If the stored cursor is older than Gmail's history retention (~1 week of no
sync), `drain_history` raises `StaleCursor` and the drain resets forward to the
latest history id rather than erroring.

### Credentials

- Per-account **OAuth** token (for `watch()` + history + label/draft writes),
  AES-GCM encrypted at rest.
- One narrow **`pubsub.subscriber`** service-account key for the streaming-pull
  subscription (NOT domain-wide delegation, NOT a push OIDC account). See
  [google-bootstrap.md](./google-bootstrap.md).
