"""Zero-dependency authenticated keystream encryption module (ADR-003, ADR-010).

Provides RFC 7539 compliant ChaCha20 keystream encryption combined with HMAC-SHA256
in an Encrypt-then-MAC construction, using only the Python 3 standard library
(struct, hmac, hashlib, os, secrets).

Used for protecting copyrighted translations, secure offline data packs,
and user encryption keys without external pip/C dependencies.
"""

import hashlib
import hmac
import secrets
import struct
from typing import Optional, Tuple

MAGIC_HEADER = b"BIBLE_PACK_V1" + bytes([0])
KEY_SIZE = 32  # 256 bits
NONCE_SIZE = 12  # 96 bits for RFC 7539 ChaCha20
SALT_SIZE = 16  # 128 bits for PBKDF2
TAG_SIZE = 32  # HMAC-SHA256 digest size
DEFAULT_PBKDF2_ITERATIONS = 100_000


class CryptoError(Exception):
    """Base exception for cryptographic failures (corrupted data, MAC failure, etc.)."""
    pass


def _rotl32(v: int, c: int) -> int:
    """Rotate 32-bit unsigned int v left by c bits."""
    return ((v << c) & 0xFFFFFFFF) | (v >> (32 - c))


class ChaCha20:
    """Pure Python RFC 7539 ChaCha20 stream cipher (Zero External Dependencies).

    Generates 64-byte blocks of pseudorandom keystream XORed with plaintext.
    """

    def __init__(self, key: bytes, nonce: bytes, counter: int = 1):
        if len(key) != KEY_SIZE:
            raise ValueError(f"ChaCha20 key must be {KEY_SIZE} bytes, got {len(key)}")
        if len(nonce) != NONCE_SIZE:
            raise ValueError(f"ChaCha20 nonce must be {NONCE_SIZE} bytes, got {len(nonce)}")

        self.key = key
        self.nonce = nonce
        self.counter = counter

    @staticmethod
    def _quarter_round(state: list, a: int, b: int, c: int, d: int) -> None:
        state[a] = (state[a] + state[b]) & 0xFFFFFFFF
        state[d] = _rotl32(state[d] ^ state[a], 16)

        state[c] = (state[c] + state[d]) & 0xFFFFFFFF
        state[b] = _rotl32(state[b] ^ state[c], 12)

        state[a] = (state[a] + state[b]) & 0xFFFFFFFF
        state[d] = _rotl32(state[d] ^ state[a], 8)

        state[c] = (state[c] + state[d]) & 0xFFFFFFFF
        state[b] = _rotl32(state[b] ^ state[c], 7)

    def _block(self, counter: int) -> bytes:
        # RFC 7539 constants: "expand 32-byte k"
        constants = (0x61707865, 0x3320646e, 0x79622d32, 0x6b206574)
        k = struct.unpack("<8I", self.key)
        n = struct.unpack("<3I", self.nonce)

        state = [
            constants[0], constants[1], constants[2], constants[3],
            k[0], k[1], k[2], k[3],
            k[4], k[5], k[6], k[7],
            counter & 0xFFFFFFFF, n[0], n[1], n[2],
        ]

        working = list(state)
        # 20 rounds = 10 double rounds
        for _ in range(10):
            # Column rounds
            self._quarter_round(working, 0, 4, 8, 12)
            self._quarter_round(working, 1, 5, 9, 13)
            self._quarter_round(working, 2, 6, 10, 14)
            self._quarter_round(working, 3, 7, 11, 15)
            # Diagonal rounds
            self._quarter_round(working, 0, 5, 10, 15)
            self._quarter_round(working, 1, 6, 11, 12)
            self._quarter_round(working, 2, 7, 8, 13)
            self._quarter_round(working, 3, 4, 9, 14)

        out = [(working[i] + state[i]) & 0xFFFFFFFF for i in range(16)]
        return struct.pack("<16I", *out)

    def crypt(self, data: bytes) -> bytes:
        """Encrypts or decrypts bytes by XORing with consecutive ChaCha20 blocks."""
        out = bytearray(len(data))
        block_count = (len(data) + 63) // 64
        current_counter = self.counter

        for i in range(block_count):
            keystream = self._block(current_counter + i)
            start = i * 64
            end = min(start + 64, len(data))
            chunk_len = end - start
            for j in range(chunk_len):
                out[start + j] = data[start + j] ^ keystream[j]

        return bytes(out)


def keystream_xor(data: bytes, key: bytes, nonce: bytes, counter: int = 1) -> bytes:
    """Convenience function to XOR data with ChaCha20 keystream."""
    cipher = ChaCha20(key, nonce, counter=counter)
    return cipher.crypt(data)


def generate_key() -> bytes:
    """Generates a cryptographically secure 256-bit (32 byte) random key."""
    return secrets.token_bytes(KEY_SIZE)


def derive_key(password: str, salt: bytes, iterations: int = DEFAULT_PBKDF2_ITERATIONS) -> bytes:
    """Derives a 256-bit encryption key from a password string using PBKDF2-HMAC-SHA256."""
    return hashlib.pbkdf2_hmac(
        hash_name="sha256",
        password=password.encode("utf-8"),
        salt=salt,
        iterations=iterations,
        dklen=KEY_SIZE,
    )


def _split_keys(master_key: bytes) -> Tuple[bytes, bytes]:
    """Derives independent encryption and MAC keys from a master key using HKDF-Expand with SHA256."""
    enc_key = hmac.new(master_key, b"BIBLE_ENC_KEY_V1", hashlib.sha256).digest()
    mac_key = hmac.new(master_key, b"BIBLE_MAC_KEY_V1", hashlib.sha256).digest()
    return enc_key, mac_key


def encrypt_bytes(data: bytes, master_key: bytes, salt: Optional[bytes] = None, iterations: int = 0) -> bytes:
    """Encrypts raw bytes using ChaCha20 + HMAC-SHA256 authenticated encryption.

    Wire format:
      [MAGIC_HEADER: 14 bytes]
      [iterations: 4 bytes big-endian unsigned int]
      [salt: 16 bytes]
      [nonce: 12 bytes]
      [hmac_tag: 32 bytes]
      [ciphertext: N bytes]
    """
    if len(master_key) != KEY_SIZE:
        raise ValueError(f"Master key must be {KEY_SIZE} bytes, got {len(master_key)}")

    effective_salt = salt if salt is not None else secrets.token_bytes(SALT_SIZE)
    nonce = secrets.token_bytes(NONCE_SIZE)
    enc_key, mac_key = _split_keys(master_key)

    cipher = ChaCha20(enc_key, nonce, counter=1)
    ciphertext = cipher.crypt(data)

    header = MAGIC_HEADER + struct.pack(">I", iterations) + effective_salt + nonce
    mac_tag = hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()

    return header + mac_tag + ciphertext


def decrypt_bytes(payload: bytes, master_key: bytes) -> bytes:
    """Decrypts and authenticates a Bible pack payload using ChaCha20 + HMAC-SHA256."""
    min_len = len(MAGIC_HEADER) + 4 + SALT_SIZE + NONCE_SIZE + TAG_SIZE
    if len(payload) < min_len:
        raise CryptoError(f"Payload too short: {len(payload)} bytes (minimum {min_len})")

    if not payload.startswith(MAGIC_HEADER):
        raise CryptoError("Invalid magic header: not a valid Bible encryption pack")

    offset = len(MAGIC_HEADER)
    iterations = struct.unpack(">I", payload[offset:offset + 4])[0]
    offset += 4

    salt = payload[offset:offset + SALT_SIZE]
    offset += SALT_SIZE

    nonce = payload[offset:offset + NONCE_SIZE]
    offset += NONCE_SIZE

    mac_tag = payload[offset:offset + TAG_SIZE]
    offset += TAG_SIZE

    ciphertext = payload[offset:]

    enc_key, mac_key = _split_keys(master_key)

    header = payload[:len(MAGIC_HEADER) + 4 + SALT_SIZE + NONCE_SIZE]
    expected_tag = hmac.new(mac_key, header + ciphertext, hashlib.sha256).digest()

    if not hmac.compare_digest(mac_tag, expected_tag):
        raise CryptoError("MAC verification failed: data is corrupted or decryption key is incorrect")

    cipher = ChaCha20(enc_key, nonce, counter=1)
    return cipher.crypt(ciphertext)


def encrypt_string(text: str, password: str, iterations: int = DEFAULT_PBKDF2_ITERATIONS) -> bytes:
    """Encrypts a plaintext string with a password/passphrase using PBKDF2 + ChaCha20 + HMAC."""
    salt = secrets.token_bytes(SALT_SIZE)
    derived_key = derive_key(password, salt=salt, iterations=iterations)
    return encrypt_bytes(text.encode("utf-8"), derived_key, salt=salt, iterations=iterations)


def decrypt_string(payload: bytes, password: str) -> str:
    """Decrypts an authenticated payload with a password/passphrase."""
    min_len = len(MAGIC_HEADER) + 4 + SALT_SIZE + NONCE_SIZE + TAG_SIZE
    if len(payload) < min_len:
        raise CryptoError("Payload too short")

    offset = len(MAGIC_HEADER)
    iterations = struct.unpack(">I", payload[offset:offset + 4])[0]
    offset += 4
    salt = payload[offset:offset + SALT_SIZE]

    iter_count = iterations if iterations > 0 else DEFAULT_PBKDF2_ITERATIONS
    derived_key = derive_key(password, salt=salt, iterations=iter_count)

    decrypted_bytes = decrypt_bytes(payload, derived_key)
    return decrypted_bytes.decode("utf-8")


def encrypt_text_pack(source_file: str, target_file: str, password: str, iterations: int = DEFAULT_PBKDF2_ITERATIONS) -> None:
    """Encrypts a text/CSV/JSON corpus file into a sovereign offline encrypted Bible pack (.bpack)."""
    with open(source_file, "rb") as f:
        data = f.read()

    salt = secrets.token_bytes(SALT_SIZE)
    derived_key = derive_key(password, salt=salt, iterations=iterations)
    encrypted = encrypt_bytes(data, derived_key, salt=salt, iterations=iterations)

    with open(target_file, "wb") as f:
        f.write(encrypted)


def decrypt_text_pack(source_file: str, target_file: str, password: str) -> None:
    """Decrypts an offline encrypted Bible pack (.bpack) back to plaintext file."""
    with open(source_file, "rb") as f:
        payload = f.read()

    min_len = len(MAGIC_HEADER) + 4 + SALT_SIZE + NONCE_SIZE + TAG_SIZE
    if len(payload) < min_len:
        raise CryptoError("Payload too short")

    offset = len(MAGIC_HEADER)
    iterations = struct.unpack(">I", payload[offset:offset + 4])[0]
    offset += 4
    salt = payload[offset:offset + SALT_SIZE]

    iter_count = iterations if iterations > 0 else DEFAULT_PBKDF2_ITERATIONS
    derived_key = derive_key(password, salt=salt, iterations=iter_count)

    decrypted = decrypt_bytes(payload, derived_key)
    with open(target_file, "wb") as f:
        f.write(decrypted)
