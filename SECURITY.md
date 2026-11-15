# Security Policy

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

hermes-inbox-organizer xử lý quyền truy cập OAuth vào Gmail của bạn và nội dung thư của bạn, vì vậy các báo cáo bảo mật được tiếp nhận một cách nghiêm túc.

### Báo cáo lỗ hổng bảo mật

**Vui lòng không mở issue công khai cho các vấn đề bảo mật.**

Hãy báo cáo riêng tư qua [chức năng báo cáo lỗ hổng riêng tư](https://github.com/hitechcloudvn/hermes-inbox-organizer/security/advisories/new) của GitHub (Security → Report a vulnerability). Hãy đính kèm phiên bản bị ảnh hưởng, mô tả, và các bước tái hiện nếu có. Bạn sẽ nhận được xác nhận, cùng với kế hoạch khắc phục hoặc giảm thiểu sau khi báo cáo được phân loại.

Vui lòng cho một khoảng thời gian hợp lý để xử lý vấn đề trước khi công khai.

### Các phiên bản được hỗ trợ

Dự án này đang ở giai đoạn pre-1.0; chỉ phiên bản phát hành mới nhất nhận được các bản vá bảo mật.

| Phiên bản | Được hỗ trợ |
|---|---|
| 0.1.x   | ✅ |
| < 0.1   | ❌ |

### Mô hình bảo mật

Các giả định thiết kế mà người đánh giá nên biết:

- **Token khi lưu trữ** — các token OAuth refresh/access được mã hóa AES-256-GCM bằng khóa được cung cấp qua cấu hình chỉ-đọc (`crypto.py` / `token_store.py`). Token không bao giờ được ghi log.
- **Bí mật không bao giờ nằm trong repo** — khóa mã hóa, JSON client OAuth, và khóa service-account Pub/Sub chỉ tồn tại trong cấu hình chỉ-đọc của bản triển khai.
- **Không có bề mặt tấn công đầu vào** — các thông báo thay đổi của Gmail đến qua một streaming pull Pub/Sub *ra ngoài*. Không có webhook, endpoint công khai, hay tunnel nào để tấn công.
- **Chống chèn prompt** — nội dung email không đáng tin được bọc trong các hàng rào ngẫu nhiên trước khi đến bất kỳ LLM nào (`classifier.py`), khiến một thư được tạo dựng có chủ đích không thể điều khiển việc phân loại hoặc soạn thảo.
- **Chỉ bản nháp** — plugin soạn các bản nháp trả lời và ghi chúng vào Gmail; nó không bao giờ gửi thư thay mặt bạn.
- **Kiểm soát theo chủ sở hữu** — việc kết nối/ngắt kết nối tài khoản được giới hạn cho chủ sở hữu đã cấu hình.

Nếu bạn phát hiện một khe hở trong bất kỳ điều nào ở trên, đó chính xác là loại báo cáo chúng tôi mong muốn.

---
## 🇬🇧 English

hermes-inbox-organizer handles OAuth access to your Gmail and the contents of
your mail, so security reports are taken seriously.

### Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report privately through GitHub's
[private vulnerability reporting](https://github.com/hitechcloudvn/hermes-inbox-organizer/security/advisories/new)
(Security → Report a vulnerability). Include the affected version, a description,
and reproduction steps if you have them. You'll get an acknowledgement, and a
fix or mitigation plan once the report is triaged.

Please give a reasonable window to address the issue before any public
disclosure.

### Supported versions

This project is pre-1.0; only the latest released version receives security
fixes.

| Version | Supported |
|---|---|
| 0.1.x   | ✅ |
| < 0.1   | ❌ |

### Security model

The design assumptions a reviewer should know:

- **Tokens at rest** — OAuth refresh/access tokens are AES-256-GCM encrypted with
  a key supplied via the read-only config mount (`crypto.py` / `token_store.py`).
  Tokens are never logged.
- **Secrets are never in the repo** — the encryption key, OAuth client JSON, and
  Pub/Sub service-account key live only in the deployment's config mount.
- **No inbound surface** — Gmail change notifications arrive over an *outbound*
  Pub/Sub streaming pull. There is no webhook, public endpoint, or tunnel to
  attack.
- **Prompt-injection containment** — untrusted email content is wrapped in
  randomized fences before it reaches any LLM (`classifier.py`), so a crafted
  message cannot steer classification or drafting.
- **Drafts only** — the plugin composes draft replies and writes them to Gmail;
  it never sends mail on your behalf.
- **Owner-gating** — account connect/disconnect is gated to the configured owner.

If you find a gap in any of these, that's exactly the kind of report we want.
