# Dashboard — connect & remove accounts from the web UI

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

Plugin đi kèm một **dashboard plugin** tùy chọn, thêm tab **Inbox Organizer** vào Hermes web dashboard (`hermes dashboard`). Đây là một UI mỏng phủ trên cùng kho token được mã hóa mà daemon dùng, phục vụ một việc bất tiện khi thao tác qua chat: **kết nối và gỡ tài khoản Google**.

Nó bổ sung — chứ không thay thế — các công cụ onboarding qua chat (`inbox_connect_account` / `inbox_disconnect_account`); dùng cách nào bạn thích.

### Tab này làm gì

- **Liệt kê** các tài khoản Google đã kết nối.
- **Kết nối** — copy-paste OAuth: bấm *Connect a Google account*, phê duyệt trong tab Google, dán mã từ trang callback, *Finish*.
- **Gỡ** — thu hồi tài khoản tại Google và xóa token đã lưu.

Kết nối/gỡ chỉ đụng tới các file token được mã hóa trong data dir; daemon đang chạy sẽ hội tụ tập tài khoản live của nó ở lần poll kế tiếp (≤ ~5 phút) hoặc khi khởi động lại — xem [Convergence](#convergence).

### Cách nó được nối vào như một Hermes dashboard plugin

Hermes web dashboard mở rộng được qua thư mục `dashboard/` dưới `$HERMES_HOME/plugins/<name>/` chứa `manifest.json`, một JS bundle, và tùy chọn một `plugin_api.py` FastAPI ([upstream docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard)). Khác với CLI/gateway plugin (load qua entry point `hermes_agent.plugins`), dashboard plugin được **khám phá theo thư mục** — không có entry-point hook — nên package chiếu `dashboard/` đóng gói của nó vào `$HERMES_HOME/plugins/inbox_organizer/dashboard/`:

- **Khi plugin load** — `register()` tự chiếu nó, nên mọi kiểu cài đặt (kể cả `pip install` thường) đều có tab.
- **pip / thủ công** — (cài lại) bất cứ lúc nào với `hermes inbox-organizer install-dashboard`.
- **Baked image** — entrypoint cũng chiếu nó khi boot (ngang hàng với dashboard-visibility shim), nên tab tồn tại từ trước lượt agent đầu tiên.

Logic backend nằm trong package đã cài (`hermes_inbox_organizer.dashboard_api`); `dashboard/plugin_api.py` được chiếu là một dòng re-export, nên các route được version và unit-test cùng plugin.

> **Khởi động lại dashboard sau lần cài đầu tiên.** Hermes gắn các route backend của plugin một lần khi dashboard khởi động, nên `plugin_api.py` vừa được chiếu cần khởi động lại `hermes dashboard`. (Riêng *tab* có thể được nhận mà không cần khởi động lại qua `GET /api/dashboard/plugins/rescan`.)

### Xác thực

Các route backend của plugin (`/api/plugins/inbox_organizer/*`) **bỏ qua xác thực session-token** — đó là cách các Hermes dashboard plugin hoạt động; dashboard bind vào localhost và auth của chính nó là cổng chặn. Plugin này **single-owner**, nên nó không thêm cổng chặn riêng: bất kỳ ai tới được dashboard đều có thể kết nối/gỡ tài khoản. Giữ dashboard chỉ ở localhost (SSH-tunnel tới nó) hoặc sau gated-mode auth của dashboard — **không** serve với `--host 0.0.0.0` trên mạng không tin cậy.

(Các công cụ onboarding qua chat bị chặn khác — bởi `owner_matrix_ids`. Dashboard không có khái niệm per-sender, nên nó dựa vào access control của chính dashboard. Xem [security.md](./security.md).)

### Hội tụ

Dashboard chạy trong một **process riêng** với gateway/daemon; chúng chỉ chia sẻ volume `/opt/data`. Vì thế tab không thể hot-add/remove một tài khoản trực tiếp trong memory của daemon — nó ghi/xóa file token được mã hóa, và **poll reconciler** của daemon diff các token trên đĩa so với tập live của nó mỗi tick:

- file token mới → arm watch + bắt đầu triage nó
- file token bị xóa → đưa nó ra khỏi routing
- file token **thay đổi** (một lần kết nối lại, ví dụ sau khi refresh-token hết hạn 7 ngày) → re-arm nó và xóa reconnect nudge của owner

Vậy một lần kết nối/gỡ từ tab có hiệu lực trong một poll interval, không cần khởi động lại. (Cùng reconciler đó là thứ làm cho một lần kết nối bằng chat-tool trên một process hiện ra với daemon.)

### Đọc thêm

- [setup.md](./setup.md) — triển khai plugin (image + entrypoint)
- [security.md](./security.md) — mã hóa token + owner gate
- [oauth-modes.md](./oauth-modes.md) — OAuth audience Testing vs Production

---

## 🇬🇧 English

The plugin ships an optional **dashboard plugin** that adds an **Inbox Organizer**
tab to the Hermes web dashboard (`hermes dashboard`). It's a thin UI over the same
encrypted token store the daemon uses, for the one thing that's awkward in chat:
**connecting and removing Google accounts**.

It's additive to — not a replacement for — the chat onboarding tools
(`inbox_connect_account` / `inbox_disconnect_account`); use whichever you prefer.

### What the tab does

- **Lists** the connected Google accounts.
- **Connect** — copy-paste OAuth: click *Connect a Google account*, approve in the
  Google tab, paste the code from the callback page, *Finish*.
- **Remove** — revokes the account at Google and deletes its stored token.

Connect/remove only touch the encrypted token files in the data dir; the running
daemon converges its live account set on its next poll tick (≤ ~5 min) or on
restart — see [Convergence](#convergence).

### How it's wired as a Hermes dashboard plugin

Hermes's web dashboard is extensible via a `dashboard/` directory under
`$HERMES_HOME/plugins/<name>/` holding a `manifest.json`, a JS bundle, and an
optional FastAPI `plugin_api.py`
([upstream docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/extending-the-dashboard)).
Unlike the CLI/gateway plugin (loaded via the `hermes_agent.plugins` entry point),
dashboard plugins are **directory-discovered** — there is no entry-point hook — so
the package projects its bundled `dashboard/` into
`$HERMES_HOME/plugins/inbox_organizer/dashboard/`:

- **On plugin load** — `register()` self-projects it, so any install (including a
  plain `pip install`) gets the tab.
- **pip / manual** — (re)install any time with `hermes inbox-organizer install-dashboard`.
- **Baked image** — the entrypoint also projects it at boot (parity with the
  dashboard-visibility shim), so the tab exists before the first agent turn.

The backend logic lives in the installed package
(`hermes_inbox_organizer.dashboard_api`); the projected `dashboard/plugin_api.py`
is a one-line re-export, so the routes version and unit-test with the plugin.

> **Restart the dashboard after first install.** Hermes mounts plugin backend
> routes once at dashboard startup, so a freshly projected `plugin_api.py` needs a
> `hermes dashboard` restart. (The *tab* alone can be picked up without a restart
> via `GET /api/dashboard/plugins/rescan`.)

### Authentication

The plugin's backend routes (`/api/plugins/inbox_organizer/*`) **bypass
session-token auth** — that's how Hermes dashboard plugins work; the dashboard
binds to localhost and its own auth is the gate. This plugin is **single-owner**,
so it adds no extra gate of its own: anyone who can reach the dashboard can
connect/remove accounts. Keep the dashboard localhost-only (SSH-tunnel it) or
behind the dashboard's gated-mode auth — do **not** serve it with `--host 0.0.0.0`
on an untrusted network.

(The chat onboarding tools are gated differently — by `owner_matrix_ids`. The
dashboard has no per-sender concept, so it relies on the dashboard's own access
control instead. See [security.md](./security.md).)

### Convergence

The dashboard runs in a **separate process** from the gateway/daemon; they share
only the `/opt/data` volume. So the tab can't hot-add/remove an account in the
daemon's memory directly — it writes/deletes the encrypted token file, and the
daemon's **poll reconciler** diffs the on-disk tokens against its live set each
tick:

- new token file → arm the watch + start triaging it
- deleted token file → drop it from routing
- **changed** token file (a reconnect, e.g. after a 7-day refresh-token expiry) →
  re-arm it and clear the owner's reconnect nudge

So a connect/remove from the tab goes live within one poll interval, no restart
needed. (The same reconciler is what makes a chat-tool connect on one process
visible to the daemon.)

### Further reading

- [setup.md](./setup.md) — deploying the plugin (image + entrypoint)
- [security.md](./security.md) — token encryption + the owner gate
- [oauth-modes.md](./oauth-modes.md) — Testing vs Production OAuth audience
