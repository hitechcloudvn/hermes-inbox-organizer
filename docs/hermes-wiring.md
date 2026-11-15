# Hermes Wiring — enabling the plugin

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

Plugin load **in-process** với Hermes agent. Không có MCP server, không có URL, và không có bearer token — bạn bật nó trong config của agent và nó đăng ký tools + daemon tại thời điểm load.

### config.yaml

```yaml
plugins:
  enabled:
    - inbox_organizer        # the entry-point name (pyproject: inbox_organizer = "hermes_inbox_organizer")
```

Đó là toàn bộ wiring. Mọi thứ khác (OAuth client, tọa độ Pub/Sub, encryption key, owner allowlist) được đọc từ config mount và env `INBOX_*` — xem [setup.md](./setup.md).

#### Cấu hình mà plugin đọc

| Nguồn | Mục đích |
|---|---|
| `config/inbox-oauth-client.json` | OAuth client + `owner_matrix_ids` (allowlist) |
| `config/inbox-pubsub.json` | `{project, topic, subscription}` |
| `config/inbox-pubsub-sa.json` | SA key `pubsub.subscriber` (xác thực streaming pull) |
| `config/inbox-encryption-key` | Khóa AES-GCM cho token khi lưu trữ |
| env `OPENROUTER_API_KEY` | Classifier dự phòng bằng LLM |
| env `INBOX_*` (tùy chọn) | overrides — `INBOX_DATA_DIR`, `INBOX_DB_PATH`, `INBOX_CLASSIFIER_MODEL`, `INBOX_OWNER_MATRIX_IDS`, `INBOX_LABELS_ENABLED` (off = chỉ classify/draft, không nhãn hay archive), … (xem `config.py`) |

### Agent tools

`register(ctx)` expose các công cụ sau cho agent:

| Tool | Mô tả |
|---|---|
| `inbox_list_accounts` | Liệt kê các tài khoản Gmail đã kết nối |
| `inbox_list_emails` | Tìm kiếm/liệt kê mail qua các inbox (cú pháp tìm kiếm Gmail) |
| `inbox_get_email` | Lấy một message |
| `inbox_get_thread` | Lấy một thread + các message của nó |
| `inbox_unread_rollup` | Digest "có gì cần tôi?" theo yêu cầu qua các tài khoản (chỉ đọc) |
| `inbox_create_draft` | Viết một reply **draft** cho một thread (không bao giờ gửi) — Hermes soạn thân thư |
| `inbox_connect_account` / `inbox_complete_connection` / `inbox_disconnect_account` | Onboarding tài khoản — chỉ owner |
| `inbox_draft_feedback_status` | Xem vòng reinforcement loop đã học được gì (histogram outcome, các bài lesson, các người gửi có learned note) — chỉ đọc |
| `inbox_forget_lesson` | Tắt mềm một bài lesson do/don't đã học theo id — owner-gated |
| `inbox_clear_learned_notes` | Xóa learned voice note của một người tương ứng — owner-gated |

Daemon cũng phân loại + gắn nhãn mail và tự kích hoạt draft — đó không phải tools, chúng diễn ra trong nền.

### Owner gating

Các công cụ quản lý tài khoản bị giới hạn cho owner qua một hook `pre_tool_call` kiểm tra sender của lượt đó với `owner_matrix_ids` (resolve theo từng lượt qua `pre_gateway_dispatch` → `pre_llm_call`). Một lời gọi không phải owner bị chặn.

### Kiểm chứng

Sau khi bật + build lại, boot log cho thấy hook đang load và các daemon thread khởi lên:

```
[hooks] Loaded hook 'inbox-organizer-boot' for events: ['gateway:startup']
[inbox-organizer-boot] inbox daemon threads alive: ['inbox-poll-reconciler', 'inbox-watch-renewal']
```

Rồi yêu cầu agent chạy `inbox_list_accounts` để xác nhận các tool đang sống.
(Runtime log qua Python `logging`, không có trên docker stdout — xác nhận daemon qua các dòng boot-hook thread đó, không phải bằng cách grep runtime log.)

### Đọc thêm

- [draft-reinforcement-loop.md](./draft-reinforcement-loop.md) — vòng phản hồi draft hoạt động ra sao, tất cả knob `INBOX_DRAFT_FEEDBACK_*`, và cách xem xét hay revert trạng thái đã học

---

## 🇬🇧 English

The plugin loads **in-process** with the Hermes agent. There is no MCP server,
no URL, and no bearer token — you enable it in the agent's config and it
registers its tools + daemon at load time.

### config.yaml

```yaml
plugins:
  enabled:
    - inbox_organizer        # the entry-point name (pyproject: inbox_organizer = "hermes_inbox_organizer")
```

That's the whole wiring. Everything else (OAuth client, Pub/Sub coordinates,
encryption key, owner allowlist) is read from the config mount and `INBOX_*`
env — see [setup.md](./setup.md).

#### Config the plugin reads

| Source | Purpose |
|---|---|
| `config/inbox-oauth-client.json` | OAuth client + `owner_matrix_ids` (the allowlist) |
| `config/inbox-pubsub.json` | `{project, topic, subscription}` |
| `config/inbox-pubsub-sa.json` | `pubsub.subscriber` SA key (streaming pull auth) |
| `config/inbox-encryption-key` | AES-GCM key for tokens at rest |
| env `OPENROUTER_API_KEY` | LLM-fallback classifier |
| env `INBOX_*` (optional) | overrides — `INBOX_DATA_DIR`, `INBOX_DB_PATH`, `INBOX_CLASSIFIER_MODEL`, `INBOX_OWNER_MATRIX_IDS`, `INBOX_LABELS_ENABLED` (off = classify/draft only, no labels or archiving), … (see `config.py`) |

### Agent tools

`register(ctx)` exposes these to the agent:

| Tool | Description |
|---|---|
| `inbox_list_accounts` | List connected Gmail accounts |
| `inbox_list_emails` | Search/list mail across inboxes (Gmail search syntax) |
| `inbox_get_email` | Fetch a single message |
| `inbox_get_thread` | Fetch a thread + its messages |
| `inbox_unread_rollup` | On-demand "what needs me?" digest across accounts (read-only) |
| `inbox_create_draft` | Write a reply **draft** for a thread (never sends) — Hermes composes the body |
| `inbox_connect_account` / `inbox_complete_connection` / `inbox_disconnect_account` | Owner-only account onboarding |
| `inbox_draft_feedback_status` | Inspect what the reinforcement loop has learned (outcome histogram, lessons, learned-note senders) — read-only |
| `inbox_forget_lesson` | Soft-disable a learned do/don't lesson by id — owner-gated |
| `inbox_clear_learned_notes` | Clear a correspondent's learned voice note — owner-gated |

The daemon also classifies + labels mail and triggers drafts autonomously — those
aren't tools, they happen in the background.

### Owner gating

The account-management tools are restricted to the owner via a `pre_tool_call`
hook that checks the turn's sender against `owner_matrix_ids` (resolved per turn
through `pre_gateway_dispatch` → `pre_llm_call`). A non-owner call is blocked.

### Verifying

After enabling + rebuilding, the boot log shows the hook loading and the daemon
threads coming up:

```
[hooks] Loaded hook 'inbox-organizer-boot' for events: ['gateway:startup']
[inbox-organizer-boot] inbox daemon threads alive: ['inbox-poll-reconciler', 'inbox-watch-renewal']
```

Then ask the agent to run `inbox_list_accounts` to confirm the tools are live.
(The runtime logs via Python `logging`, which isn't on docker stdout — confirm
the daemon via those boot-hook thread lines, not by grepping for runtime logs.)

### Further reading

- [draft-reinforcement-loop.md](./draft-reinforcement-loop.md) — how the draft
  feedback loop works, all `INBOX_DRAFT_FEEDBACK_*` knobs, and how to inspect
  or revert the learned state
