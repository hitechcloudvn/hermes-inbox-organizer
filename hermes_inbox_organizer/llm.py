"""VI: Client LLM tương thích OpenAI tối giản cho phân loại (lối đi cục bộ rẻ tiền).

Mặc định dùng OpenRouter nhưng hoạt động với **bất kỳ endpoint tương thích
OpenAI nào**: đặt ``INBOX_CLASSIFIER_BASE_URL`` và ``INBOX_CLASSIFIER_API_KEY``
(khóa dự phòng ``OPENROUTER_API_KEY`` để tương thích ngược). Model mặc định là
một model nhỏ, rẻ, làm theo chỉ dẫn và có thể ghi đè qua
``INBOX_CLASSIFIER_MODEL``. Cả ba được phân giải qua :mod:`.config`. SDK
``openai`` được import lười (lazy) để gói vẫn tải được khi thiếu nó.

EN: Minimal OpenAI-compatible LLM client for classification (the cheap local path).

Defaults to OpenRouter but works with **any OpenAI-compatible endpoint**: set
``INBOX_CLASSIFIER_BASE_URL`` and ``INBOX_CLASSIFIER_API_KEY`` (the key falls back
to ``OPENROUTER_API_KEY`` for back-compat). The model defaults to a small, cheap,
instruction-following model and is overridable via ``INBOX_CLASSIFIER_MODEL``.
All three resolve through :mod:`.config`. The ``openai`` SDK is imported lazily so
the package loads without it.
"""

from __future__ import annotations

import json

from .config import get_config


def _client():
    """Build an OpenAI client for the configured (OpenAI-compatible) endpoint."""
    from openai import OpenAI

    cfg = get_config()
    if not cfg.classifier_api_key:
        raise RuntimeError(
            "no classifier API key — set INBOX_CLASSIFIER_API_KEY (or OPENROUTER_API_KEY)"
        )
    return OpenAI(api_key=cfg.classifier_api_key, base_url=cfg.classifier_base_url)


def classify_json(system: str, user: str, *, model: str | None = None) -> dict:
    """VI: Gọi model với định dạng phản hồi JSON-object; trả về dict đã phân tích cú pháp.

    EN: Call the model with a JSON-object response format; return the parsed dict.
    """
    resp = _client().chat.completions.create(
        model=model or get_config().classifier_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        response_format={"type": "json_object"},
        temperature=0,
    )
    return json.loads(resp.choices[0].message.content or "{}")


def summarize(system: str, user: str, *, model: str | None = None) -> str:
    """VI: Hoàn tất văn bản thuần (giống :func:`classify_json` nhưng trả về chuỗi gốc).

    Được dùng bởi backfill hồ sơ người gửi để chắt lọc giọng văn của chủ hộp thư
    từ chính văn bản họ đã gửi. Nhiệt độ 0 để đầu ra ổn định, súc tích.

    EN: Plain-text completion (mirrors :func:`classify_json` but returns the raw string).

    Used by the sender-profile backfill to distil the owner's voice from their own
    sent prose. Temperature 0 for stable, terse output.
    """
    resp = _client().chat.completions.create(
        model=model or get_config().classifier_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    return (resp.choices[0].message.content or "").strip()
