# Hermes self-install runbook

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

**Tài liệu này được viết cho agent Hermes thực thi.** Một chủ sở hữu là con người có thể đưa tài liệu này cho bạn và nói *"hãy đọc cái này và cài đặt + cấu hình inbox organizer cho tôi."* Nhiệm vụ của bạn là cài plugin `hermes-inbox-organizer` vào triển khai của chính bạn, kết nối cấu hình của nó, và hướng dẫn chủ sở hữu qua những phần chỉ họ mới có thể làm (thiết lập Google Cloud diễn ra trong trình duyệt của họ, dưới tài khoản Google của họ — bạn không thể làm điều đó thay họ).

Hãy xử lý từng giai đoạn theo thứ tự. Sau mỗi giai đoạn, chạy bước **Verify** của nó trước khi chuyển tiếp. Nếu một bước verify thất bại, hãy sửa nó (xem **Khắc phục sự cố**) trước khi tiếp tục — không đi tiếp qua một bước đang hỏng.

---

### Quy tắc cho bạn (agent)

1. **Bí mật.** Bạn sẽ xử lý một bí mật client OAuth, một khóa service-account, và một khóa mã hóa AES. Không bao giờ in lại một bí mật cho người dùng, không bao giờ in bí mật vào câu trả lời hay bất kỳ log nào, và không bao giờ dán bí mật vào một tin nhắn chat. Hãy ghi thẳng chúng vào các tệp với `chmod 600`. Khi cần đề cập đến một bí mật, hãy đề cập đến *tệp*, không phải nội dung của nó.
2. **Xác nhận trước các hành động không thể hoàn tác hoặc hướng ra ngoài.** Hãy hỏi chủ sở hữu trước bất kỳ điều gì chạm vào tài khoản Google của họ, gửi dữ liệu cho Google, hoặc khởi động lại Hermes của họ. Sự chấp thuận cho một bước không phải là sự chấp thuận cho bước tiếp theo.
3. **Khóa mã hóa là then chốt.** Hãy tạo nó một lần và giữ ổn định. Nếu nó bị mất hoặc thay đổi, mọi token Gmail đã lưu trữ trở nên không thể giải mã và tất cả tài khoản phải được kết nối lại. Không bao giờ tạo lại nó khi cài đặt lại.
4. **Idempotent.** Chạy lại một bước phải an toàn. Kiểm tra xem một tệp/thư mục/env đã tồn tại chưa trước khi ghi đè, và hỏi trước khi ghi đè.
5. **Nếu bạn không thể chạy lệnh shell hoặc ghi tệp** trong triển khai này, hãy chuyển sang *chế độ hướng dẫn*: đưa cho chủ sở hữu từng lệnh/tệp chính xác để họ tự chạy và chờ họ xác nhận trước bước tiếp theo.

---

### Giai đoạn 0 — Kiểm tra trước

**Mục tiêu:** xác định môi trường bạn đang cài vào.

1. Xác nhận khả năng của bạn: bạn có thể chạy lệnh shell và ghi tệp không? Nếu không, hãy dùng chế độ hướng dẫn (xem quy tắc 5).
2. Tìm Hermes CLI và môi trường Python của nó — plugin **phải** cài vào đúng trình thông dịch chạy `hermes`:
   ```sh
   which hermes
   head -1 "$(which hermes)"     # the shebang shows the python it uses
   ```
   Dùng `pip` của trình thông dịch đó cho Giai đoạn 2 (ví dụ `/opt/hermes/.venv/bin/pip`).
3. Xác định các gốc cấu hình + dữ liệu. Mặc định (dưới `HERMES_HOME=/opt/data`):
   - `INBOX_CONFIG_DIR` → `/opt/data/config` (bí mật bạn cài đặt; mount chỉ-đọc)
   - `INBOX_DATA_DIR` → `/opt/data/inbox-organizer` (SQLite DB + token được mã hóa; ghi được)

   Nếu `HERMES_HOME` của triển khai này khác đi, hãy đặt cả hai env var trong Giai đoạn 3.
4. Ghi nhận hình thái triển khai, vì nó ảnh hưởng đến *mức độ bền vững* của bản cài đặt và *cách* các env var được đặt:
   - **Hermes Docker / `docker compose`** (phổ biến nhất): một `pip install` lúc runtime
     trong container cho bạn chạy ngay bây giờ, nhưng sẽ **bị xóa khi build lại image
     tiếp theo** (`docker compose up --build`). Để cài đặt bền vững, hãy đưa gói vào
     image — xem [`docs/setup.md`](docs/setup.md). Đặt các env var trong
     `environment:` / `.env` của service.
   - **Hermes bare / systemd:** bản cài đặt lúc runtime tồn tại lâu dài. Đặt các env var trong
     file unit hoặc profile shell.

**Verify:** bạn có thể nêu được (a) pip cần dùng, (b) thư mục cấu hình, (c) thư mục dữ liệu, và (d) cách các env var được đặt cho triển khai này. Hãy báo cho chủ sở hữu bốn điều này trước khi tiếp tục.

---

### Giai đoạn 1 — Google Cloud (chủ sở hữu làm; bạn hướng dẫn)

**Mục tiêu:** một dự án Google Cloud cho phép plugin đọc/gắn nhãn Gmail và nhận thông báo thay đổi qua Pub/Sub. **Bạn không thể làm điều này** — nó cần đăng nhập Google và trình duyệt của chủ sở hữu. Hãy hướng dẫn họ từng bước một và thu thập các giá trị liệt kê ở cuối. Ảnh chụp màn hình đầy đủ:
[`docs/google-bootstrap.md`](docs/google-bootstrap.md).

Hãy bảo chủ sở hữu:

1. **Dự án** — [console.cloud.google.com](https://console.cloud.google.com/) →
   tạo hoặc chọn một dự án (ví dụ `hermes-inbox`).
2. **Bật API** — bật **Gmail API** (`gmail.googleapis.com`) và **Cloud
   Pub/Sub API** (`pubsub.googleapis.com`).
3. **OAuth consent screen** — *External*. Thêm scope **`gmail.modify`** (đó là
   scope duy nhất plugin thực sự yêu cầu — nó bao gồm đọc, gắn nhãn,
   và ghi bản nháp; plugin không bao giờ gửi thư). Thêm chủ sở hữu làm **Test
   User**, rồi **Publish App** lên **Production**. Việc publish quan trọng: một
   consent screen "Testing" làm các refresh token hết hạn sau **7 ngày**, khiến
   mọi tài khoản bị ngắt kết nối âm thầm. (Xem [`docs/oauth-modes.md`](docs/oauth-modes.md).)
4. **OAuth client** — Credentials → Create OAuth client ID → **Web application**.
   Với **Authorized redirect URI**, dùng một trang tĩnh chỉ hiển thị mã xác thực
   để copy-paste: tái sử dụng `https://inbox-organizer.northbound.run/` (trang này
   không giữ bí mật nào — OAuth client vẫn thuộc về họ) hoặc tự host trang
   `oauth-callback/`. Lưu lại **client ID** và **client secret**.
5. **Pub/Sub** — tạo một **Topic** (ví dụ `gmail-notifications`), rồi trên đó một
   **Subscription** với kiểu giao hàng **Pull** (ví dụ `gmail-inbox-organizer-pull`).
6. **Cho phép Gmail publish** — trên topic → Permissions → thêm principal
   `gmail-api-push@system.gserviceaccount.com` với vai trò **Pub/Sub Publisher**.
7. **Khóa subscriber** — tạo một service account, cấp cho nó
   **`roles/pubsub.subscriber`** *trên subscription* (không phải toàn dự án), và
   tải xuống **JSON key** của nó.

**Thu thập từ chủ sở hữu** (hỏi họ dán những thứ này cho bạn; coi hai mục cuối là bí mật):
- **client_id**, **client_secret** OAuth, và **redirect_uri** họ đã đăng ký
- **project id** Pub/Sub, **topic** (đường dẫn đầy đủ `projects/<id>/topics/<name>`), tên **subscription**
- **JSON key của service-account** (một bí mật)
- một **API key cho classifier LLM** — OpenRouter
  ([openrouter.ai/keys](https://openrouter.ai/keys)) theo mặc định, hoặc một khóa cho bất kỳ
  endpoint tương thích OpenAI nào bạn thích (một bí mật)
- **Hermes user ID** của họ — id người gửi mà gateway báo cáo cho kênh
  họ nói chuyện với Hermes, dùng để ủy quyền cho họ là chủ sở hữu được phép kết nối
  các hộp thư. Nó **không** riêng Matrix (Matrix chỉ là `@you:your-homeserver`;
  backend khác dùng id của nền tảng đó). Nếu không chắc, xem "Tìm owner ID"
  trong Giai đoạn 3.

**Verify:** bạn có tất cả những thứ ở trên. Không tiếp tục cho đến khi consent screen ở trạng thái
**Published / Production**.

---

### Giai đoạn 2 — Cài đặt + bật plugin

**Mục tiêu:** plugin được cài trong môi trường Hermes và được bật.

```sh
# use the pip from Phase 0
<hermes-pip> install "hermes-inbox-organizer[live]"
hermes plugins enable inbox_organizer
```

`[live]` kéo các dependency Gmail / Pub/Sub / OpenRouter. `enable` là cần thiết
vì các plugin pip/entry-point là opt-in.

**Verify:**
```sh
hermes plugins list        # inbox_organizer → enabled
```
Nếu nó không xuất hiện: `HERMES_PLUGINS_DEBUG=1 hermes plugins list`.

---

### Giai đoạn 3 — Ghi cấu hình + bí mật

**Mục tiêu:** bốn tệp cấu hình tồn tại trong `INBOX_CONFIG_DIR` và các env var
bắt buộc được đặt. Áp dụng quy tắc 1 trong suốt quá trình.

1. Tạo các thư mục và khóa chúng lại:
   ```sh
   mkdir -p "$INBOX_CONFIG_DIR" "$INBOX_DATA_DIR"
   chmod 700 "$INBOX_CONFIG_DIR"
   ```
2. Ghi tệp OAuth client — `$INBOX_CONFIG_DIR/inbox-oauth-client.json`:
   ```json
   {
     "client_id": "<client_id>",
     "client_secret": "<client_secret>",
     "redirect_uri": "https://inbox-organizer.northbound.run/",
     "owner_matrix_ids": ["@you:your-homeserver"]
   }
   ```
   `owner_matrix_ids` ở đây là **danh sách cho phép chủ sở hữu** — các Hermes user ID
   được phép kết nối/ngắt kết nối hộp thư. Mặc dù tên trường là vậy, nó **không
   riêng Matrix**: hãy đặt bất kỳ id người gửi nào mà gateway của bạn báo cáo cho
   kênh của chủ sở hữu (Matrix `@you:server`, hoặc id của backend khác). Đặt nó trong
   tệp này (thay vì một env var) có nghĩa là nó sống sót qua việc build lại container.
   (Một Google `client_secret.json` với node `web`/`installed` cũng được chấp nhận thay cho
   cấu trúc phẳng.)

   **Tìm owner ID:** đó là `source.user_id` của gateway cho chủ sở hữu. Trên
   Matrix đó là `@user:homeserver` của họ. Nếu bạn không chắc trên backend khác,
   hãy đặt tạm thời nó, thử Giai đoạn 6, và nếu việc kết nối bị từ chối, hãy kiểm tra
   log gateway Hermes tìm id người gửi bị từ chối và dùng đúng giá trị đó.
3. Ghi cấu hình Pub/Sub — `$INBOX_CONFIG_DIR/inbox-pubsub.json`:
   ```json
   {
     "project": "<project-id>",
     "topic": "projects/<project-id>/topics/<topic-name>",
     "subscription": "<subscription-name>"
   }
   ```
4. Ghi khóa service-account — `$INBOX_CONFIG_DIR/inbox-pubsub-sa.json` —
   nguyên văn từ JSON mà chủ sở hữu đã tải xuống.
5. Tạo khóa mã hóa AES (**một lần, rồi không bao giờ thay đổi nó** — xem quy tắc 3):
   ```sh
   openssl rand -hex 32 > "$INBOX_CONFIG_DIR/inbox-encryption-key"
   ```
6. Khóa mọi bí mật:
   ```sh
   chmod 600 "$INBOX_CONFIG_DIR"/inbox-*.json "$INBOX_CONFIG_DIR/inbox-encryption-key"
   ```
7. Đặt các biến môi trường trong môi trường Hermes (phương pháp theo Giai đoạn 0):
   - **Classifier LLM** — bắt buộc cho việc phân loại bằng LLM. Mặc định: đặt
     **`OPENROUTER_API_KEY`**. Với bất kỳ endpoint tương thích OpenAI nào khác, đặt
     **`INBOX_CLASSIFIER_API_KEY`** + **`INBOX_CLASSIFIER_BASE_URL`** thay thế
     (và tùy chọn **`INBOX_CLASSIFIER_MODEL`**).
   - **Danh sách cho phép chủ sở hữu** — bắt buộc để việc kết nối tài khoản hoạt động. Bạn đã đặt nó
     qua `owner_matrix_ids` trong JSON OAuth (bước 2); cách khác là đặt
     **`INBOX_OWNER_MATRIX_IDS`** (phân tách bằng dấu phẩy), giá trị này được ưu tiên. Cả hai
     đều chứa id người gửi của gateway (mọi backend, không chỉ Matrix). Cổng này
     **fail-closed**: khi không đặt cái nào, *mọi* lượt thử kết nối đều bị từ chối,
     kể cả của chủ sở hữu.
   - `HERMES_API_URL` — *tùy chọn*; endpoint tương thích OpenAI của Hermes cục bộ.
     Chỉ cần cho các bản nháp trả lời; triage + gắn nhãn chạy mà không cần nó.
   - `API_SERVER_KEY` — *tùy chọn*; bearer token nếu endpoint wake yêu cầu.
   - `INBOX_CONFIG_DIR` / `INBOX_DATA_DIR` — chỉ nếu bạn chọn đường dẫn không mặc định.

**Verify (không in bí mật):**
```sh
ls -l "$INBOX_CONFIG_DIR"          # 4 files, all mode 600
python -c "import json,os; d=os.environ['INBOX_CONFIG_DIR']; \
  [json.load(open(os.path.join(d,f))) for f in ('inbox-oauth-client.json','inbox-pubsub.json','inbox-pubsub-sa.json')]; \
  print('json files parse OK')"
```

---

### Giai đoạn 4 — Khởi động daemon khi boot (khuyến nghị)

**Mục tiêu:** daemon triage khởi động khi gateway boot, không chỉ ở lượt agent đầu tiên sau khi khởi động lại.

Hermes nạp các plugin entry-point một cách lười biếng, vì vậy sau khi khởi động lại daemon vẫn ngủ cho đến khi có ai đó chat lần sau. Một hook `gateway:startup` khắc phục điều đó. Hook nằm trong repo tại `deploy/hooks/inbox-organizer-boot/` và **không** được đóng gói trong wheel pip, vì vậy hãy tự tạo hai tệp trong thư mục hooks của Hermes
(thường là `~/.hermes/hooks/inbox-organizer-boot/`):

`HOOK.yaml`:
```yaml
name: inbox-organizer-boot
description: Load entry-point plugins at gateway startup so the triage daemon starts at boot.
events:
  - gateway:startup
```

`handler.py`:
```python
async def handle(event_type, context):  # Hermes hook signature
    tag = "[inbox-organizer-boot]"
    try:
        from hermes_cli.plugins import discover_plugins
        print(f"{tag} {event_type}: loading entry-point plugins at boot", flush=True)
        discover_plugins()  # idempotent; runs each enabled plugin's register()
        print(f"{tag} discover_plugins() complete", flush=True)
    except Exception as exc:
        import traceback
        print(f"{tag} FAILED to load plugins at startup: {exc!r}", flush=True)
        traceback.print_exc()
```

(Nếu bạn có quyền truy cập repo, sao chép `deploy/hooks/inbox-organizer-boot/` nguyên văn là
tương đương và bao gồm một health log daemon-thread.)

**Verify:** cả hai tệp tồn tại dưới thư mục hooks.

---

### Giai đoạn 5 — Khởi động lại + xác minh nạp

**Mục tiêu:** Hermes khởi động lại với env + plugin mới và daemon được kích hoạt.

1. Hỏi chủ sở hữu trước khi khởi động lại (quy tắc 2), rồi khởi động lại Hermes theo cách
   triển khai này làm (`docker compose up -d hermes`, `systemctl restart hermes`, …).
2. Xác minh:
   ```sh
   hermes plugins list        # inbox_organizer → enabled
   ```
3. Trong một phiên chat, xác nhận `/plugins` liệt kê nó là đã nạp, rồi gọi công cụ
   `inbox_list_accounts` — nó phải trả về một danh sách rỗng (chưa có tài khoản nào),
   chứng tỏ các công cụ đã được kết nối và cấu hình được nạp không lỗi.

**Nếu `inbox_list_accounts` báo lỗi về cấu hình**, hãy kiểm tra lại Giai đoạn 3 (đường dẫn tệp,
tính hợp lệ của JSON, env var) trước khi kết nối một tài khoản.

---

### Giai đoạn 6 — Kết nối Gmail của chủ sở hữu

**Mục tiêu:** hộp thư của chủ sở hữu được kết nối và được triage.

1. Gọi **`inbox_connect_account`**. Nó trả về một `auth_url` đăng nhập Google.
2. Đưa liên kết cho chủ sở hữu. Bảo họ: chấp thuận quyền truy cập; nếu Google hiển thị
   một màn hình *"hasn't verified this app"*, chọn **Advanced → Continue** (điều này là
   bình thường với client của chính họ); rồi sao chép **mã hiển thị trên trang callback**.
3. Khi họ dán mã trở lại, gọi **`inbox_complete_connection`** với
   `{ "code": "<pasted code>" }`. Thành công trông như
   `{"ok": true, "email": "...", "live": true}`.
   - `live: true` → tài khoản được thêm nóng vào daemon đang chạy.
   - `live: false` → token được lưu; nó sẽ được nạp ở lần khởi động lại sau.
   - Các công cụ này được **chặn theo chủ sở hữu**; nếu bạn nhận *"restricted to this assistant's
     owner,"* user ID gateway của người gọi không có trong danh sách cho phép — hãy sửa Giai đoạn 3 bước 7.
4. Lặp lại cho bất kỳ hộp thư bổ sung nào.

**Verify:**
- `inbox_list_accounts` giờ liệt kê địa chỉ đã kết nối.
- Nhờ chủ sở hữu tự gửi cho mình một email thử; nó phải nhận được một nhãn đánh số
  trong vài giây (push Pub/Sub) hoặc vài phút (reconciler polling).

---

### Giai đoạn 7 — Bàn giao cho chủ sở hữu

Hãy nói với chủ sở hữu, bằng ngôn ngữ đơn giản:

- Điều gì đang chạy: mỗi email mới được phân loại và gắn nhãn `1: To Respond` …
  `8: Marketing`; chỉ *To Respond* và *FYI* ở lại hộp thư đến, phần còn lại được lưu trữ.
  Với *To Respond*, bạn sẽ soạn một bản nháp trả lời theo giọng của họ (**chỉ bản nháp — không bao giờ
  được gửi**).
- Cách thêm/bỏ hộp thư sau này: chỉ cần yêu cầu bạn *"connect another Gmail"* hoặc
  *"disconnect <email>"*.
- Công tắc dừng khẩn cấp: đặt `INBOX_LABELS_ENABLED=0` để giữ phân loại + soạn thảo
  nhưng dừng mọi thay đổi nhãn/lưu trữ/chuyển thư.
- Các đẩy chủ động (mã 2FA, cập nhật vận chuyển — nếu các module đó được bật) sẽ
  đến **kênh home** của Hermes trên bất kỳ nền tảng nào bạn dùng. Chạy `/sethome` trong
  phòng bạn muốn chúng được gửi đến, hoặc đặt `INBOX_NOTIFY_TARGET` để ghi đè.
- Trạng thái nằm ở đâu: `INBOX_DATA_DIR` (SQLite `state.db` + token được mã hóa). Hãy sao lưu
  **khóa mã hóa** ở nơi an toàn — mất nó có nghĩa là phải kết nối lại mọi
  tài khoản.
- Nếu đây là triển khai Docker và bạn đã `pip install` lúc runtime, hãy nhắc họ
  đưa gói vào image để tăng độ bền ([`docs/setup.md`](docs/setup.md)).

---

### Khắc phục sự cố

- **Plugin không có trong `hermes plugins list`** — đã cài vào sai môi trường Python
  (Giai đoạn 0); cài lại với chính pip của `hermes` CLI. Sau đó
  `HERMES_PLUGINS_DEBUG=1 hermes plugins list`.
- **Nạp được nhưng không có triage sau khi khởi động lại** — boot hook (Giai đoạn 4) bị thiếu, hoặc
  daemon không được kích hoạt. Kiểm tra stdout của Hermes tìm các dòng `[inbox-organizer-boot]`.
- **`OAuth client not configured`** — `inbox-oauth-client.json` bị thiếu,
  không đọc được, hoặc thiếu `client_id`/`client_secret`/`redirect_uri`.
- **`no refresh_token in token response`** — consent screen không cấp
  quyền truy cập ngoại tuyến; hãy đảm bảo app đã được Publish và chủ sở hữu đã thực hiện một consent mới.
- **Các tài khoản bị ngắt kết nối mỗi ~7 ngày** — consent screen vẫn ở trạng thái
  "Testing." Hãy publish nó lên Production và kết nối lại ([`docs/oauth-modes.md`](docs/oauth-modes.md)).
- **`restricted to this assistant's owner`** — danh sách cho phép chủ sở hữu trống hoặc
  không chứa user ID gateway của người gọi (Giai đoạn 3 bước 7).
- **Không có nhãn nào xuất hiện** — xác nhận `INBOX_LABELS_ENABLED` không phải `0`, và khóa
  subscriber Pub/Sub có `roles/pubsub.subscriber` trên subscription.

Để biết chi tiết sâu hơn, xem [`docs/setup.md`](docs/setup.md), [`docs/sync-modes.md`](docs/sync-modes.md),
và [`docs/security.md`](docs/security.md).

---
## 🇬🇧 English

**This document is written for the Hermes agent to execute.** A human owner can
hand it to you and say *"read this and install + configure the inbox organizer
for me."* Your job is to install the `hermes-inbox-organizer` plugin into your own
deployment, wire up its config, and walk the owner through the parts only they
can do (the Google Cloud setup happens in their browser, under their Google
account — you cannot do that for them).

Work through the phases in order. After each phase, run its **Verify** step
before moving on. If a verify fails, fix it (see **Troubleshooting**) before
continuing — do not push past a broken step.

---

### Rules for you (the agent)

1. **Secrets.** You will handle an OAuth client secret, a service-account key, and
   an AES encryption key. Never echo a secret back to the user, never print one
   into your reply or any log, and never paste one into a chat message. Write
   them straight to files with `chmod 600`. When you must refer to one, refer to
   the *file*, not its contents.
2. **Confirm before irreversible or outward actions.** Ask the owner before
   anything that touches their Google account, sends data to Google, or restarts
   their Hermes. Approval for one step is not approval for the next.
3. **The encryption key is load-bearing.** Generate it once and keep it stable.
   If it is ever lost or changed, every stored Gmail token becomes undecryptable
   and all accounts must be reconnected. Never regenerate it on a reinstall.
4. **Idempotent.** Re-running a step should be safe. Check whether a file/dir/env
   already exists before overwriting it, and ask before clobbering.
5. **If you cannot run shell commands or write files** in this deployment, switch
   to *guide mode*: give the owner each exact command/file to run themselves and
   wait for them to confirm before the next step.

---

### Phase 0 — Preflight

**Goal:** locate the environment you're installing into.

1. Confirm your capabilities: can you run shell commands and write files? If not,
   use guide mode (see rule 5).
2. Find the Hermes CLI and its Python environment — the plugin **must** install
   into the same interpreter that runs `hermes`:
   ```sh
   which hermes
   head -1 "$(which hermes)"     # the shebang shows the python it uses
   ```
   Use that interpreter's `pip` for Phase 2 (e.g. `/opt/hermes/.venv/bin/pip`).
3. Determine the config + data roots. Defaults (under `HERMES_HOME=/opt/data`):
   - `INBOX_CONFIG_DIR` → `/opt/data/config` (secrets you install; read-only mount)
   - `INBOX_DATA_DIR` → `/opt/data/inbox-organizer` (SQLite DB + encrypted tokens; writable)

   If this deployment's `HERMES_HOME` differs, set both env vars in Phase 3.
4. Note the deployment shape, because it changes *how durable* the install is and
   *how* env vars are set:
   - **Docker / `docker compose` Hermes** (most common): a runtime `pip install`
     inside the container gets you running now, but is **wiped on the next image
     rebuild** (`docker compose up --build`). For a durable install, bake the
     package into the image instead — see [`docs/setup.md`](docs/setup.md). Set
     env vars in the service's `environment:` / `.env`.
   - **Bare / systemd Hermes:** the runtime install persists. Set env vars in the
     unit file or shell profile.

**Verify:** you can name (a) the pip to use, (b) the config dir, (c) the data
dir, and (d) how env vars get set for this deployment. Tell the owner these four
things before continuing.

---

### Phase 1 — Google Cloud (owner does this; you guide)

**Goal:** a Google Cloud project that lets the plugin read/label Gmail and
receive change notifications over Pub/Sub. **You cannot do this** — it needs the
owner's Google login and browser. Walk them through it one step at a time and
collect the values listed at the end. Full screenshots:
[`docs/google-bootstrap.md`](docs/google-bootstrap.md).

Tell the owner to:

1. **Project** — [console.cloud.google.com](https://console.cloud.google.com/) →
   create or pick a project (e.g. `hermes-inbox`).
2. **Enable APIs** — enable **Gmail API** (`gmail.googleapis.com`) and **Cloud
   Pub/Sub API** (`pubsub.googleapis.com`).
3. **OAuth consent screen** — *External*. Add the **`gmail.modify`** scope (that
   is the only scope the plugin actually requests — it covers reading, labeling,
   and writing drafts; the plugin never sends mail). Add the owner as a **Test
   User**, then **Publish App** to **Production**. Publishing matters: a "Testing"
   consent screen expires refresh tokens after **7 days**, which silently
   disconnects every account. (See [`docs/oauth-modes.md`](docs/oauth-modes.md).)
4. **OAuth client** — Credentials → Create OAuth client ID → **Web application**.
   For **Authorized redirect URI**, use a static page that just displays the auth
   code for copy-paste: reuse `https://inbox-organizer.northbound.run/` (it holds
   no secrets — the OAuth client stays theirs) or self-host the `oauth-callback/`
   page. Save the **client ID** and **client secret**.
5. **Pub/Sub** — create a **Topic** (e.g. `gmail-notifications`), then on it a
   **Subscription** with delivery type **Pull** (e.g. `gmail-inbox-organizer-pull`).
6. **Let Gmail publish** — on the topic → Permissions → add principal
   `gmail-api-push@system.gserviceaccount.com` with role **Pub/Sub Publisher**.
7. **Subscriber key** — create a service account, grant it
   **`roles/pubsub.subscriber`** *on the subscription* (not project-wide), and
   download its **JSON key**.

**Collect from the owner** (ask them to paste these to you; treat the last two as
secrets):
- OAuth **client_id**, **client_secret**, and the **redirect_uri** they registered
- Pub/Sub **project id**, **topic** (full path `projects/<id>/topics/<name>`), **subscription** name
- the **service-account key JSON** (a secret)
- a **classifier LLM API key** — OpenRouter
  ([openrouter.ai/keys](https://openrouter.ai/keys)) by default, or a key for any
  OpenAI-compatible endpoint you prefer (a secret)
- their **Hermes user ID** — the sender id the gateway reports for the channel
  they talk to Hermes on, used to authorize them as the owner who may connect
  mailboxes. It is **not** Matrix-specific (Matrix is just `@you:your-homeserver`;
  another backend uses that platform's id). If unsure, see "Finding the owner ID"
  in Phase 3.

**Verify:** you have all of the above. Do not proceed until the consent screen is
**Published / Production**.

---

### Phase 2 — Install + enable the plugin

**Goal:** the plugin is installed in the Hermes env and enabled.

```sh
# use the pip from Phase 0
<hermes-pip> install "hermes-inbox-organizer[live]"
hermes plugins enable inbox_organizer
```

`[live]` pulls the Gmail / Pub/Sub / OpenRouter dependencies. `enable` is needed
because pip/entry-point plugins are opt-in.

**Verify:**
```sh
hermes plugins list        # inbox_organizer → enabled
```
If it doesn't appear: `HERMES_PLUGINS_DEBUG=1 hermes plugins list`.

---

### Phase 3 — Write config + secrets

**Goal:** the four config files exist in `INBOX_CONFIG_DIR` and the required env
vars are set. Apply rule 1 throughout.

1. Create the dirs and lock them down:
   ```sh
   mkdir -p "$INBOX_CONFIG_DIR" "$INBOX_DATA_DIR"
   chmod 700 "$INBOX_CONFIG_DIR"
   ```
2. Write the OAuth client file — `$INBOX_CONFIG_DIR/inbox-oauth-client.json`:
   ```json
   {
     "client_id": "<client_id>",
     "client_secret": "<client_secret>",
     "redirect_uri": "https://inbox-organizer.northbound.run/",
     "owner_matrix_ids": ["@you:your-homeserver"]
   }
   ```
   `owner_matrix_ids` here is the **owner allowlist** — the Hermes user ID(s)
   permitted to connect/disconnect mailboxes. Despite the field name it is **not
   Matrix-only**: put whatever sender id your gateway reports for the owner's
   channel (Matrix `@you:server`, or another backend's id). Putting it in this
   file (rather than an env var) means it survives a container rebuild. (A Google
   `client_secret.json` with a `web`/`installed` node is also accepted in place of
   the flat shape.)

   **Finding the owner ID:** it's the gateway's `source.user_id` for the owner. On
   Matrix that's their `@user:homeserver`. If you're unsure on another backend,
   set it provisionally, attempt Phase 6, and if the connect is refused, check the
   Hermes gateway logs for the rejected sender id and use that exact value.
3. Write the Pub/Sub config — `$INBOX_CONFIG_DIR/inbox-pubsub.json`:
   ```json
   {
     "project": "<project-id>",
     "topic": "projects/<project-id>/topics/<topic-name>",
     "subscription": "<subscription-name>"
   }
   ```
4. Write the service-account key — `$INBOX_CONFIG_DIR/inbox-pubsub-sa.json` —
   verbatim from the JSON the owner downloaded.
5. Generate the AES encryption key (**once, then never change it** — see rule 3):
   ```sh
   openssl rand -hex 32 > "$INBOX_CONFIG_DIR/inbox-encryption-key"
   ```
6. Lock down every secret:
   ```sh
   chmod 600 "$INBOX_CONFIG_DIR"/inbox-*.json "$INBOX_CONFIG_DIR/inbox-encryption-key"
   ```
7. Set environment variables in the Hermes environment (method per Phase 0):
   - **Classifier LLM** — required for LLM classification. Default: set
     **`OPENROUTER_API_KEY`**. For any other OpenAI-compatible endpoint set
     **`INBOX_CLASSIFIER_API_KEY`** + **`INBOX_CLASSIFIER_BASE_URL`** instead
     (and optionally **`INBOX_CLASSIFIER_MODEL`**).
   - **Owner allowlist** — required so account-connect works. You already set it
     via `owner_matrix_ids` in the OAuth JSON (step 2); alternatively set
     **`INBOX_OWNER_MATRIX_IDS`** (comma-separated), which takes precedence. Both
     hold gateway sender ids (any backend, not just Matrix). The gate is
     **fail-closed**: with neither set, *every* connect attempt is refused,
     including the owner's.
   - `HERMES_API_URL` — *optional*; the local Hermes OpenAI-compatible endpoint.
     Needed only for drafted replies; triage + labeling run without it.
   - `API_SERVER_KEY` — *optional*; bearer token if the wake endpoint requires one.
   - `INBOX_CONFIG_DIR` / `INBOX_DATA_DIR` — only if you chose non-default paths.

**Verify (without printing secrets):**
```sh
ls -l "$INBOX_CONFIG_DIR"          # 4 files, all mode 600
python -c "import json,os; d=os.environ['INBOX_CONFIG_DIR']; \
  [json.load(open(os.path.join(d,f))) for f in ('inbox-oauth-client.json','inbox-pubsub.json','inbox-pubsub-sa.json')]; \
  print('json files parse OK')"
```

---

### Phase 4 — Start the daemon at boot (recommended)

**Goal:** the triage daemon starts on gateway boot, not just on the first agent
turn after a restart.

Hermes loads entry-point plugins lazily, so after a restart the daemon stays
dormant until someone next chats. A `gateway:startup` hook fixes that. The hook
lives in the repo at `deploy/hooks/inbox-organizer-boot/` and is **not** shipped
in the pip wheel, so create the two files yourself in the Hermes hooks dir
(usually `~/.hermes/hooks/inbox-organizer-boot/`):

`HOOK.yaml`:
```yaml
name: inbox-organizer-boot
description: Load entry-point plugins at gateway startup so the triage daemon starts at boot.
events:
  - gateway:startup
```

`handler.py`:
```python
async def handle(event_type, context):  # Hermes hook signature
    tag = "[inbox-organizer-boot]"
    try:
        from hermes_cli.plugins import discover_plugins
        print(f"{tag} {event_type}: loading entry-point plugins at boot", flush=True)
        discover_plugins()  # idempotent; runs each enabled plugin's register()
        print(f"{tag} discover_plugins() complete", flush=True)
    except Exception as exc:
        import traceback
        print(f"{tag} FAILED to load plugins at startup: {exc!r}", flush=True)
        traceback.print_exc()
```

(If you have repo access, copying `deploy/hooks/inbox-organizer-boot/` verbatim is
equivalent and includes a daemon-thread health log.)

**Verify:** both files exist under the hooks dir.

---

### Phase 5 — Restart + verify load

**Goal:** Hermes restarts with the new env + plugin and the daemon arms.

1. Ask the owner before restarting (rule 2), then restart Hermes the way this
   deployment does (`docker compose up -d hermes`, `systemctl restart hermes`, …).
2. Verify:
   ```sh
   hermes plugins list        # inbox_organizer → enabled
   ```
3. In a chat session, confirm `/plugins` lists it as loaded, then call the
   `inbox_list_accounts` tool — it should return an empty list (no accounts yet),
   which proves the tools are wired and config loaded without error.

**If `inbox_list_accounts` errors about config**, re-check Phase 3 (file paths,
JSON validity, env vars) before connecting an account.

---

### Phase 6 — Connect the owner's Gmail

**Goal:** the owner's mailbox is connected and triaged.

1. Call **`inbox_connect_account`**. It returns a Google sign-in `auth_url`.
2. Give the owner the link. Tell them: approve access; if Google shows a
   *"hasn't verified this app"* screen, choose **Advanced → Continue** (expected
   for their own client); then copy the **code shown on the callback page**.
3. When they paste the code back, call **`inbox_complete_connection`** with
   `{ "code": "<pasted code>" }`. A success looks like
   `{"ok": true, "email": "...", "live": true}`.
   - `live: true` → the account was hot-added to the running daemon.
   - `live: false` → the token is saved; it will be picked up on the next restart.
   - These tools are **owner-gated**; if you get *"restricted to this assistant's
     owner,"* the caller's gateway user ID isn't in the allowlist — fix Phase 3 step 7.
4. Repeat for any additional mailboxes.

**Verify:**
- `inbox_list_accounts` now lists the connected address.
- Ask the owner to send themselves a test email; it should get a numbered label
  within seconds (Pub/Sub push) or a few minutes (the polling reconciler).

---

### Phase 7 — Hand back to the owner

Tell the owner, in plain language:

- What's running: each new email is classified and labeled `1: To Respond` …
  `8: Marketing`; only *To Respond* and *FYI* stay in the inbox, the rest archive.
  For *To Respond*, you'll draft a reply in their voice (**drafts only — never
  sent**).
- How to add/remove mailboxes later: just ask you to *"connect another Gmail"* or
  *"disconnect <email>"*.
- The kill switch: set `INBOX_LABELS_ENABLED=0` to keep classification + drafting
  but stop all label/archive/move mutations.
- Proactive pushes (2FA codes, shipping updates — if those modules are enabled) go
  to your Hermes **home channel** on whatever platform you use. Run `/sethome` in
  the room you want them delivered to, or set `INBOX_NOTIFY_TARGET` to override.
- Where state lives: `INBOX_DATA_DIR` (SQLite `state.db` + encrypted tokens). Back
  up the **encryption key** somewhere safe — losing it means reconnecting every
  account.
- If this is a Docker deployment and you did a runtime `pip install`, remind them
  to bake the package into the image for durability ([`docs/setup.md`](docs/setup.md)).

---

### Troubleshooting

- **Plugin not in `hermes plugins list`** — installed into the wrong Python env
  (Phase 0); reinstall with the `hermes` CLI's own pip. Then
  `HERMES_PLUGINS_DEBUG=1 hermes plugins list`.
- **Loads but no triage after restart** — the boot hook (Phase 4) is missing, or
  the daemon didn't arm. Check Hermes stdout for `[inbox-organizer-boot]` lines.
- **`OAuth client not configured`** — `inbox-oauth-client.json` is missing,
  unreadable, or lacks `client_id`/`client_secret`/`redirect_uri`.
- **`no refresh_token in token response`** — the consent screen isn't granting
  offline access; ensure the app is Published and the owner did a fresh consent.
- **Accounts disconnect every ~7 days** — the consent screen is still in
  "Testing." Publish it to Production and reconnect ([`docs/oauth-modes.md`](docs/oauth-modes.md)).
- **`restricted to this assistant's owner`** — the owner allowlist is empty or
  doesn't include the caller's gateway user ID (Phase 3 step 7).
- **No labels appear** — confirm `INBOX_LABELS_ENABLED` isn't `0`, and that the
  Pub/Sub subscriber key has `roles/pubsub.subscriber` on the subscription.

For deeper detail see [`docs/setup.md`](docs/setup.md), [`docs/sync-modes.md`](docs/sync-modes.md),
and [`docs/security.md`](docs/security.md).
