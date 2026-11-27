"""M01 crypto: Argon2id key derivation + AES-256-GCM. Uses audited libraries only."""
import os
import struct
from argon2.low_level import Type, hash_secret_raw
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

MAGIC = b"SSX1"
VERSION = 1
SALT_LEN, NONCE_LEN, TAG_LEN = 16, 12, 16
HEADER_LEN = 4 + 1 + SALT_LEN + NONCE_LEN + 4  # 37 bytes

class StegoError(Exception):
    """Clear, user-safe error. Never contains the password or plaintext."""
    def __init__(self, code, message):
        super().__init__(message)
        self.code, self.message = code, message

def derive_key(password: str, salt: bytes) -> bytes:
    if not password:
        raise StegoError("empty_password", "Password must not be empty.")
    return hash_secret_raw(password.encode("utf-8"), salt, time_cost=2,
                           memory_cost=19456, parallelism=1, hash_len=32, type=Type.ID)

def build_header(salt: bytes, nonce: bytes, ct_len: int, version: int = VERSION) -> bytes:
    return MAGIC + bytes([version]) + salt + nonce + struct.pack(">I", ct_len)

def encrypt(message: bytes, password: str, version: int = VERSION) -> bytes:
    """Return full payload: header(37) + ciphertext + tag(16). Header is AAD."""
    salt, nonce = os.urandom(SALT_LEN), os.urandom(NONCE_LEN)
    header = build_header(salt, nonce, len(message), version)
    ct_and_tag = AESGCM(derive_key(password, salt)).encrypt(nonce, message, header)
    return header + ct_and_tag

def payload_size(message_len: int) -> int:
    return HEADER_LEN + message_len + TAG_LEN

def parse_header(header: bytes):
    if len(header) < HEADER_LEN or header[:4] != MAGIC:
        raise StegoError("no_payload", "No valid Sublumen payload found in this image.")
    if header[4] not in (1, 2):  # 1 = sequential, 2 = keyed order
        raise StegoError("bad_version", "Unsupported payload version.")
    salt = header[5:5 + SALT_LEN]
    nonce = header[5 + SALT_LEN:5 + SALT_LEN + NONCE_LEN]
    (ct_len,) = struct.unpack(">I", header[-4:])
    return salt, nonce, ct_len

def permutation_seed(password: str, salt: bytes) -> int:
    import hashlib
    return int.from_bytes(hashlib.sha256(b'ssx-perm' + derive_key(password, salt)).digest()[:8], 'big')

def decrypt(header: bytes, body: bytes, password: str) -> bytes:
    salt, nonce, _ = parse_header(header)
    try:
        return AESGCM(derive_key(password, salt)).decrypt(nonce, body, header)
    except InvalidTag:
        raise StegoError("auth_failed",
            "Wrong password, or the image was modified/compressed (GCM tag check failed).")
