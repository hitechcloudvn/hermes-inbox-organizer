"""VI: Mã hóa AES-256-GCM cho token OAuth khi lưu trữ.

Khóa gồm 32 byte (64 ký tự hex). Trong container đã triển khai, plugin đọc khóa
từ một tệp trong thư mục cấu hình do root sở hữu và gắn chỉ-đọc; luồng kết nối
phía laptop dùng chính khóa đó để mã hóa trước khi blob token được chuyển về máy
chủ (token-import, đường dẫn an toàn cho headless). Định dạng blob:
base64(nonce[12] || ciphertext+tag).

Việc xoay ``key_id`` chưa được triển khai. ``cryptography`` được import lười
(lazy) để gói vẫn import được cả ở nơi chưa cài thư viện này.

EN: AES-256-GCM encryption for OAuth tokens at rest.

Key is 32 bytes (64 hex chars). In the deployed container the plugin reads the
key from a file in the root-owned, read-only-mounted config dir; the laptop-side
connect flow uses the same key to encrypt before the token blob is shipped to the
host (token-import, the headless-safe path). Blob format:
base64(nonce[12] || ciphertext+tag).

``key_id`` rotation is not yet implemented. ``cryptography`` is imported lazily so
the package imports even where the lib isn't installed.
"""

from __future__ import annotations

import base64
import os

_NONCE_LEN = 12


def _key_bytes(key_hex: str) -> bytes:
    b = bytes.fromhex(key_hex.strip())
    if len(b) != 32:
        raise ValueError("encryption key must be 32 bytes (64 hex chars)")
    return b


def generate_key() -> str:
    """VI: Tạo một khóa AES-256 mới và trả về dạng hex.

    EN: Generate a fresh 32-byte AES-256 key and return it as hex.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    return AESGCM.generate_key(bit_length=256).hex()


def encrypt(plaintext: str, key_hex: str) -> str:
    """VI: Mã hóa chuỗi bằng AES-256-GCM và trả về blob base64(nonce || bản mã + tag).

    EN: Encrypt a string with AES-256-GCM and return base64(nonce || ciphertext+tag).
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    nonce = os.urandom(_NONCE_LEN)
    ct = AESGCM(_key_bytes(key_hex)).encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()


def decrypt(blob_b64: str, key_hex: str) -> str:
    """VI: Giải mã blob base64 mà ``encrypt`` tạo ra và trả về chuỗi gốc.

    EN: Decrypt the base64 blob produced by ``encrypt`` and return the plaintext.
    """
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    raw = base64.b64decode(blob_b64)
    nonce, ct = raw[:_NONCE_LEN], raw[_NONCE_LEN:]
    return AESGCM(_key_bytes(key_hex)).decrypt(nonce, ct, None).decode()
