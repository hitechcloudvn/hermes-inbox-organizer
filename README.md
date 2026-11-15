<div align="center">

# hermes-inbox-organizer

**Phân loại Gmail tự động dạng plugin Hermes chạy trong tiến trình — sắp xếp, gắn nhãn, lưu trữ thư và soạn bản nháp trả lời bằng giọng của bạn, tự lưu trữ, không qua SaaS bên thứ ba**

**Autonomous Gmail triage as an in-process Hermes plugin — it sorts, labels, and archives your mail and drafts replies in your voice, self-hosted, with no third-party SaaS in the path of your inbox**

[![CI](https://github.com/hitechcloudvn/hermes-inbox-organizer/actions/workflows/ci.yml/badge.svg)](https://github.com/hitechcloudvn/hermes-inbox-organizer/actions/workflows/ci.yml)
[![Release](https://github.com/hitechcloudvn/hermes-inbox-organizer/actions/workflows/release.yml/badge.svg)](https://github.com/hitechcloudvn/hermes-inbox-organizer/actions/workflows/release.yml)
[![PyPI](https://img.shields.io/pypi/v/hermes-inbox-organizer)](https://pypi.org/project/hermes-inbox-organizer/)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Made in Vietnam](https://img.shields.io/badge/Made%20in-Vietnam-DA251D?style=flat-square)](https://hitechcloud.vn)

**Tiếng Việt** | **English**

[GitHub](https://github.com/hitechcloudvn/hermes-inbox-organizer) · [GitLab](https://gitlab.com/hitechcloudvn/hermes-inbox-organizer)

</div>

---

## 🇻🇳 Tiếng Việt

### Tổng quan

Một agent Hermes (`NousResearch/hermes-agent`) nạp plugin này trong tiến trình và chạy
một daemon phân loại Gmail liên tục: mỗi thư mới được phân loại bằng pipeline kết hợp
**pre-classifier + LLM OpenRouter** và nhận một nhãn Gmail đánh số kiểu Fyxer có màu
(`1: To Respond` … `8: Marketing`). Chỉ `1: To Respond` và `2: FYI` ở lại hộp thư;
các nhãn còn lại skip-inbox và lưu trữ. Với `1: To Respond`, plugin nhờ **Hermes soạn
bản nháp trả lời** bằng giọng của bạn (chỉ bản nháp, không bao giờ tự gửi). Khi bạn
trả lời, chủ đề chuyển sang `7: Actioned`; khi bạn gửi và đang chờ, chuyển sang
`6: Awaiting Reply`.

Không có dịch vụ riêng và không có webhook công khai — chỉ một plugin nạp cùng agent.
Plugin cũng có thể thêm một **tab Inbox Organizer** vào dashboard web của Hermes để
kết nối/gỡ tài khoản ([docs/dashboard.md](docs/dashboard.md)).

### Kiến trúc

- **Nạp**: `register(ctx)` đăng ký các agent tool + hook nudge `pre_llm_call` và khởi
  động daemon. Hook `gateway:startup` khởi động daemon ngay khi boot (không phải chờ
  lượt chat đầu tiên).
- **Đồng bộ**: Gmail `watch()` → Pub/Sub **streaming pull** (kết nối đi ra — không
  webhook/tunnel) → drain lịch sử từ con trỏ đã lưu → phân loại + gắn nhãn → đánh
  thức Hermes soạn thảo. Một **polling reconciler** drain lại theo chu kỳ đề phòng
  push bị bỏ lỡ.
- **Trạng thái**: SQLite (`state.db`) trong volume dữ liệu của Hermes — con trỏ lịch
  sử, chống trùng lặp bản nháp, thư đã phân loại, trạng thái chủ đề, kết quả bản nháp
  + bài học đã học (schema v3, tự migrate khi triển khai). Token OAuth được mã hoá
  AES-256-GCM khi lưu trữ.
- **Chi phí**: pre-classifier cục bộ giá rẻ xử lý phần lớn thư; LLM dự phòng (một
  model OpenRouter nhỏ) chỉ chạy khi cần, nên chi phí mỗi thư chỉ là vài phần xu.

**Bố cục thư mục**:

- **`hermes_inbox_organizer/`** — package plugin (module), gồm `dashboard/` web-UI
  kèm theo; cùng `tests/`, `deploy/` (hook boot `gateway:startup`) và `pyproject.toml`
  ở gốc repo.
- **`oauth-callback/`** — trang tĩnh OAuth callback (Cloudflare Pages) dùng cho
  onboarding qua chat.
- **`docs/`** — ghi chú về cài đặt, Google Cloud, OAuth, đồng bộ, bảo mật và dashboard.

### Tính năng

- **Gmail đa tài khoản** — kết nối/ngắt bằng cách **chat với Hermes**, hoặc từ **tab
  web dashboard** — [docs/dashboard.md](docs/dashboard.md)
- **Phân loại lai**: luật header/sender deterministic + LLM dự phòng
- **Bản nháp trả lời do Hermes soạn** cho `1: To Respond`
- **Xử lý thư đã gửi** (`Actioned` / `Awaiting Reply`)
- **Vòng học tăng cường bản nháp** — học từ chênh lệch draft→sent: chắt lọc ghi chú
  giọng văn theo người gửi + bài học toàn cục nên/không nên + ví dụ trả lời mẫu vào
  một lớp riêng có thể kiểm toán, cung cấp cho brief soạn thảo sau này
  (in-context learning-from-edits; không fine-tune model)
- **Công cụ rollup thư chưa đọc** theo yêu cầu ("điều gì cần tôi across các hộp thư?")
- **Agent tools**: `inbox_create_draft`, `inbox_list_accounts`, `inbox_list_emails`,
  `inbox_get_email`, `inbox_get_thread`, `inbox_unread_rollup`,
  `inbox_connect_account` / `inbox_complete_connection` / `inbox_disconnect_account`,
  `inbox_draft_feedback_status`, `inbox_forget_lesson`, `inbox_clear_learned_notes`

### Cài đặt

Bạn cần một **triển khai Hermes bạn tự kiểm soát** và một **Google Cloud project**
(thiết lập một lần trong trình duyệt). Xem [Cấu hình](#cấu-hình) cho phần config +
secrets, và [Sử dụng](#sử-dụng) để kết nối hộp thư.

```sh
# 1) Cài đặt (pip — plugin này cần các phụ thuộc Gmail/Pub/Sub)
pip install "hermes-inbox-organizer[live]"
hermes plugins enable inbox_organizer

# 2) Thiết lập Google Cloud một lần (OAuth client + Pub/Sub)
#    → docs/google-bootstrap.md  (~10 phút, trong trình duyệt)

# 3) Cấu hình — wizard ghi các file config + khoá
#    (tự sinh khoá mã hoá; không bao giờ in ra secrets)
hermes-inbox-organizer setup
hermes-inbox-organizer status      # những gì đã cấu hình + khả năng

# 4) Khởi động lại Hermes, rồi trong chat: "connect a Gmail account"
```

Đã chạy sẵn một agent Hermes? Đưa cho nó
[`HERMES_SELF_INSTALL.md`](HERMES_SELF_INSTALL.md) và nó sẽ tự làm tất cả những việc
trên. Chi tiết đầy đủ và cách cấu hình thủ công nằm dưới đây.

Đây là **plugin Hermes kiểu pip / entry-point** — nó ship entry point
`hermes_agent.plugins` và agent Hermes nạp nó trong tiến trình. Nó **không** được cài
bằng `hermes plugins install <repo>`: lệnh đó git-clone một plugin kiểu *thư mục* và
không cài dependency Python, mà plugin này cần (Gmail, Pub/Sub, OpenRouter). Hãy dùng
`pip`. Mô hình discovery/enable xem
[tài liệu plugin của Hermes](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins).

#### 1. Google Cloud

Plugin theo dõi Gmail qua Pub/Sub bằng **streaming pull đi ra** (không webhook, không
endpoint công khai), nên cần một Google Cloud project có Gmail + Pub/Sub APIs, một
OAuth client, và một topic + pull subscription.

1. **Project** — [console.cloud.google.com](https://console.cloud.google.com/) →
   project selector → **New Project** (ví dụ `hermes-inbox`).
2. **Bật APIs** — APIs & Services → Library → bật **Gmail API**
   (`gmail.googleapis.com`) và **Cloud Pub/Sub API** (`pubsub.googleapis.com`).
3. **OAuth consent screen** — APIs & Services → OAuth consent screen →
   **External**. Thêm scopes `gmail.modify`, `gmail.send`, `userinfo.email`,
   `userinfo.profile`; thêm Gmail của bạn làm **Test User**; rồi **Publish App**
   (Production audience) để tránh refresh-token hết hạn sau 7 ngày
   ([docs/oauth-modes.md](docs/oauth-modes.md)).
4. **OAuth client** — Credentials → Create Credentials → OAuth client ID →
   **Web application**. Với **Authorized redirect URI**, dùng một trang tĩnh chỉ
   hiện mã để bạn dán lại — tự host `oauth-callback/` hoặc dùng lại
   `https://inbox-organizer.northbound.run/` (trang này không giữ secrets; OAuth
   client vẫn phải là **của bạn**). Lưu lại client id/secret cho bước 3.
5. **Pub/Sub** — Pub/Sub → Topics → **Create Topic** (ví dụ `gmail-notifications`);
   trên topic đó, **Create Subscription** với loại giao hàng **Pull** (ví dụ
   `gmail-inbox-organizer-pull`).
6. **Cho phép Gmail publish** — trên topic → Permissions → **Add Principal**
   `gmail-api-push@system.gserviceaccount.com`, role **Pub/Sub Publisher**.
7. **Subscriber key** — IAM & Admin → Service Accounts → tạo một tài khoản (ví dụ
   `hermes-inbox-pubsub`), cấp **`roles/pubsub.subscriber`** *trên subscription*
   (không cấp toàn project), và tải về một JSON key.

(Hình ảnh và chi tiết: [docs/google-bootstrap.md](docs/google-bootstrap.md).)

#### 2. Cài plugin

Cài vào **cùng môi trường Python** với CLI `hermes` của bạn:

```sh
pip install "hermes-inbox-organizer[live]"
# hoặc từ nguồn: pip install "hermes-inbox-organizer[live] @ git+https://github.com/hitechcloudvn/hermes-inbox-organizer"
```

`[live]` kéo theo các phụ thuộc Gmail/Pub/Sub/OpenRouter. Hermes tự tìm plugin qua
entry point; **bật** plugin lên (plugin pip là opt-in):

```sh
hermes plugins enable inbox_organizer    # hoặc thêm `inbox_organizer` vào plugins.enabled trong ~/.hermes/config.yaml
```

#### Cập nhật

```sh
pip install --upgrade "hermes-inbox-organizer[live]"
```

Rồi khởi động lại Hermes (hoặc `/reset` trong phiên CLI) để các tool + schema mới
được nạp lại. Schema SQLite tự migrate khi nạp, nên con trỏ, token và trạng thái soạn
thảo đã học được giữ nguyên; chạy `hermes-inbox-organizer status` để xác nhận.

### Cấu hình

Plugin đọc secrets dạng **file** từ một thư mục config (`INBOX_CONFIG_DIR`, mặc định
`/opt/data/config`) và ghi SQLite DB + token đã mã hoá vào thư mục dữ liệu
(`INBOX_DATA_DIR`, mặc định `/opt/data/inbox-organizer`). Đặt cả hai biến môi trường
này vào đường dẫn thực nếu mặc định không phù hợp với máy của bạn.

**Dễ nhất — wizard cài đặt.** Wizard hỏi các giá trị từ bước 1, sinh khoá mã hoá và
ghi mọi thứ vào `INBOX_CONFIG_DIR` (mode `0600`):

```sh
hermes-inbox-organizer setup     # hoặc: python -m hermes_inbox_organizer setup
hermes-inbox-organizer status    # kiểm tra những gì đã cấu hình + khả năng
```

Wizard ghi các giá trị chỉ dùng qua env (API key + endpoint của classifier, tuỳ chọn
`HERMES_API_URL`) vào `INBOX_CONFIG_DIR/inbox.env` để bạn đưa vào môi trường Hermes
(ví dụ `env_file:` của compose).

**Hoặc cấu hình thủ công** — cài các file này vào `INBOX_CONFIG_DIR`:

| File | Nội dung |
|---|---|
| `inbox-oauth-client.json` | `{ "client_id", "client_secret", "redirect_uri", "owner_matrix_ids": ["@you:your-homeserver"] }` (từ bước 1.4) |
| `inbox-pubsub.json` | `{ "project", "topic": "projects/<id>/topics/<topic>", "subscription" }` (từ bước 1.5) |
| `inbox-pubsub-sa.json` | service-account key `pubsub.subscriber` (bước 1.7) |
| `inbox-encryption-key` | 32 hex bytes — `openssl rand -hex 32` (AES-GCM cho token khi lưu trữ) |

`owner_matrix_ids` là **danh sách cho phép chủ sở hữu** cho các tool kết nối/ngắt —
là gateway sender id, **không** chỉ dành riêng cho Matrix dù tên là vậy (dùng bất kỳ
`source.user_id` nào kênh của bạn báo về). Bạn cũng có thể đặt qua
`INBOX_OWNER_MATRIX_IDS` (phân tách bằng dấu phẩy), biến này được ưu tiên. Cổng này
fail-closed: khi không đặt gì, kể cả chủ sở hữu cũng không thể kết nối hộp thư. Các
module chủ động (2FA, shipping) gửi về kênh `/sethome` home channel trên nền tảng
bạn đang dùng.

Và trong môi trường Hermes:

- **Classifier LLM** — classifier nói giao thức OpenAI API, nên chạy được với
  **bất kỳ endpoint tương thích nào**. Mặc định dùng OpenRouter qua
  `OPENROUTER_API_KEY` ([openrouter.ai/keys](https://openrouter.ai/keys); hầu hết
  thiết lập Hermes đã có sẵn). Với endpoint khác — server vLLM/Ollama/LM Studio cục
  bộ, hoặc gateway khác — đặt `INBOX_CLASSIFIER_API_KEY` và
  `INBOX_CLASSIFIER_BASE_URL`, và tuỳ chọn `INBOX_CLASSIFIER_MODEL`
  (mặc định `google/gemini-2.5-flash-lite`). `INBOX_CLASSIFIER_API_KEY` được ưu tiên
  hơn `OPENROUTER_API_KEY`.
- `HERMES_API_URL` *(tuỳ chọn)* — endpoint OpenAI-compatible của Hermes, chỉ cần cho
  bản nháp trả lời; phân loại + gắn nhãn chạy được không cần nó.

Khởi động lại Hermes. Để daemon khởi động ngay khi boot (thay vì chờ lượt agent đầu
tiên), copy hook `gateway:startup` từ
[`deploy/hooks/inbox-organizer-boot/`](deploy/hooks/inbox-organizer-boot) vào
`~/.hermes/hooks/inbox-organizer-boot/`.

### Sử dụng

#### Kết nối tài khoản Gmail

Hai cách — cùng một luồng OAuth copy-paste:

- **Chat với Hermes** — *"Connect a Gmail account."* Agent trả về link consent của
  Google; bạn duyệt nó, dán mã từ trang callback trở lại, và tài khoản được thêm
  nóng (có cổng theo chủ sở hữu). Lặp lại cho các hộp thư khác.
- **Tab dashboard** — mở dashboard web của Hermes và dùng tab **Inbox Organizer**
  để kết nối/gỡ tài khoản bằng nút bấm thay cho tool. Nếu tab chưa có, chạy
  `hermes inbox-organizer install-dashboard` một lần và khởi động lại
  `hermes dashboard`. Xem [docs/dashboard.md](docs/dashboard.md).

#### Kiểm tra

```sh
hermes-inbox-organizer status                # config + khả năng trong một cái nhìn
hermes plugins list                          # inbox_organizer → enabled
HERMES_PLUGINS_DEBUG=1 hermes plugins list   # discovery chi tiết nếu plugin không hiện
```

Trong phiên đang chạy, `/plugins` liệt kê plugin đã được nạp. Nhờ agent chạy
`inbox_list_accounts`, rồi gửi cho chính bạn một thư thử — nó sẽ nhận nhãn đánh số
trong vài giây (push) hoặc vài phút (polling reconciler).

> **Triển khai vào image container đã nướng sẵn** (daemon chạy ngay khi boot, secrets
> trong mount chỉ-đọc)? Đó là cách stack của repo này chạy — xem
> [docs/setup.md](docs/setup.md) để biết Dockerfile + entrypoint.

### Kiểm thử

```sh
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest -q     # test chạy hoàn toàn offline (network/Google/agent được seam)
ruff check .                      # lint
mypy                              # type-check
```

Plugin này tuân theo [Hermes Plugin Standard](HERMES_PLUGIN_STANDARD.md) chung
(các quy ước packaging, tooling, CI, release và bảo mật dùng chung cho các plugin
Hermes của chúng tôi). Xem [CONTRIBUTING.md](CONTRIBUTING.md) trước khi mở PR.

### Giấy phép

MIT — xem [LICENSE](LICENSE).

---

## 🇬🇧 English

### Overview

A Hermes agent (`NousResearch/hermes-agent`) loads this plugin in-process and it
runs a continual Gmail triage daemon: each new message is classified by a hybrid
**pre-classifier + OpenRouter LLM** pipeline and gets a colored Fyxer-style
numbered Gmail label (`1: To Respond` … `8: Marketing`). Only `1: To Respond`
and `2: FYI` stay in the inbox; the rest skip-inbox and archive. For
`1: To Respond`, the plugin asks **Hermes to compose a reply draft** in your
voice (drafts only, never sent). When you reply, the thread moves to
`7: Actioned`; when you send and are waiting, `6: Awaiting Reply`.

No separate service and no public webhook — it's one plugin that loads with the
agent. It can also add an optional **Inbox Organizer tab** to Hermes's own web
dashboard for connecting/removing accounts ([docs/dashboard.md](docs/dashboard.md)).

### Architecture

- **Load**: `register(ctx)` registers the agent tools + a `pre_llm_call` nudge
  hook and starts the daemon. A `gateway:startup` hook starts the daemon at boot
  (so it doesn't wait for the first agent turn).
- **Sync**: Gmail `watch()` → Pub/Sub **streaming pull** (outbound connection —
  no webhook/tunnel) → drain history from a stored cursor → classify + label →
  wake Hermes to draft. A **polling reconciler** re-drains on a timer in case a
  push is dropped.
- **State**: SQLite (`state.db`) in the Hermes data volume — history cursors,
  draft idempotency, classified messages, thread state, draft outcomes + learned
  lessons (schema v3, migrates in place on deploy). OAuth tokens are
  AES-256-GCM encrypted at rest.
- **Cost**: the cheap local pre-classifier handles most mail; the LLM fallback
  (a small OpenRouter model) runs only when needed, so per-message cost is a
  fraction of a cent.

**Layout**:

- **`hermes_inbox_organizer/`** — the plugin package (the module), including its
  bundled `dashboard/` web-UI plugin; with `tests/`, `deploy/` (the
  `gateway:startup` boot hook), and `pyproject.toml` at the repo root.
- **`oauth-callback/`** — the static OAuth callback page (Cloudflare Pages) used
  by chat onboarding.
- **`docs/`** — setup, Google Cloud, OAuth, sync, security, and dashboard notes.

### Features

- Multi-account Gmail (connect/disconnect by **chatting with Hermes**, or from an
  optional **web dashboard tab** — [docs/dashboard.md](docs/dashboard.md))
- Hybrid triage: deterministic header/sender rules + LLM fallback
- Hermes-drafted replies for `1: To Respond`
- Sent-handling (`Actioned` / `Awaiting Reply`)
- **Draft reinforcement loop** — learns from draft→sent deltas: distils
  per-sender voice notes + global do/don't lessons + gold-example replies into
  a separate auditable layer that feeds future drafting briefs (in-context
  learning-from-edits; no model fine-tuning)
- On-demand unread **rollup** tool ("what needs me across my inboxes?")
- Agent tools: `inbox_create_draft`, `inbox_list_accounts`, `inbox_list_emails`,
  `inbox_get_email`, `inbox_get_thread`, `inbox_unread_rollup`,
  `inbox_connect_account` / `inbox_complete_connection` / `inbox_disconnect_account`,
  `inbox_draft_feedback_status`, `inbox_forget_lesson`, `inbox_clear_learned_notes`

### Install

You need a **Hermes deployment you control** and a **Google Cloud project**
(a one-time setup in your browser). See [Configuration](#configuration) for the
config + secrets step, and [Usage](#usage) to connect mailboxes.

```sh
# 1) Install (pip — this plugin needs the Gmail/Pub/Sub deps)
pip install "hermes-inbox-organizer[live]"
hermes plugins enable inbox_organizer

# 2) One-time Google Cloud setup (OAuth client + Pub/Sub)
#    → docs/google-bootstrap.md  (~10 min, in your browser)

# 3) Configure — the wizard writes the config files + keys
#    (auto-generates the encryption key; never prints secrets)
hermes-inbox-organizer setup
hermes-inbox-organizer status      # what's configured + capabilities

# 4) Restart Hermes, then in chat: "connect a Gmail account"
```

Already run a Hermes agent? Hand it
[`HERMES_SELF_INSTALL.md`](HERMES_SELF_INSTALL.md) and it'll do all of this for
you. The full detail and the by-hand path are below.

This is a **pip / entry-point Hermes plugin** — it ships the
`hermes_agent.plugins` entry point and your Hermes agent loads it in-process. It
is **not** installed with `hermes plugins install <repo>`: that command
git-clones a *directory* plugin and never installs Python dependencies, which
this plugin needs (Gmail, Pub/Sub, OpenRouter). Use `pip`. For the
discovery/enable model see the
[Hermes plugin docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins).

#### 1. Google Cloud

The plugin watches Gmail over Pub/Sub via an **outbound streaming pull** (no
webhook, no public endpoint), so it needs a Google Cloud project with the Gmail +
Pub/Sub APIs, an OAuth client, and a topic + pull subscription.

1. **Project** — [console.cloud.google.com](https://console.cloud.google.com/) →
   project selector → **New Project** (e.g. `hermes-inbox`).
2. **Enable APIs** — APIs & Services → Library → enable **Gmail API**
   (`gmail.googleapis.com`) and **Cloud Pub/Sub API** (`pubsub.googleapis.com`).
3. **OAuth consent screen** — APIs & Services → OAuth consent screen →
   **External**. Add scopes `gmail.modify`, `gmail.send`, `userinfo.email`,
   `userinfo.profile`; add your Gmail as a **Test User**; then **Publish App**
   (Production audience) to avoid the 7-day refresh-token expiry
   ([docs/oauth-modes.md](docs/oauth-modes.md)).
4. **OAuth client** — Credentials → Create Credentials → OAuth client ID →
   **Web application**. For the **Authorized redirect URI** use a static page
   that just displays the code for you to paste back — host `oauth-callback/`
   yourself or reuse `https://inbox-organizer.northbound.run/` (it holds no
   secrets; the OAuth client itself must still be **your own**). Save the
   client id/secret for step 3.
5. **Pub/Sub** — Pub/Sub → Topics → **Create Topic** (e.g. `gmail-notifications`);
   on that topic, **Create Subscription** with delivery type **Pull** (e.g.
   `gmail-inbox-organizer-pull`).
6. **Let Gmail publish** — on the topic → Permissions → **Add Principal**
   `gmail-api-push@system.gserviceaccount.com`, role **Pub/Sub Publisher**.
7. **Subscriber key** — IAM & Admin → Service Accounts → create one (e.g.
   `hermes-inbox-pubsub`), grant **`roles/pubsub.subscriber`** *on the
   subscription* (not project-wide), and download a JSON key.

(Screens and detail: [docs/google-bootstrap.md](docs/google-bootstrap.md).)

#### 2. Install the plugin

Install into the **same Python environment** as your `hermes` CLI:

```sh
pip install "hermes-inbox-organizer[live]"
# or from source: pip install "hermes-inbox-organizer[live] @ git+https://github.com/hitechcloudvn/hermes-inbox-organizer"
```

`[live]` pulls the Gmail/Pub/Sub/OpenRouter deps. Hermes auto-discovers the
plugin via its entry point; **enable** it (pip plugins are opt-in):

```sh
hermes plugins enable inbox_organizer    # or add `inbox_organizer` to plugins.enabled in ~/.hermes/config.yaml
```

#### Updating

```sh
pip install --upgrade "hermes-inbox-organizer[live]"
```

Then restart Hermes (or `/reset` in a CLI session) so the updated tools + schemas
reload. The SQLite schema migrates in place on load, so cursors, tokens, and
learned drafting state carry over; run `hermes-inbox-organizer status` to confirm.

### Configuration

The plugin reads its secrets as **files** from a config dir
(`INBOX_CONFIG_DIR`, default `/opt/data/config`) and writes its SQLite DB +
encrypted tokens to a data dir (`INBOX_DATA_DIR`, default
`/opt/data/inbox-organizer`). Point both env vars at real paths if those
defaults don't fit your host.

**Easiest — the setup wizard.** It prompts for the values from step 1, generates
the encryption key, and writes everything into `INBOX_CONFIG_DIR` (mode `0600`):

```sh
hermes-inbox-organizer setup     # or: python -m hermes_inbox_organizer setup
hermes-inbox-organizer status    # verify what's configured + capabilities
```

The wizard writes env-only values (the classifier API key + endpoint, optional
`HERMES_API_URL`) to `INBOX_CONFIG_DIR/inbox.env` for you to wire into the Hermes
environment (e.g. a compose `env_file:`).

**Or by hand** — install these files into `INBOX_CONFIG_DIR`:

| File | Contents |
|---|---|
| `inbox-oauth-client.json` | `{ "client_id", "client_secret", "redirect_uri", "owner_matrix_ids": ["@you:your-homeserver"] }` (from step 1.4) |
| `inbox-pubsub.json` | `{ "project", "topic": "projects/<id>/topics/<topic>", "subscription" }` (from step 1.5) |
| `inbox-pubsub-sa.json` | the `pubsub.subscriber` service-account key (step 1.7) |
| `inbox-encryption-key` | 32 hex bytes — `openssl rand -hex 32` (AES-GCM for tokens at rest) |

`owner_matrix_ids` is the **owner allowlist** for the connect/disconnect tools —
gateway sender ids, **not** Matrix-only despite the name (use whatever
`source.user_id` your channel reports). You can instead set it via
`INBOX_OWNER_MATRIX_IDS` (comma-separated), which takes precedence. The gate is
fail-closed: with neither set, even the owner can't connect a mailbox. Proactive
module pushes (2FA, shipping) go to your Hermes `/sethome` home channel on
whatever platform you use.

And in the Hermes environment:

- **Classifier LLM** — the classifier speaks the OpenAI API, so it works with
  **any compatible endpoint**. By default it uses OpenRouter via
  `OPENROUTER_API_KEY` ([openrouter.ai/keys](https://openrouter.ai/keys); most
  Hermes setups already have one). For any other endpoint — a local
  vLLM/Ollama/LM Studio server, or another gateway — set `INBOX_CLASSIFIER_API_KEY`
  and `INBOX_CLASSIFIER_BASE_URL` instead, and optionally `INBOX_CLASSIFIER_MODEL`
  (default `google/gemini-2.5-flash-lite`). `INBOX_CLASSIFIER_API_KEY` takes
  precedence over `OPENROUTER_API_KEY`.
- `HERMES_API_URL` *(optional)* — the Hermes OpenAI-compatible endpoint, needed
  only for the drafted replies; triage + labeling run without it.

Restart Hermes. To start the daemon at boot (instead of on the first agent
turn), copy the `gateway:startup` hook from
[`deploy/hooks/inbox-organizer-boot/`](deploy/hooks/inbox-organizer-boot) into
`~/.hermes/hooks/inbox-organizer-boot/`.

### Usage

#### Connect a Gmail account

Two ways — same copy-paste OAuth either way:

- **Chat with Hermes** — *"Connect a Gmail account."* The agent returns a Google
  consent link; approve it, paste the code from the callback page back, and the
  account is hot-added (owner-gated). Repeat for additional mailboxes.
- **Dashboard tab** — open Hermes's web dashboard and use the **Inbox Organizer**
  tab to connect/remove accounts with buttons instead of tools. If the tab isn't
  there yet, run `hermes inbox-organizer install-dashboard` once and restart
  `hermes dashboard`. See [docs/dashboard.md](docs/dashboard.md).

#### Verify

```sh
hermes-inbox-organizer status                # config + capabilities at a glance
hermes plugins list                          # inbox_organizer → enabled
HERMES_PLUGINS_DEBUG=1 hermes plugins list   # verbose discovery if it doesn't show up
```

In a running session, `/plugins` lists it as loaded. Ask the agent to run
`inbox_list_accounts`, then send yourself a test email — it should get a numbered
label within seconds (push) or a few minutes (the polling reconciler).

> **Deploying into a baked container image** (the daemon up at boot, secrets in a
> read-only mount)? That's how this repo's own stack runs — see
> [docs/setup.md](docs/setup.md) for the Dockerfile + entrypoint wiring.

### Testing

```sh
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest -q     # tests run fully offline (network/Google/agent are seamed)
ruff check .                      # lint
mypy                              # type-check
```

This plugin follows the shared [Hermes Plugin Standard](HERMES_PLUGIN_STANDARD.md)
(packaging, tooling, CI, release, and security conventions used across our Hermes
plugins). See [CONTRIBUTING.md](CONTRIBUTING.md) before opening a PR.

### License

MIT — see [LICENSE](LICENSE).
