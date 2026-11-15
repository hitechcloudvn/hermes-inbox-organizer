# Hermes Plugin Standard

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

Các quy ước dùng chung cho các **Hermes plugin** chạy trong tiến trình mà chúng tôi (HiTechCloud.VN) xây dựng và duy trì. Đây là tài liệu tham khảo chính thức; nó được commit nguyên văn vào từng repo plugin để chúng luôn đồng bộ.

Các plugin đang áp dụng:
- [`hermes-inbox-organizer`](https://github.com/hitechcloudvn/hermes-inbox-organizer)
- [`hermes-chat-recorder`](https://github.com/hitechcloudvn/hermes-chat-recorder)

Một plugin được coi là tuân thủ nếu nó theo các mục **MUST** dưới đây. Các mục **SHOULD** là các mặc định mạnh; chỉ đi lệch khi có ghi chú giải thích lý do.

---

### 1. Danh tính & metadata

- **MUST** được cấp phép MIT, với một tệp `LICENSE` ở gốc repo.
- **MUST** khai báo metadata license PEP 639 trong `pyproject.toml`:
  `license = "MIT"` + `license-files = ["LICENSE"]`, và
  `requires = ["setuptools>=77"]` trong `[build-system]` (Metadata-Version 2.4).
- **MUST** đặt author là `Nguyễn Thanh An <thanhan92f1@gmail.com> (HiTechCloud.VN)`.
- **MUST** sở hữu repo dưới tổ chức GitHub `hitechcloudvn`; dùng đúng cách viết đó trong mọi URL (`[project.urls]`, badge, tài liệu).
- **SHOULD** thiết lập `[project.urls]` Homepage, Repository, Issues, Documentation.
- **SHOULD** giữ `classifiers` Development Status trung thực
  (`4 - Beta` khi đã chạy trong production; `3 - Alpha` khi schema/API còn thay đổi).

### 2. Python & đóng gói

- **MUST** nhắm tới **Python 3.11+** (`requires-python = ">=3.11"`).
- **MUST** kiểm thử trên ma trận **3.11, 3.12, 3.13, 3.14**.
- **MUST** cài đặt được từ PyPI với tên `hermes-<name>` và expose entry point của Hermes (xem §3).
- **MUST** đóng gói manifest plugin + mọi tài nguyên runtime dưới dạng `package-data` (để một `pip install` không phải editable vẫn bao gồm chúng), và **assert trong CI** rằng chúng có mặt trong wheel đã build.
- Dependencies: **SHOULD** ưu tiên thư viện chuẩn trước hết. Chỉ kéo dependency bên thứ ba khi nó xứng đáng (ví dụ `cryptography` để mã hóa khi lưu trữ, `google-cloud-pubsub` cho streaming pull). Giữ các dependency nặng/live phía sau một extra tùy chọn (ví dụ `[live]`) khi unit test không cần chúng.

### 3. Khám phá, bố cục & entry point

Hermes khám phá plugin theo hai cách. Cách bạn hỗ trợ quyết định bố cục của bạn.

- **Entry-point (pip)** — `pip install` expose nhóm entry-point `hermes_agent.plugins`; Hermes import module và gọi `register` của nó.
- **Thư mục (`hermes plugins install <owner>/<repo>`)** — git-clone repo vào `~/.hermes/plugins/<name>/` và thực thi module ở gốc repo. Đường dẫn này **không chạy `pip install` nào**, nên nó chỉ hoạt động cho các plugin **stdlib-only**.

Các quy tắc:

- **MUST** khai báo entry point chỉ là **đường dẫn module** — không có hậu tố `:register`. Hermes làm `getattr(module, "register")`; trỏ vào hàm khiến `register` resolve thành `None`.
  ```toml
  [project.entry-points."hermes_agent.plugins"]
  <name> = "hermes_<name>"
  ```
- **MUST** expose một `register(ctx)` cấp cao nhất và giữ `__init__.py` **mỏng** — một docstring, `__version__`, và một re-export/delegation tới phần triển khai thật trong `plugin.py`. Logic nghiệp vụ **không** nằm trong `__init__`.
- **Bố cục — chọn theo mô hình cài đặt:**
  - *Plugin stdlib-only hỗ trợ cài đặt một-dòng theo thư mục* — **MUST**
    dùng bố cục `src/hermes_<name>/` kèm một shim `__init__.py` ở gốc repo
    đưa `src/` vào `sys.path` và re-export `register` (để bộ nạp thư mục
    tìm thấy một `register` hoạt động tại gốc bản clone). Đường dẫn pip bỏ qua shim.
  - *Plugin có dependency biên dịch/nặng (chỉ pip)* — **SHOULD** dùng một gói phẳng
    `hermes_<name>/` ở gốc repo. Việc chuyển sang `src/` không mua được gì ở đây
    (cài đặt theo thư mục vốn không thể hoạt động) và chỉ làm xáo trộn đóng gói. Quy tắc
    `__init__` mỏng + tách `plugin.py` như trên vẫn áp dụng.
- **MUST** giữ một manifest `plugin.yaml`. Nếu tồn tại cả bản đóng gói
  (`hermes_<name>/plugin.yaml`) lẫn bản gốc (các bản cài theo thư mục đọc
  bản gốc), hãy giữ chúng đồng bộ và ghi rõ điều đó trong một comment.

### 4. Cấu hình & bí mật

- **MUST** resolve mọi thiết lập qua một module cấu hình duy nhất
  (`config.py` với một accessor được cache), không rải rác `os.environ.get(...)`.
- **MUST** đọc **bí mật dưới dạng tệp** từ một mount cấu hình chỉ-đọc (khóa mã hóa,
  JSON client OAuth, khóa service-account) — không bao giờ từ repo, không bao giờ
  commit.
- **SHOULD** đặt tiền tố cho env var theo từng plugin (ví dụ `INBOX_*`), và
  ưu tiên cấu hình không phụ thuộc endpoint: một LLM tương thích OpenAI nên nhận
  `*_BASE_URL` + `*_API_KEY`, không hardcode một nhà cung cấp.
- **SHOULD** đóng gói một CLI `setup`/`status` (một console script `[project.scripts]`,
  cũng chạy được qua `python -m hermes_<name>`) để ghi các tệp cấu hình
  (mode `0600`), sinh khóa, và báo cáo các khả năng đã cấu hình — **không bao giờ
  in ra giá trị bí mật**.

### 5. Bảo mật

- **MUST NOT** ghi log token, bí mật, hoặc PII.
- **MUST** mã hóa thông tin xác thực khi lưu trữ (AES-256-GCM) bằng khóa do người vận hành cung cấp khi plugin lưu token của bên thứ ba.
- **MUST** bọc nội dung không đáng tin (thân email, tin nhắn chat) trước khi
  nội dung đó đến bất kỳ prompt LLM nào, để nó không thể điều khiển mô hình.
- **SHOULD** ưu tiên kết nối ra ngoài hơn bất kỳ bề mặt đầu vào/công khai nào.
- **SHOULD** chặn các công cụ đặc quyền theo chủ sở hữu dựa trên
  `source.user_id` do gateway báo cáo (không phụ thuộc backend — không riêng Matrix), và fail closed.

### 6. Công cụ

- **MUST** lint bằng **ruff**, cấu hình trong `pyproject.toml`:
  ```toml
  [tool.ruff]
  line-length = 100
  target-version = "py311"
  [tool.ruff.lint]
  select = ["E", "F", "I", "W", "UP", "B", "SIM", "RUF"]
  ```
  Nới lỏng nhiễu chỉ dành cho test qua `[tool.ruff.lint.per-file-ignores]` thay vì
  làm yếu bộ chọn toàn cục.
- **MUST** type-check bằng **mypy** và đóng gói `py.typed`. Một cấu hình non-strict là
  được; im lặng các missing stub không thể tránh của các dependency live nạp muộn bằng
  `ignore_missing_imports` theo từng module, không ignore toàn bộ.
- **MUST** kiểm thử bằng **pytest**, và test **MUST chạy hoàn toàn ngoại tuyến** — mạng,
  Google/cloud, và các lời gọi agent nằm sau các seam có thể inject. Hãy giữ nguyên các seam.

### 7. CI

- **MUST** dùng `actions/checkout@v5` + `actions/setup-python@v6` (các action Node-20
  đã EOL).
- **MUST** chạy, khi push vào `main` + các PR:
  1. `ruff check .`
  2. `pytest -q` trên ma trận 3.11–3.14
  3. build sdist+wheel, `twine check`, và **assert manifest/tài nguyên có mặt trong
     wheel** (`unzip -l dist/*.whl | grep -q hermes_<name>/plugin.yaml`).

### 8. Phát hành

- **MUST** publish lên PyPI qua **OIDC Trusted Publishing** — không có API token trong
  repo. Dùng một GitHub Environment `pypi` (và `testpypi`).
- **MUST** kích hoạt trên một tag **`vX.Y.Z`** được push, và job build **MUST assert
  tag khớp với `project.version`** trước khi publish (một lần quên bump sẽ fail
  to tiếng thay vì ship sai phiên bản).
- **SHOULD** cung cấp một target **TestPyPI dry-run** `workflow_dispatch`.
- **MUST** tuân theo SemVer, giữ `pyproject.version` và `__version__` đồng bộ, và
  tạo một **GitHub Release** với ghi chú là phần CHANGELOG tương ứng.

### 9. Tài liệu & sức khỏe cộng đồng

- **MUST** có một `README.md` theo hình mẫu: một dòng giá trị + badge (CI, PyPI,
  Python, License) → **Tại sao tồn tại** → **Bắt đầu nhanh** (copy-paste) →
  **Cập nhật** → **Tài liệu** → các phần tham khảo.
- **MUST** giữ một `CHANGELOG.md` (Keep a Changelog + SemVer).
- **MUST** có `CONTRIBUTING.md`, `SECURITY.md` (báo cáo lỗ hổng riêng tư),
  `.github/ISSUE_TEMPLATE/` (bug + feature + `config.yml` định tuyến báo cáo bảo mật
  một cách riêng tư), và `.github/PULL_REQUEST_TEMPLATE.md`.
- **SHOULD** tài liệu hóa quy trình phát hành (`docs/releasing.md`) và, ở những nơi
  thiết lập phức tạp, đóng gói một `HERMES_SELF_INSTALL.md` mà agent thực thi được để
  một agent Hermes có thể tự cài đặt + cấu hình plugin.

---

*Các thay đổi đối với tiêu chuẩn này nên được thực hiện trong một repo và sao chép sang các repo khác trong cùng một bộ thay đổi, để các bản canonical không bao giờ lệch nhau.*

---
## 🇬🇧 English

Shared conventions for the in-process **Hermes plugins** we (HiTechCloud.VN) build and
maintain. This is the canonical reference; it is committed verbatim to each plugin
repo so they stay in sync.

Current adopters:
- [`hermes-inbox-organizer`](https://github.com/hitechcloudvn/hermes-inbox-organizer)
- [`hermes-chat-recorder`](https://github.com/hitechcloudvn/hermes-chat-recorder)

A plugin is conformant if it follows the **MUST** items below. **SHOULD** items
are strong defaults; deviate only with a comment explaining why.

---

### 1. Identity & metadata

- **MUST** be MIT licensed, with a `LICENSE` file at the repo root.
- **MUST** declare PEP 639 license metadata in `pyproject.toml`:
  `license = "MIT"` + `license-files = ["LICENSE"]`, and
  `requires = ["setuptools>=77"]` in `[build-system]` (Metadata-Version 2.4).
- **MUST** set author to `Nguyễn Thanh An <thanhan92f1@gmail.com> (HiTechCloud.VN)`.
- **MUST** own the repo under the `hitechcloudvn` GitHub org; use that exact
  casing in every URL (`[project.urls]`, badges, docs).
- **SHOULD** set `[project.urls]` Homepage, Repository, Issues, Documentation.
- **SHOULD** keep `classifiers` Development Status honest
  (`4 - Beta` once running in production; `3 - Alpha` while the schema/API churns).

### 2. Python & packaging

- **MUST** target **Python 3.11+** (`requires-python = ">=3.11"`).
- **MUST** test against the matrix **3.11, 3.12, 3.13, 3.14**.
- **MUST** be installable from PyPI as `hermes-<name>` and expose the Hermes
  entry point (see §3).
- **MUST** ship the plugin manifest + any runtime assets as `package-data` (so a
  non-editable `pip install` includes them), and **assert in CI** that they land
  in the built wheel.
- Dependencies: **SHOULD** stay standard-library-first. Pull a third-party dep
  only when it earns its place (e.g. `cryptography` for at-rest encryption,
  `google-cloud-pubsub` for streaming pull). Keep the heavy/live deps behind an
  optional extra (e.g. `[live]`) when the unit tests don't need them.

### 3. Discovery, layout & the entry point

Hermes discovers plugins two ways. Which you support drives your layout.

- **Entry-point (pip)** — `pip install` exposes the `hermes_agent.plugins`
  entry-point group; Hermes imports the module and calls its `register`.
- **Directory (`hermes plugins install <owner>/<repo>`)** — git-clones the repo
  into `~/.hermes/plugins/<name>/` and execs the repo-root module. This path runs
  **no `pip install`**, so it only works for **stdlib-only** plugins.

Rules:

- **MUST** declare the entry point as the **module path only** — no `:register`
  suffix. Hermes does `getattr(module, "register")`; pointing at the function
  makes `register` resolve to `None`.
  ```toml
  [project.entry-points."hermes_agent.plugins"]
  <name> = "hermes_<name>"
  ```
- **MUST** expose a top-level `register(ctx)` and keep `__init__.py` **thin** — a
  docstring, `__version__`, and a re-export/delegation to the real
  implementation in `plugin.py`. Business logic does **not** live in `__init__`.
- **Layout — pick by install model:**
  - *Stdlib-only plugin that supports the one-line directory install* — **MUST**
    use a `src/hermes_<name>/` layout plus a repo-root `__init__.py` shim that
    puts `src/` on `sys.path` and re-exports `register` (so the directory loader
    finds a working `register` at the clone root). The pip path ignores the shim.
  - *Plugin with compiled/heavy deps (pip-only)* — **SHOULD** use a flat
    `hermes_<name>/` package at the repo root. A `src/` move buys nothing here
    (the directory install can't work anyway) and only churns packaging. The
    thin-`__init__` + `plugin.py` split from above still applies.
- **MUST** keep a `plugin.yaml` manifest. If both a packaged copy
  (`hermes_<name>/plugin.yaml`) and a root copy exist (directory installs read
  the root), keep them in sync and say so in a comment.

### 4. Configuration & secrets

- **MUST** resolve every setting through a single config module
  (`config.py` with a cached accessor), not scattered `os.environ.get(...)`.
- **MUST** read **secrets as files** from a read-only config mount (encryption
  keys, OAuth client JSON, service-account keys) — never from the repo, never
  committed.
- **SHOULD** namespace env vars with a per-plugin prefix (e.g. `INBOX_*`), and
  prefer endpoint-agnostic config: an OpenAI-compatible LLM should take a
  `*_BASE_URL` + `*_API_KEY`, not hardcode one provider.
- **SHOULD** ship a `setup`/`status` CLI (a `[project.scripts]` console script,
  also runnable via `python -m hermes_<name>`) that writes the config files
  (mode `0600`), generates keys, and reports configured capabilities — **never
  echoing secret values**.

### 5. Security

- **MUST NOT** log tokens, secrets, or PII.
- **MUST** encrypt credentials at rest (AES-256-GCM) with an operator-supplied
  key when the plugin stores third-party tokens.
- **MUST** fence untrusted content (email bodies, chat messages) before it
  reaches any LLM prompt, so it can't steer the model.
- **SHOULD** prefer outbound connections over any inbound/public surface.
- **SHOULD** owner-gate privileged tools against the gateway-reported
  `source.user_id` (backend-agnostic — not Matrix-specific), and fail closed.

### 6. Tooling

- **MUST** lint with **ruff**, config in `pyproject.toml`:
  ```toml
  [tool.ruff]
  line-length = 100
  target-version = "py311"
  [tool.ruff.lint]
  select = ["E", "F", "I", "W", "UP", "B", "SIM", "RUF"]
  ```
  Relax test-only noise via `[tool.ruff.lint.per-file-ignores]` rather than
  weakening the global set.
- **MUST** type-check with **mypy** and ship `py.typed`. A non-strict config is
  fine; silence unavoidable missing stubs for lazily-imported live deps with
  per-module `ignore_missing_imports`, not blanket ignores.
- **MUST** test with **pytest**, and tests **MUST run fully offline** — network,
  Google/cloud, and agent calls sit behind injectable seams. Preserve the seams.

### 7. CI

- **MUST** use `actions/checkout@v5` + `actions/setup-python@v6` (Node-20 actions
  are EOL).
- **MUST** run, on push to `main` + PRs:
  1. `ruff check .`
  2. `pytest -q` across the 3.11–3.14 matrix
  3. build sdist+wheel, `twine check`, and **assert the manifest/assets are in
     the wheel** (`unzip -l dist/*.whl | grep -q hermes_<name>/plugin.yaml`).

### 8. Release

- **MUST** publish to PyPI via **OIDC Trusted Publishing** — no API tokens in the
  repo. Use a `pypi` (and `testpypi`) GitHub Environment.
- **MUST** trigger on a pushed **`vX.Y.Z` tag**, and the build job **MUST assert
  the tag matches `project.version`** before publishing (a forgotten bump fails
  loudly instead of shipping the wrong version).
- **SHOULD** offer a `workflow_dispatch` **TestPyPI dry-run** target.
- **MUST** follow SemVer, keep `pyproject.version` and `__version__` in sync, and
  cut a **GitHub Release** whose notes are the CHANGELOG section.

### 9. Docs & community health

- **MUST** have a `README.md` shaped: one-line value prop + badges (CI, PyPI,
  Python, License) → **Why this exists** → **Quick Start** (copy-paste) →
  **Updating** → **Documentation** → reference sections.
- **MUST** keep a `CHANGELOG.md` (Keep a Changelog + SemVer).
- **MUST** have `CONTRIBUTING.md`, `SECURITY.md` (private vulnerability
  reporting), `.github/ISSUE_TEMPLATE/` (bug + feature + `config.yml` routing
  security reports privately), and `.github/PULL_REQUEST_TEMPLATE.md`.
- **SHOULD** document the release process (`docs/releasing.md`) and, where the
  setup is involved, ship an agent-executable `HERMES_SELF_INSTALL.md` so a
  Hermes agent can install + configure the plugin itself.

---

*Changes to this standard should be made in one repo and copied to the others in
the same change set, so the canonical copies never drift.*
