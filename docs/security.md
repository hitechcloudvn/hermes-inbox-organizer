# Security Model

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

Plugin chạy **in-process** bên trong Hermes agent. Không có network endpoint nào
cần xác thực (không HTTP server, không webhook) — kiểm soát truy cập xoay quanh
việc ai có thể điều khiển các công cụ của agent, còn bảo vệ dữ liệu xoay quanh
các token khi lưu trữ và nội dung nào được đưa tới LLM.

### Kiểm soát truy cập — owner gating

Các công cụ quản lý tài khoản (`inbox_connect_account`, `inbox_complete_connection`,
`inbox_disconnect_account`) bị giới hạn cho chủ sở hữu. Một hook `pre_tool_call`
kiểm tra người gửi của lượt hội thoại (được gán theo từng lượt qua
`pre_gateway_dispatch` → `pre_llm_call`) với `owner_matrix_ids` (trong
`inbox-oauth-client.json` / `INBOX_OWNER_MATRIX_IDS`) và chặn lời gọi từ người
không phải chủ sở hữu. Các công cụ đọc + tạo bản nháp là không phá hủy (bản nháp
không bao giờ được gửi đi).

### Refresh token khi lưu trữ

Token OAuth của Gmail được mã hóa bằng **AES-256-GCM** trước khi ghi vào data
volume (`crypto.py` / `token_store.py`). Khóa nằm trong config mount chỉ-đọc
(`inbox-encryption-key`), không bao giờ nằm trong repo hay image. Token không bao
giờ bị ghi log.

Lưu ý của dạng plugin: daemon giữ các token đã giải mã trong bộ nhớ tiến trình của
agent khi đang chạy (không cách ly tiến trình với agent) — mã hóa khi lưu trữ
giảm thiểu rủi ro lộ trên đĩa, không giảm thiểu rủi ro trong bộ nhớ của tiến trình.

### Quyền riêng tư / luồng dữ liệu

- **Tới OpenRouter** (chỉ cho phân loại LLM-fallback): người gửi, chủ đề, snippet,
  và phần thân bị cắt ngắn. Pre-classifier cục bộ rẻ (quy tắc header/người gửi)
  xử lý rất nhiều thư mà *không* cần gọi ra ngoài. OpenRouter dùng
  `OPENROUTER_API_KEY` của chính người vận hành. (Đây là bản triển khai
  một-chủ-sở hữu xử lý hộp thư của chính chủ sở hữu; không có cổng đồng ý theo
  từng tài khoản — cột `openrouter_consent_at` tồn tại nhưng hiện chưa được
  thực thi.)
- **Tới Google** (Gmail API): thay đổi nhãn và tạo bản nháp.
- Không có gì khác rời khỏi máy chủ — không analytics, không telemetry.

### Chống prompt-injection

Mọi nội dung email không đáng tin đều được bọc trong các hàng rào (fence) ngẫu
nhiên trước khi tới prompt phân loại, và system prompt đánh dấu nội dung trong
hàng rào là DATA, không bao giờ là instructions (`classifier.py`). Các trường hợp
injection được bao phủ trong `tests/test_classifier.py`.

### Bí mật

JSON OAuth client, khóa service-account `pubsub.subscriber` của Pub/Sub và khóa mã
hóa đều nằm trong config mount chỉ-đọc, thuộc sở hữu của runtime uid, không bao giờ
được commit. SA của Pub/Sub được giới hạn phạm vi `pubsub.subscriber` trên đúng một
subscription — không phải domain-wide delegation.

### Các mục tiêu ngoài phạm vi đã biết

Không cách ly đa thuê (một chủ sở hữu, dùng hộp thư của chính họ), không có công
tắc dừng (kill-switch) cho ngân sách chi phí hay cron lưu-retention dữ liệu (cố ý
bỏ qua cho bản triển khai này — có thể khôi phục từ lịch sử git nếu cần), không có
SLA chính thức hay pen test của bên thứ ba.

### Báo cáo

Ưu tiên responsible disclosure. Liên hệ: Nguyễn Thanh An <thanhan92f1@gmail.com> (HiTechCloud.VN)

---

## 🇬🇧 English

The plugin runs **in-process** inside the Hermes agent. There are no network
endpoints to authenticate (no HTTP server, no webhook) — access control is about
who can drive the agent's tools, and data protection is about tokens at rest and
what content reaches the LLM.

### Access control — owner gating

The account-management tools (`inbox_connect_account`, `inbox_complete_connection`,
`inbox_disconnect_account`) are restricted to the owner. A `pre_tool_call` hook
checks the turn's sender (bound per turn via `pre_gateway_dispatch` →
`pre_llm_call`) against `owner_matrix_ids` (in `inbox-oauth-client.json` /
`INBOX_OWNER_MATRIX_IDS`) and blocks a non-owner call. The read tools + draft
creation are non-destructive (drafts are never sent).

### Refresh tokens at rest

Gmail OAuth tokens are encrypted with **AES-256-GCM** before being written to the
data volume (`crypto.py` / `token_store.py`). The key lives in the read-only
config mount (`inbox-encryption-key`), never in the repo or the image. Tokens are
never logged.

Caveat of the plugin form: the daemon holds decrypted tokens in the agent's
process memory while running (no process isolation from the agent) — at-rest
encryption mitigates disk exposure, not in-process memory.

### Privacy / data flow

- **To OpenRouter** (LLM-fallback classification only): sender, subject, snippet,
  and a truncated body. The cheap local pre-classifier (header/sender rules)
  handles a lot of mail with *no* external call. OpenRouter uses the operator's
  own `OPENROUTER_API_KEY`. (This is a single-owner deployment processing the
  owner's own mailboxes; there is no per-account consent gate — the
  `openrouter_consent_at` column exists but is not currently enforced.)
- **To Google** (Gmail API): label changes and draft creates.
- Nothing else leaves the host — no analytics, no telemetry.

### Prompt-injection guard

All untrusted email content is wrapped in randomized fences before it reaches the
classifier prompt, and the system prompt marks fenced content as DATA, never
instructions (`classifier.py`). Injection cases are covered in
`tests/test_classifier.py`.

### Secrets

The OAuth client JSON, the Pub/Sub `pubsub.subscriber` SA key, and the encryption
key all live in the read-only config mount, owned by the runtime uid, never
committed. The Pub/Sub SA is scoped to `pubsub.subscriber` on the one
subscription — not domain-wide delegation.

### Known non-goals

No multi-tenant isolation (single owner, own mailboxes), no cost-budget
kill-switch or data-retention cron (deliberately skipped for this deployment —
recoverable from git history if ever needed), no formal SLA or third-party pen test.

### Reporting

Responsible disclosure preferred. Contact: Nguyễn Thanh An <thanhan92f1@gmail.com> (HiTechCloud.VN)
