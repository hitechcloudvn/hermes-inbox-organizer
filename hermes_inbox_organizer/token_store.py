"""VI: Kho lưu token OAuth mã hóa theo từng tài khoản.

Một blob JSON mã hóa AES-GCM cho mỗi tài khoản đã kết nối, ghi với quyền 0600.
Blob chứa refresh token + client id/secret + token_uri + scopes — đủ để plugin
tự tạo access token mới (Credentials tự động làm mới).

EN: Encrypted per-account OAuth token storage.

One AES-GCM-encrypted JSON blob per connected account, written with 0600 perms.
The blob holds the refresh token + client id/secret + token_uri + scopes — enough
for the plugin to mint fresh access tokens (Credentials auto-refresh).
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass

from . import crypto


@dataclass
class AccountToken:
    """VI: Dữ liệu token OAuth của một tài khoản đã kết nối.

    EN: OAuth token material for one connected account.
    """
    email: str
    refresh_token: str
    client_id: str
    client_secret: str
    token_uri: str
    scopes: list[str]


def save_token(tok: AccountToken, key_hex: str, path: str) -> None:
    """VI: Mã hóa và ghi token ra tệp với quyền 0600.

    EN: Encrypt and write the token to a file with 0600 permissions.
    """
    os.makedirs(os.path.dirname(path), exist_ok=True)
    blob = crypto.encrypt(json.dumps(asdict(tok)), key_hex)
    with open(path, "w") as f:
        f.write(blob)
    os.chmod(path, 0o600)


def load_token(key_hex: str, path: str) -> AccountToken:
    """VI: Đọc và giải mã token từ tệp đã lưu.

    EN: Read and decrypt the token from the saved file.
    """
    with open(path) as f:
        blob = f.read()
    return AccountToken(**json.loads(crypto.decrypt(blob, key_hex)))
