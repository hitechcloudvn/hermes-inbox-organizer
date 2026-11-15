# Contributing

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

Cảm ơn bạn đã quan tâm đến hermes-inbox-organizer. Đây là một gói Python duy nhất (`hermes_inbox_organizer/`) được nạp vào một agent [Hermes](https://hermes-agent.nousresearch.com) dưới dạng plugin. Chúng tôi hoan nghênh các issue và pull request.

### Thiết lập phát triển

```sh
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest -q     # the suite runs offline — no Hermes or live Google needed
ruff check .                      # lint
mypy                              # type-check
```

Bộ unit test chạy hoàn toàn ngoại tuyến — các lời gọi mạng, Google và agent đều nằm sau các seam mà test giả lập. **Hãy giữ nguyên các seam đó**: một thay đổi khiến bộ test cần thông tin xác thực trực tiếp hoặc một Hermes đang chạy sẽ không được chấp nhận.

Plugin này tuân theo [Hermes Plugin Standard](HERMES_PLUGIN_STANDARD.md) dùng chung — các quy ước về đóng gói, công cụ, CI, phát hành và bảo mật được dùng chung cho các plugin Hermes của chúng tôi. Hãy đọc lướt qua tài liệu đó trước khi thực hiện một thay đổi đáng kể.

### Quy ước

Các quy ước này phản chiếu `CLAUDE.md`, vốn là nguồn dữ liệu chính thức:

- **Cấu hình** — đọc mọi thiết lập `INBOX_*` qua `config.get_config()`. Đừng rải rác `os.environ.get(...)` trong mã mới.
- **Cơ sở dữ liệu** — SQLite qua `db.py`. Dùng `db.connect()` và các accessor có kiểu; đừng mở kết nối thô ở nơi khác.
- **Ghi log** — stdlib `logging` (`logging.getLogger(__name__)`). **Không bao giờ ghi log token, bí mật OAuth, hoặc nội dung email/PII.**
- **Bảo mật** — nội dung email không đáng tin được bọc trong các hàng rào ngẫu nhiên trước khi đưa vào bất kỳ prompt LLM nào (`classifier.py`); hãy giữ nguyên như vậy. Các token OAuth được mã hóa AES-256-GCM khi lưu trữ (`crypto.py` / `token_store.py`).
- **Bản nháp** — plugin chỉ kích hoạt agent và ghi bản nháp MIME. Nó không bao giờ gửi thư.

### Pull request

1. Fork và tạo nhánh từ `main`.
2. Giữ thay đổi tập trung; thêm hoặc cập nhật test cho các thay đổi hành vi.
3. Đảm bảo `pytest`, `ruff check .` và `mypy` đều đạt.
4. Dùng tiêu đề [Conventional Commit](https://www.conventionalcommits.org/) để khớp với lịch sử commit, ví dụ `feat(classifier): …`, `fix(dashboard): …`, `docs(readme): …`.
5. Ghi lại mọi thay đổi ảnh hưởng đến người dùng trong `CHANGELOG.md` dưới mục `## [Unreleased]`.

### Báo lỗi / vấn đề bảo mật

Hãy dùng [các mẫu issue](https://github.com/hitechcloudvn/hermes-inbox-organizer/issues/new/choose) cho lỗi và yêu cầu tính năng. Với bất kỳ vấn đề bảo mật nào, **đừng mở issue công khai** — hãy làm theo [SECURITY.md](SECURITY.md) thay vì vậy.

---
## 🇬🇧 English

Thanks for your interest in hermes-inbox-organizer. This is a single Python
package (`hermes_inbox_organizer/`) that loads into a [Hermes](https://hermes-agent.nousresearch.com)
agent as a plugin. Issues and pull requests are welcome.

### Development setup

```sh
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest -q     # the suite runs offline — no Hermes or live Google needed
ruff check .                      # lint
mypy                              # type-check
```

The unit tests run entirely offline — network, Google, and agent calls sit behind
seams that the tests stub. **Preserve those seams**: a change that makes the
suite require live credentials or a running Hermes won't be accepted.

This plugin follows the shared [Hermes Plugin Standard](HERMES_PLUGIN_STANDARD.md)
— packaging, tooling, CI, release, and security conventions used across our Hermes
plugins. Skim it before a substantial change.

### Conventions

These mirror `CLAUDE.md`, which is the source of truth:

- **Config** — read every `INBOX_*` setting through `config.get_config()`. Don't
  scatter `os.environ.get(...)` in new code.
- **Database** — SQLite via `db.py`. Use `db.connect()` and the typed accessors;
  don't open raw connections elsewhere.
- **Logging** — stdlib `logging` (`logging.getLogger(__name__)`). **Never log
  tokens, OAuth secrets, or email contents/PII.**
- **Security** — untrusted email content is wrapped in randomized fences before
  any LLM prompt (`classifier.py`); keep it that way. OAuth tokens are
  AES-256-GCM encrypted at rest (`crypto.py` / `token_store.py`).
- **Drafts** — the plugin only triggers the agent and writes the MIME draft. It
  never sends mail.

### Pull requests

1. Fork and branch from `main`.
2. Keep changes focused; add or update tests for behavior changes.
3. Make sure `pytest`, `ruff check .`, and `mypy` all pass.
4. Use [Conventional Commit](https://www.conventionalcommits.org/) subjects to
   match the history, e.g. `feat(classifier): …`, `fix(dashboard): …`,
   `docs(readme): …`.
5. Note any user-facing change in `CHANGELOG.md` under `## [Unreleased]`.

### Reporting bugs / security issues

Use the [issue templates](https://github.com/hitechcloudvn/hermes-inbox-organizer/issues/new/choose)
for bugs and feature requests. For anything security-sensitive, **do not open a
public issue** — follow [SECURITY.md](SECURITY.md) instead.
