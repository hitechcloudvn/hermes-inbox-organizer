#!/usr/bin/env python3
"""Tao GitLab Release qua Releases API / Create the GitLab Release via the Releases API.

Vi sao khong dung keyword `release:` cua GitLab CI / Why not the `release:` keyword:

1. gitlab-runner 19.6+ (SaaS) sinh buoc "step_release" dang
   `if command -v glab; then glab ...; else release-cli ...` — runner doi mot
   trong hai binary co SAN trong image chay job; image nho (python alpine)
   thuong khong co ca hai => exit 127. (Da gap thuc te o repo
   cloud-hermes-management, pipeline tag v0.1.0.)
   / gitlab-runner 19.6+ (SaaS) generates a release step of the form
   `if command -v glab; then glab ...; else release-cli ...` — the runner
   expects one of those binaries INSIDE the job image; slim images have
   neither => exit 127. (Hit live on cloud-hermes-management's v0.1.0 tag.)

2. Buoc do embed mo ta markdown vao script shell — cac backtick trong mo ta
   bi bash hieu la command substitution va duoc THUC THI.
   / That step embeds the markdown description into shell script code —
   backticks in the description are executed by bash as command substitution.

Goi Releases API truc tiep bang CI_JOB_TOKEN (header JOB-TOKEN) la duong dan
on dinh, khong phu thuoc release-cli/glab hoac ki tu dac biet trong mo ta.
/ Calling the Releases API directly with CI_JOB_TOKEN (JOB-TOKEN header) is
stable, independent of release-cli/glab and of special characters in the notes.

Chi dung stdlib — khong can package nao them / stdlib only — no extra packages.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import urllib.error
import urllib.request

# Mo ta release song ngu / bilingual release notes
NOTES = """\
## Tiếng Việt

**hermes-inbox-organizer** — phân loại Gmail tự động dạng plugin Hermes chạy trong tiến trình:
sắp xếp, gắn nhãn, lưu trữ thư và soạn bản nháp trả lời bằng giọng của bạn, tự lưu trữ,
không qua SaaS bên thứ ba.

- Daemon Pub/Sub streaming-pull phân loại + gắn nhãn thư mới (8 nhãn đánh số kiểu Fyxer)
- Phân loại lai pre-classifier + LLM dự phòng; Hermes soạn bản nháp cho `1: To Respond`
- Plugin kiểu pip/entry-point (`hermes_agent.plugins`) — Python 3.11+, bản `0.2.1`,
  token OAuth mã hoá AES-256-GCM khi lưu trữ

Cài đặt:

```bash
git clone https://github.com/hitechcloudvn/hermes-inbox-organizer.git
pip install "./hermes-inbox-organizer[live]"
hermes plugins enable inbox_organizer
hermes-inbox-organizer setup
```

Xem README + `HERMES_SELF_INSTALL.md` để thiết lập Google Cloud (OAuth + Pub/Sub) và cấu hình.
Plugin cài bằng `pip`, KHÔNG bằng `hermes plugins install`.

## English

**hermes-inbox-organizer** — autonomous Gmail triage as an in-process Hermes plugin: it sorts,
labels, and archives your mail and drafts replies in your voice, self-hosted, with no
third-party SaaS in the path of your inbox.

- Pub/Sub streaming-pull daemon classifying + labeling new mail (8 Fyxer-style numbered labels)
- Hybrid pre-classifier + fallback LLM; Hermes drafts replies for `1: To Respond`
- Pip/entry-point plugin (`hermes_agent.plugins`) — Python 3.11+, version `0.2.1`,
  OAuth tokens encrypted AES-256-GCM at rest

Install:

```bash
git clone https://github.com/hitechcloudvn/hermes-inbox-organizer.git
pip install "./hermes-inbox-organizer[live]"
hermes plugins enable inbox_organizer
hermes-inbox-organizer setup
```

See the README + `HERMES_SELF_INSTALL.md` for the one-time Google Cloud setup (OAuth + Pub/Sub)
and configuration. Install with `pip` — NOT with `hermes plugins install`.
"""


def api_call(method: str, url: str, token: str, payload: dict | None = None):
    """Moi goi API luon tra ve (status, body) — khong nem loi / never raises."""
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "JOB-TOKEN": token,
            "Content-Type": "application/json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", "replace")
            return resp.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "replace")
        try:
            parsed = json.loads(body) if body else {}
        except json.JSONDecodeError:
            parsed = {"raw": body}
        return e.code, parsed


def save_response(status: int, body: object) -> None:
    with open("release-response.json", "w", encoding="utf-8") as fh:
        json.dump({"http_status": status, "body": body}, fh, ensure_ascii=False, indent=2)


def main() -> int:
    if "--print" in sys.argv:
        # Che do kiem tra payload cuc bo / local payload inspection mode
        tag = os.environ.get("CI_COMMIT_TAG", "v0.0.0-print")
        print(json.dumps({"name": tag, "tag_name": tag, "description": NOTES},
                         ensure_ascii=False, indent=2))
        return 0

    api_v4 = os.environ["CI_API_V4_URL"]
    project_id = os.environ["CI_PROJECT_ID"]
    tag = os.environ["CI_COMMIT_TAG"]
    token = os.environ["CI_JOB_TOKEN"]

    payload = {"name": tag, "tag_name": tag, "description": NOTES}

    print(f"Creating GitLab release for tag {tag}")
    url = f"{api_v4}/projects/{project_id}/releases"
    status, body = api_call("POST", url, token, payload)

    # Release da ton tai (vi du chay lai pipeline) — cap nhat lai / already
    # exists (pipeline re-run): update in place instead of failing the job.
    if status in (409, 422):
        print(f"Release already exists (HTTP {status}) — updating via PUT")
        status, body = api_call("PUT", f"{url}/{tag}", token, payload)

    save_response(status, body)
    if 200 <= status < 300:
        print(f"Release created/updated: {body.get('_links', {}).get('self', url)}")
        return 0

    print(f"ERROR: release API returned HTTP {status}", file=sys.stderr)
    print(json.dumps(body, ensure_ascii=False, indent=2), file=sys.stderr)
    return 1


if __name__ == "__main__":
    # Dam bao stdout/stderr la UTF-8 ke ca khi locale la POSIX/ASCII (Docker)
    # / force UTF-8 stdout/stderr even under POSIX/ASCII locales (Docker)
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError):
            stream.reconfigure(encoding="utf-8")
    sys.exit(main())
