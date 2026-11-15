# Draft reinforcement loop

**Tiếng Việt** | **English**

---

## 🇻🇳 Tiếng Việt

Plugin đóng vòng phản hồi quanh việc viết draft: nó ghi lại những gì đã soạn, quan sát những gì bạn thực sự gửi (hoặc không gửi), chưng cất phần chỉnh sửa, và đưa kết quả đó trở lại các brief soạn draft tương lai để bản nháp cải thiện dần theo thời gian.

**Đây là in-context learning-from-edits, không phải fine-tune model.** Hermes sở hữu model soạn thảo; plugin không đụng được vào trọng số của nó. Tín hiệu định hình nội dung của *brief*: ghi chú giọng văn đã học theo từng người gửi, các bài học do/don't toàn cục, và các câu trả lời gold-example. Tất cả được feed vào `brief.build_draft_brief` lúc soạn draft, có fence và gắn nhãn UNTRUSTED để định hướng giọng văn mà không trở thành chỉ thị thực thi được.

---

### Cách hoạt động

1. **Bắt draft.** Khi `inbox_create_draft` ghi một reply draft vào Gmail, nó cũng lưu thân draft (cắt bớt theo cap) vào `draft_outcomes` trong `state.db`, khóa theo `(account, thread_id)`.

2. **Ghép outcome.** Khi bạn gửi reply trên một thread đã có draft, observer `DraftFeedbackModule.on_sent` so sánh draft↔sent:
   - `sent_verbatim` — độ tương đồng ≥ `VERBATIM_THRESHOLD` (mặc định 92): draft được gửi gần như nguyên xi; được củng cố mà không cần gọi LLM.
   - `sent_edited` — độ tương đồng ≥ `EDIT_THRESHOLD` (mặc định 45): bạn đã sửa nó; được chưng cất qua LLM để trích hướng dẫn phong cách viết.
   - `sent_ignored` — độ tương đồng dưới `EDIT_THRESHOLD`: bạn viết một reply hoàn toàn mới; được xử lý như một tín hiệu chỉnh sửa mạnh hơn.
   - `sent_no_draft` — bạn gửi trên một thread plugin không soạn draft; được bắt lại làm gold-example khi `capture_all_sent` bật (mặc định).
   - `no_reply` — cửa sổ draft trôi qua mà không quan sát thấy lần gửi nào; được đánh dấu bởi periodic sweep **chỉ** khi mailbox demonstrably sống suốt cửa sổ đó (liveness-gated — xem bên dưới).

3. **Chưng cất.** Với `sent_edited` và `sent_ignored`, plugin gọi local LLM (qua OpenRouter, cùng đường dẫn với classifier). Thân draft và thân sent được bọc trong **randomized fences** và prompt chỉ thị model chỉ trích xuất hướng dẫn phong cách viết — model không bao giờ được làm theo chỉ thị tìm thấy bên trong fence. Kết quả được áp vào một **learned layer riêng** (`sender_profiles.learned_notes` + bảng `draft_lessons`) có thể audit và revert. Voice profile backfill gốc (`voice_notes`, `tone_hints`) không bao giờ bị ghi đè.

4. **Tiêm vào brief.** Learned layer được tiêm vào drafting brief (có fence + bounded): một ghi chú giọng văn đã học theo từng người gửi, tối đa `max_lessons` quy tắc do/don't toàn cục xếp hạng theo evidence count, và tối đa `max_examples` câu trả lời gold-example gần đây từ người tương ứng đó. Mỗi block được fence là UNTRUSTED để chống prompt-injection từ nội dung đã học tích lũy.

5. **Quét định kỳ.** Mỗi `sweep_interval_s` (mặc định 6 giờ), sweep:
   - Đánh dấu các dòng `pending` cũ hơn `no_reply_hours` (mặc định 72 giờ) thành `no_reply` — **chỉ** nếu tài khoản được quản lý, không chờ kết nối lại, VÀ đã được drain thành công sau khi draft được tạo (`accounts.updated_at_ms > draft_created_ms`). Một đợt token outage để nguyên các dòng `pending` thay vì ghi nhầm `no_reply`.
   - Thử lại bất kỳ lần chưng cất nào hỏng trên nhánh `on_sent`.
   - Dọn các bài học ít bằng chứng (soft-evict vượt store cap 20) và xóa các learned outcome cũ hơn `retention_days` (mặc định 90 ngày) để chặn `draft_outcomes` phình to.

---

### Các nút cấu hình (`INBOX_DRAFT_FEEDBACK_*`)

Tất cả các nút đều là tùy chọn — mặc định hiển thị bên dưới. Đặt chúng trong `.env` của Hermes hoặc khối environment của `docker-compose.yml`.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `INBOX_DRAFT_FEEDBACK_ENABLED` | `true` | Bật/tắt toàn bộ vòng lặp. Đặt `false` để opt-out mà không cần gỡ plugin. |
| `INBOX_DRAFT_FEEDBACK_CAPTURE_ALL_SENT` | `true` | Bắt các câu trả lời gold-example trên những thread plugin không soạn draft (chỉ gửi một người nhận). Đặt `false` để chỉ ghi các thread đã soạn draft. |
| `INBOX_DRAFT_FEEDBACK_NO_REPLY_HOURS` | `72` | Số giờ sau khi draft được tạo trước khi một thread không được trả lời đủ điều kiện bị đánh dấu `no_reply` (liveness-gated — xem trên). |
| `INBOX_DRAFT_FEEDBACK_SWEEP_INTERVAL_S` | `21600` | Số giây giữa các lần sweep (mặc định 6 giờ). |
| `INBOX_DRAFT_FEEDBACK_MAX_EXAMPLES` | `3` | Số câu trả lời gold-example tối đa được tiêm vào drafting brief cho mỗi người tương ứng. |
| `INBOX_DRAFT_FEEDBACK_MAX_LESSONS` | `8` | Số bài học do/don't toàn cục tối đa được tiêm vào brief (xếp hạng theo evidence count). Store cap (20) là một module constant riêng. |
| `INBOX_DRAFT_FEEDBACK_RETENTION_DAYS` | `90` | Xóa các dòng outcome `learned=1` cũ hơn N ngày. Đặt `0` để tắt retention pruning. |
| `INBOX_DRAFT_FEEDBACK_VERBATIM_THRESHOLD` | `92` | Điểm tương đồng (0–100) mà từ đó một reply được gửi được coi là verbatim (không gọi LLM, chỉ củng cố dương). Tinh chỉnh nếu bạn chỉ sửa draft tối thiểu trước khi gửi. |
| `INBOX_DRAFT_FEEDBACK_EDIT_THRESHOLD` | `45` | Điểm tương đồng mà từ đó một reply được gửi là `sent_edited` (chưng cất bằng LLM); dưới ngưỡng này → `sent_ignored` (chưng cất LLM mạnh hơn). Tinh chỉnh để hiệu chỉnh mức độ học tích cực của vòng lặp. |

---

### Công cụ cho owner — xem xét và revert

Trạng thái đã học có thể audit và revert hoàn toàn bởi owner qua các agent tool.

#### `inbox_draft_feedback_status`

Chỉ đọc. Trả về:
- **`outcomes`** — histogram của tất cả các loại outcome (`pending`, `sent_verbatim`, `sent_edited`, `sent_ignored`, `no_reply`, `sent_no_draft`) kèm số đếm.
- **`active_lessons`** — các quy tắc do/don't toàn cục đang active với `lesson_id`, `polarity`, văn bản `rule`, và `evidence_count`.
- **`learned_senders`** — những người tương ứng nào có ghi chú giọng văn đã học, kèm độ dài ghi chú và timestamp cập nhật lần cuối (không in văn bản ghi chú ở đây; dùng `inbox_get_sender_profile` để đọc toàn bộ ghi chú).

Tham số tùy chọn: `account_id` để giới hạn vào một mailbox.

#### `inbox_forget_lesson`

Tắt mềm một bài học toàn cục theo `lesson_id` (đặt `active=0`). Bài học ngừng ảnh hưởng đến các draft tương lai nhưng được giữ lại trong DB để tham khảo. Dùng `inbox_draft_feedback_status` để tìm `lesson_id`.

Tham số bắt buộc: `lesson_id` (số nguyên).

*Owner-gated — chặn với người gọi không phải owner.*

#### `inbox_clear_learned_notes`

Xóa ghi chú giọng văn learned-from-edits của một người tương ứng. Profile `voice_notes` / `tone_hints` backfill gốc được giữ nguyên. Dùng để hoàn tác một ghi chú được chưng cất từ một email xấu hoặc có chủ đích tấn công.

Tham số bắt buộc: `account_id`, `sender_email`.

*Owner-gated — chặn với người gọi không phải owner.*

---

### Dữ liệu và schema

Tất cả trạng thái đã học nằm trong `state.db` (SQLite DB trong Hermes data volume, mặc định `/opt/data/inbox-organizer/state.db`):

| Bảng / cột | Nội dung |
|---|---|
| `draft_outcomes` | Thân draft + thân sent + outcome + độ tương đồng theo `(account, thread_id)`. Kho gold-example. |
| `draft_lessons` | Các quy tắc do/don't đã học toàn cục; `evidence_count` đếm có bao nhiêu delta ủng hộ mỗi quy tắc. |
| `sender_profiles.learned_notes` | Ghi chú giọng văn đã học theo từng người gửi (cột riêng với `voice_notes` — không bao giờ ghi đè layer backfill). |
| `sender_profiles.learned_updated_ms` | Timestamp lần cập nhật ghi chú đã học gần nhất của một người gửi. |

Đây là **schema v3**. Khi triển khai, `state.db` hiện có được migrate tại chỗ: hai bảng mới (`draft_outcomes`, `draft_lessons`) được tạo tự động, và hai cột mới trên `sender_profiles` được thêm qua một `ALTER TABLE` có guard. Không mất dữ liệu; một image v2 chạy với DB v3 đơn giản là bỏ qua các bảng/cột mới.

---

### Ghi chú bảo mật

- Mọi thân email (draft và sent) đều được bọc trong **randomized fences** trước khi đưa cho LLM chưng cất, và lần nữa khi được tiêm vào brief. System prompt chỉ thị model không bao giờ làm theo chỉ thị nằm bên trong fence.
- Learned layer được giữ tách biệt tuyệt đối với backfill voice profile. Ngay cả khi một ghi chú chưng cất có chủ đích tấn công, `inbox_clear_learned_notes` gỡ nó mà không đụng tới profile nền.
- Không thân email nào từng được ghi log. Chỉ các nhãn outcome, điểm tương đồng, thread id, và số đếm xuất hiện trong log.
- Xem [security.md](./security.md) để hiểu mô hình bảo mật tổng thể.

---

## 🇬🇧 English

The plugin closes the feedback loop on draft writing: it records what it
drafted, observes what you actually sent (or didn't), distils the correction,
and feeds it back into future drafting briefs so drafts improve over time.

**This is in-context learning-from-edits, not model fine-tuning.** Hermes owns
the drafting model; the plugin can't touch its weights. The signal shapes what
the *brief* contains: per-sender learned voice notes, global do/don't lessons,
and gold-example replies. All of it feeds `brief.build_draft_brief` at draft
time, fenced and labelled UNTRUSTED so it guides voice without becoming
executable instructions.

---

### How it works

1. **Draft capture.** When `inbox_create_draft` writes a reply draft to Gmail
   it also persists the draft body (truncated to a cap) to `draft_outcomes` in
   `state.db`, keyed on `(account, thread_id)`.

2. **Outcome pairing.** When you send a reply on a drafted thread, the
   `DraftFeedbackModule.on_sent` observer compares draft↔sent:
   - `sent_verbatim` — similarity ≥ `VERBATIM_THRESHOLD` (default 92): the
     draft landed as-is; reinforced without an LLM call.
   - `sent_edited` — similarity ≥ `EDIT_THRESHOLD` (default 45): you changed
     it; distilled via LLM to extract writing-style guidance.
   - `sent_ignored` — similarity below `EDIT_THRESHOLD`: you wrote a fresh
     reply; treated as a stronger edit signal.
   - `sent_no_draft` — you sent on a thread the plugin didn't draft; captured
     as a gold example when `capture_all_sent` is on (default).
   - `no_reply` — the draft window elapsed with no send observed; marked by the
     periodic sweep only when the mailbox was demonstrably live through the
     window (liveness-gated — see below).

3. **Distillation.** For `sent_edited` and `sent_ignored` the plugin calls the
   local LLM (via OpenRouter, the same path as the classifier). The draft and
   sent bodies are wrapped in **randomized fences** and the prompt instructs the
   model to extract only writing-style guidance — it may never follow
   instructions found inside the fences. The result is applied to a **separate
   learned layer** (`sender_profiles.learned_notes` + the `draft_lessons` table)
   that is auditable and revertible. The original backfill voice profile
   (`voice_notes`, `tone_hints`) is never overwritten.

4. **Brief injection.** The learned layer is injected into the drafting brief
   (fenced + bounded): a per-sender learned voice note, up to
   `max_lessons` global do/don't rules ranked by evidence count, and up to
   `max_examples` recent gold-example replies from that correspondent. Each
   block is fenced as UNTRUSTED to prevent prompt-injection from accumulated
   learned content.

5. **Periodic sweep.** Every `sweep_interval_s` (default 6 h) the sweep:
   - Marks `pending` rows older than `no_reply_hours` (default 72 h) as
     `no_reply` — **only** if the account is managed, not awaiting reconnect,
     AND was drained successfully after the draft was created
     (`accounts.updated_at_ms > draft_created_ms`). A token outage leaves rows
     `pending` rather than falsely marking `no_reply`.
   - Retries any distillation that failed on the `on_sent` path.
   - Prunes low-evidence lessons (soft-evicts beyond a store cap of 20) and
     deletes learned outcomes older than `retention_days` (default 90 days) to
     bound `draft_outcomes` growth.

---

### Configuration knobs (`INBOX_DRAFT_FEEDBACK_*`)

All knobs are optional — defaults shown. Set them in your Hermes `.env` or
`docker-compose.yml` environment block.

| Variable | Default | Meaning |
|---|---|---|
| `INBOX_DRAFT_FEEDBACK_ENABLED` | `true` | Enable/disable the entire loop. Set `false` to opt out without removing the plugin. |
| `INBOX_DRAFT_FEEDBACK_CAPTURE_ALL_SENT` | `true` | Capture gold-example replies on threads the plugin didn't draft (single-recipient sends only). Set `false` to record only drafted threads. |
| `INBOX_DRAFT_FEEDBACK_NO_REPLY_HOURS` | `72` | Hours after a draft is created before a non-replied thread is eligible to be marked `no_reply` (liveness-gated — see above). |
| `INBOX_DRAFT_FEEDBACK_SWEEP_INTERVAL_S` | `21600` | Seconds between sweep runs (default 6 h). |
| `INBOX_DRAFT_FEEDBACK_MAX_EXAMPLES` | `3` | Maximum gold-example replies injected into the drafting brief per correspondent. |
| `INBOX_DRAFT_FEEDBACK_MAX_LESSONS` | `8` | Maximum global do/don't lessons injected into the brief (ranked by evidence count). The store cap (20) is a separate module constant. |
| `INBOX_DRAFT_FEEDBACK_RETENTION_DAYS` | `90` | Delete `learned=1` outcome rows older than N days. Set `0` to disable retention pruning. |
| `INBOX_DRAFT_FEEDBACK_VERBATIM_THRESHOLD` | `92` | Similarity score (0–100) at or above which a sent reply is considered verbatim (no LLM, positive reinforcement only). Tune this if you edit drafts minimally before sending. |
| `INBOX_DRAFT_FEEDBACK_EDIT_THRESHOLD` | `45` | Similarity score at or above which a sent reply is `sent_edited` (LLM distil); below this → `sent_ignored` (stronger LLM distil). Tune to calibrate how aggressively the loop learns. |

---

### Owner tools — inspect and revert

The learned state is auditable and fully revertible by the owner via agent
tools.

#### `inbox_draft_feedback_status`

Read-only. Returns:
- **`outcomes`** — a histogram of all outcome types (`pending`, `sent_verbatim`,
  `sent_edited`, `sent_ignored`, `no_reply`, `sent_no_draft`) with counts.
- **`active_lessons`** — the active global do/don't rules with their `lesson_id`,
  `polarity`, `rule` text, and `evidence_count`.
- **`learned_senders`** — which correspondents have a learned voice note, with
  note length and last-updated timestamp (note text is not echoed here; use
  `inbox_get_sender_profile` to read the full note).

Optional parameter: `account_id` to scope to one mailbox.

#### `inbox_forget_lesson`

Soft-disables a global lesson by `lesson_id` (sets `active=0`). The lesson
stops influencing future drafts but is retained in the DB for reference. Use
`inbox_draft_feedback_status` to find the `lesson_id`.

Required parameter: `lesson_id` (integer).

*Owner-gated — blocked for non-owner callers.*

#### `inbox_clear_learned_notes`

Clears the learned-from-edits voice note for one correspondent. The original
backfill `voice_notes` / `tone_hints` profile is left intact. Use this to undo
a note that was distilled from a bad or adversarial email.

Required parameters: `account_id`, `sender_email`.

*Owner-gated — blocked for non-owner callers.*

---

### Data and schema

All learned state lives in `state.db` (the SQLite DB in the Hermes data
volume, default `/opt/data/inbox-organizer/state.db`):

| Table / column | Contents |
|---|---|
| `draft_outcomes` | Draft body + sent body + outcome + similarity per `(account, thread_id)`. The gold-example store. |
| `draft_lessons` | Global learned do/don't rules; `evidence_count` tracks how many deltas support each. |
| `sender_profiles.learned_notes` | Per-sender learned voice note (separate column from `voice_notes` — never overwrites the backfill layer). |
| `sender_profiles.learned_updated_ms` | Timestamp of the last learned-note update for a sender. |

This is **schema v3**. On deploy the existing `state.db` migrates in place: the
two new tables (`draft_outcomes`, `draft_lessons`) are created automatically,
and the two new columns on `sender_profiles` are added via a guarded `ALTER
TABLE`. No data loss; a v2 image against a v3 DB simply ignores the new
tables/columns.

---

### Security notes

- Every email-derived body (draft and sent) is wrapped in **randomized fences**
  before being passed to the distillation LLM, and again when injected into the
  brief. The system prompt instructs the model never to follow instructions
  inside fences.
- The learned layer is kept strictly separate from the backfill voice profile.
  Even if a distilled note is adversarial, `inbox_clear_learned_notes` removes
  it without touching the underlying profile.
- No email body is ever logged. Only outcome labels, similarity scores, thread
  ids, and counts appear in the logs.
- See [security.md](./security.md) for the broader security model.
