# Changelog

**Tất cả thay đổi đáng chú ý của dự án đều được ghi tại đây.**

**All notable changes to this project are documented here.**

Định dạng theo [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), và dự án
này tuân theo [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and
this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

## [Unreleased]

## [0.2.1] - 2026-11-16

### Thêm

- **Tài liệu song ngữ VN/EN** — README, mọi file `*.md` còn lại (`docs/`,
  `CHANGELOG`, `CONTRIBUTING`, `SECURITY`, `HERMES_PLUGIN_STANDARD`,
  `HERMES_SELF_INSTALL`, PULL_REQUEST_TEMPLATE) đều có phần
  `## 🇻🇳 Tiếng Việt` và `## 🇬🇧 English` đầy đủ; docstring module + hàm/công
  khai cũng song ngữ (`VI:` / `EN:`).
- **`.gitlab-ci.yml`** — CI GitLab: kiểm thử mọi nhánh, tạo bản phát hành khi
  có tag `v*`.

### Đổi

- **Đổi tên tổ chức sang `hitechcloudvn`** — mọi URL GitHub/GitLab, metadata
  gói (`pyproject.toml`, `plugin.yaml`, `dashboard/manifest.json`), và các
  liên kết so sánh trong CHANGELOG đều trỏ về
  `github.com/hitechcloudvn/hermes-inbox-organizer`.
- **CI/CD phát hành qua GitHub Releases** — `.github/workflows/release.yml`
  mới: khi đẩy tag `v*`, chạy pytest, kiểm tra tag khớp version trong
  `pyproject.toml`, dựng gói bằng `python -m build` + `twine check --strict`,
  rồi đính kèm `dist/*` vào GitHub Release (sinh release notes tự động).
  **Không** đăng PyPI. CI kiểm thử trên ma trận Python 3.10–3.13
  (`Kiểm thử / Test (Python …)`) + job lint (ruff, mypy, LICENSE).
- Nâng version `0.2.0` → `0.2.1` (tag `v0.2.0` đã được dùng).

## [0.2.0] - 2026-06-24

### Thêm

- **Setup wizard** — console script `hermes-inbox-organizer` (cũng chạy được
  `python -m hermes_inbox_organizer`, và `hermes inbox-organizer …`) với:
  - `setup` — wizard tương tác ghi các file config OAuth/Pub/Sub/service-account
    vào `INBOX_CONFIG_DIR`, tự sinh khoá mã hoá AES (không bao giờ sinh lại khoá
    đã có), và không bao giờ in ra secrets; các file secret được ghi ở mode
    `0600`.
  - `status` — báo cáo những gì đã cấu hình và khả năng tương ứng.
- **`HERMES_SELF_INSTALL.md`** — runbook để agent tự thực thi, giúp một agent
  Hermes tự cài + cấu hình plugin và hướng dẫn chủ nhân qua các bước Google
  Cloud.
- **Bất kỳ endpoint classifier tương thích OpenAI nào** — LLM classifier không
  còn bị khoá cứng vào OpenRouter. Đặt `INBOX_CLASSIFIER_BASE_URL` +
  `INBOX_CLASSIFIER_API_KEY` (ví dụ server vLLM/Ollama/LM Studio cục bộ hoặc
  gateway khác); `OPENROUTER_API_KEY` vẫn được chấp nhận và vẫn là mặc định.

### Đổi

- README: **Quick Start** copy-paste xoay quanh wizard `setup`, mục
  **Updating**, badge trạng thái, và cách diễn đạt owner-id trung lập backend
  (danh sách cho phép chấp nhận mọi `source.user_id` của gateway, không chỉ
  Matrix).
- **Áp dụng [Hermes Plugin Standard](HERMES_PLUGIN_STANDARD.md) dùng chung**:
  bộ rule ruff đầy đủ (`E,F,I,W,UP,B,SIM,RUF`) + type-check mypy với `py.typed`
  được ship kèm; CI chạy lint + mypy và ma trận kiểm thử 3.11–3.14 trên
  `actions/checkout@v5` / `setup-python@v6`, cùng một job build kiểm tra
  manifest/assets được đóng trong wheel; author đặt thành
  `Nguyễn Thanh An <thanhan92f1@gmail.com> (HiTechCloud.VN)`. (Độ dài dòng 100
  đã khai báo; một lượt `ruff format` một lần để enforce E501 là việc theo dõi
  sau.)

## [0.1.0] - 2026-06-23

Bản phát hành công khai đầu tiên. Phân loại Gmail tự động, nạp trong tiến
trình vào agent [Hermes](https://hermes-agent.nousresearch.com) dưới dạng
plugin cài bằng `pip`.

### Thêm

- **Daemon phân loại** — Gmail `watch()` → Pub/Sub streaming pull (chỉ kết nối
  đi ra, không webhook) → drain lịch sử từ con trỏ đã lưu → phân loại → gắn
  nhãn. Một polling reconciler drain lại theo chu kỳ để push bị bỏ lỡ không
  bao giờ làm kẹt thư.
- **Classifier lai** — pre-classifier header/sender deterministic xử lý phần
  lớn thư; một model OpenRouter nhỏ làm dự phòng, giữ chi phí mỗi thư ở mức
  vài phần xu. Thư không được tin cậy được ngăn cách trước khi chạm tới model.
- **Tám nhãn kiểu Fyxer** (`1: To Respond` … `8: Marketing`). Chỉ
  `1: To Respond` và `2: FYI` ở lại hộp thư; các nhãn còn lại skip-inbox và
  lưu trữ. `INBOX_LABELS_ENABLED=0` chạy ở chế độ chỉ phân loại/soạn thảo,
  không tạo nhãn hay lưu trữ.
- **Bản nháp trả lời do Hermes soạn** cho `1: To Respond` — plugin đánh thức
  agent soạn trả lời bằng giọng của bạn và ghi bản nháp MIME (chỉ bản nháp,
  không bao giờ gửi).
- **Xử lý thư đã gửi** — chuyển chủ đề sang `7: Actioned` sau khi bạn trả lời,
  hoặc `6: Awaiting Reply` khi bạn gửi và đang chờ.
- **Vòng học tăng cường bản nháp** — học từ chênh lệch draft→sent, chắt lọc
  ghi chú giọng văn theo người gửi, bài học toàn cục nên/không nên, và các ví
  dụ trả lời mẫu vào một lớp riêng có thể kiểm toán, cung cấp cho brief soạn
  thảo sau này (in-context, không fine-tuning).
- **Công cụ rollup thư chưa đọc** — "điều gì cần tôi across các hộp thư?" trên
  tất cả tài khoản.
- **Đa tài khoản** — kết nối/ngắt bằng cách chat với Hermes hoặc từ tab tuỳ
  chọn **Inbox Organizer** trong web dashboard của Hermes. OAuth copy-paste.
- **Module cắm được** — hiển thị mã 2FA, theo dõi vận chuyển/17track, rollup,
  và phản hồi bản nháp được ship trong cây, đứng sau một module registry.
- **Agent tools** — `inbox_create_draft`, `inbox_list_accounts`,
  `inbox_list_emails`, `inbox_get_email`, `inbox_get_thread`,
  `inbox_unread_rollup`, `inbox_connect_account` / `inbox_complete_connection` /
  `inbox_disconnect_account`, `inbox_draft_feedback_status`,
  `inbox_forget_lesson`, `inbox_clear_learned_notes`.
- **Trạng thái** — SQLite (`state.db`, schema v3, tự migrate tại chỗ) cho con
  trỏ lịch sử, chống trùng lặp bản nháp, thư đã phân loại, trạng thái chủ đề,
  và kết quả/bài học bản nháp. Token OAuth được mã hoá AES-256-GCM khi lưu trữ.

---

## 🇬🇧 English

## [Unreleased]

## [0.2.1] - 2026-11-16

### Added

- **Bilingual VN/EN docs** — the README and every other `*.md` (`docs/`,
  `CHANGELOG`, `CONTRIBUTING`, `SECURITY`, `HERMES_PLUGIN_STANDARD`,
  `HERMES_SELF_INSTALL`, PULL_REQUEST_TEMPLATE) now carry full
  `## 🇻🇳 Tiếng Việt` and `## 🇬🇧 English` sections; module + public
  function/class docstrings are bilingual too (`VI:` / `EN:`).
- **`.gitlab-ci.yml`** — GitLab CI: tests on every branch, release creation on
  `v*` tags.

### Changed

- **Org renamed to `hitechcloudvn`** — every GitHub/GitLab URL, package
  metadata (`pyproject.toml`, `plugin.yaml`, `dashboard/manifest.json`), and
  the CHANGELOG compare links now point at
  `github.com/hitechcloudvn/hermes-inbox-organizer`.
- **CI/CD release via GitHub Releases** — the new
  `.github/workflows/release.yml`: on a `v*` tag push it runs pytest, asserts
  the tag matches the `pyproject.toml` version, builds with `python -m build`
  + `twine check --strict`, then attaches `dist/*` to a GitHub Release
  (auto-generated release notes). It does **not** publish to PyPI. CI tests a
  Python 3.10–3.13 matrix (`Kiểm thử / Test (Python …)`) plus a lint job
  (ruff, mypy, LICENSE).
- Version bumped `0.2.0` → `0.2.1` (tag `v0.2.0` was already taken).

## [0.2.0] - 2026-06-24

### Added

- **Setup wizard** — a `hermes-inbox-organizer` console script (also
  `python -m hermes_inbox_organizer`, and `hermes inbox-organizer …`) with:
  - `setup` — interactive wizard that writes the OAuth/Pub/Sub/service-account
    config files into `INBOX_CONFIG_DIR`, auto-generates the AES encryption key
    (never regenerates an existing one), and never echoes secrets; secret files
    are written mode `0600`.
  - `status` — reports what's configured and the resulting capabilities.
- **`HERMES_SELF_INSTALL.md`** — an agent-executable runbook so a Hermes agent
  can install + configure the plugin itself and walk the owner through Google
  Cloud.
- **Any OpenAI-compatible classifier endpoint** — the classifier LLM is no
  longer hardcoded to OpenRouter. Set `INBOX_CLASSIFIER_BASE_URL` +
  `INBOX_CLASSIFIER_API_KEY` (e.g. a local vLLM/Ollama/LM Studio server or
  another gateway); `OPENROUTER_API_KEY` is still accepted and remains the
  default.

### Changed

- README: a copy-paste **Quick Start** built around the `setup` wizard, an
  **Updating** section, status badges, and backend-neutral owner-id wording
  (the allowlist accepts any gateway `source.user_id`, not just Matrix).
- **Adopted the shared [Hermes Plugin Standard](HERMES_PLUGIN_STANDARD.md)**:
  full ruff ruleset (`E,F,I,W,UP,B,SIM,RUF`) + mypy type-checking with a
  shipped `py.typed`; CI now runs lint + mypy and a 3.11–3.14 test matrix on
  `actions/checkout@v5` / `setup-python@v6`, plus a build job that asserts the
  packaged manifest/assets ship in the wheel; author set to
  `Nguyễn Thanh An <thanhan92f1@gmail.com> (HiTechCloud.VN)`. (Line-length 100
  is declared; a one-time `ruff format` pass to enforce E501 is a tracked
  follow-up.)

## [0.1.0] - 2026-06-23

First public release. Autonomous Gmail triage that loads into a
[Hermes](https://hermes-agent.nousresearch.com) agent in-process as a
`pip`-installable plugin.

### Added

- **Triage daemon** — Gmail `watch()` → Pub/Sub streaming pull (outbound only,
  no webhook) → drain history from a stored cursor → classify → label. A
  polling reconciler re-drains on a timer so a dropped push never strands mail.
- **Hybrid classifier** — a deterministic header/sender pre-classifier handles
  most mail; a small OpenRouter model is the fallback, keeping per-message cost
  a fraction of a cent. Untrusted email is fenced before it ever reaches the
  model.
- **Eight Fyxer-style labels** (`1: To Respond` … `8: Marketing`). Only
  `1: To Respond` and `2: FYI` stay in the inbox; the rest skip-inbox and
  archive. `INBOX_LABELS_ENABLED=0` runs classify/draft-only with no label or
  archive mutations.
- **Hermes-drafted replies** for `1: To Respond` — the plugin wakes the agent
  to compose a reply in your voice and writes the MIME draft (drafts only,
  never sent).
- **Sent-handling** — moves a thread to `7: Actioned` after you reply, or
  `6: Awaiting Reply` when you send and are waiting.
- **Draft reinforcement loop** — learns from draft→sent edits, distilling
  per-sender voice notes, global do/don't lessons, and gold-example replies
  into a separate auditable layer that feeds future drafting briefs (in-context,
  no fine-tuning).
- **Unread rollup** tool — "what needs me across my inboxes?" across accounts.
- **Multi-account** — connect/disconnect by chatting with Hermes or from an
  optional **Inbox Organizer** tab in the Hermes web dashboard. Copy-paste
  OAuth.
- **Pluggable modules** — 2FA-code surfacing, shipping/17track tracking,
  rollup, and draft-feedback ship in-tree behind a module registry.
- **Agent tools** — `inbox_create_draft`, `inbox_list_accounts`,
  `inbox_list_emails`, `inbox_get_email`, `inbox_get_thread`,
  `inbox_unread_rollup`, `inbox_connect_account` / `inbox_complete_connection` /
  `inbox_disconnect_account`, `inbox_draft_feedback_status`,
  `inbox_forget_lesson`, `inbox_clear_learned_notes`.
- **State** — SQLite (`state.db`, schema v3, migrates in place) for history
  cursors, draft idempotency, classified messages, thread state, and draft
  outcomes/lessons. OAuth tokens are AES-256-GCM encrypted at rest.

[Unreleased]: https://github.com/hitechcloudvn/hermes-inbox-organizer/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/hitechcloudvn/hermes-inbox-organizer/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/hitechcloudvn/hermes-inbox-organizer/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/hitechcloudvn/hermes-inbox-organizer/releases/tag/v0.1.0
