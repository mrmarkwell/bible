"""Hermetic unit tests for core/crypto.py (Zero External Dependencies)."""

import os
import tempfile
import unittest
from core.crypto import (
    MAGIC_HEADER,
    ChaCha20,
    CryptoError,
    decrypt_bytes,
    decrypt_string,
    decrypt_text_pack,
    derive_key,
    encrypt_bytes,
    encrypt_string,
    encrypt_text_pack,
    generate_key,
)


class TestChaCha20Keystream(unittest.TestCase):
    """Test pure-Python ChaCha20 implementation against RFC 7539 test vectors."""

    def test_rfc7539_section_2_3_2_block_vector(self):
        """Verify against RFC 7539 section 2.3.2 test vector.

        Key: 00:01:02:...:1f
        Nonce: 00:00:00:09:00:00:00:4a:00:00:00:00
        Block Count: 1
        """
        key = bytes(range(32))
        nonce = bytes([0, 0, 0, 0x09, 0, 0, 0, 0x4a, 0, 0, 0, 0])
        counter = 1
        cipher = ChaCha20(key, nonce, counter=counter)
        block = cipher._block(counter)

        # RFC 7539 section 2.3.2 serialized block:
        expected_hex = (
            "10f1e7e4d13b5915500fdd1fa32071c4"
            "c7d1f4c733c068030422aa9ac3d46c4e"
            "d2826446079faa0914c2d705d98b02a2"
            "b5129cd1de164eb9cbd083e8a2503c4e"
        )
        self.assertEqual(block.hex(), expected_hex)

    def test_rfc7539_section_2_4_2_encryption_vector(self):
        """Verify against RFC 7539 section 2.4.2 Sunscreen encryption test vector."""
        key = bytes(range(32))
        nonce = bytes([0, 0, 0, 0, 0, 0, 0, 0x4a, 0, 0, 0, 0])
        counter = 1
        plaintext = (
            b"Ladies and Gentlemen of the class of '99: "
            b"If I could offer you only one tip for the future, "
            b"sunscreen would be it."
        )

        cipher = ChaCha20(key, nonce, counter=counter)
        ciphertext = cipher.crypt(plaintext)

        # RFC 7539 section 2.4.2 Ciphertext Sunscreen:
        expected_ciphertext_hex = (
            "6e2e359a2568f98041ba0728dd0d6981"
            "e97e7aec1d4360c20a27afccfd9fae0b"
            "f91b65c5524733ab8f593dabcd62b357"
            "1639d624e65152ab8f530c359f0861d8"
            "07ca0dbf500d6a6156a38e088a22b65e"
            "52bc514d16ccf806818ce91ab7793736"
            "5af90bbf74a35be6b40b8eedf2785e42"
            "874d"
        )
        self.assertEqual(ciphertext.hex(), expected_ciphertext_hex)

        # Roundtrip decrypt with fresh cipher
        decipher = ChaCha20(key, nonce, counter=counter)
        self.assertEqual(decipher.crypt(ciphertext), plaintext)


class TestKeyDerivation(unittest.TestCase):
    """Test PBKDF2 key derivation and random key generation."""

    def test_generate_key(self):
        k1 = generate_key()
        k2 = generate_key()
        self.assertEqual(len(k1), 32)
        self.assertEqual(len(k2), 32)
        self.assertNotEqual(k1, k2)

    def test_derive_key_deterministic(self):
        salt = b"test_salt_16byte"
        k1 = derive_key("my-secret-passphrase", salt=salt, iterations=1000)
        k2 = derive_key("my-secret-passphrase", salt=salt, iterations=1000)
        self.assertEqual(k1, k2)
        self.assertEqual(len(k1), 32)

    def test_derive_key_different_passwords(self):
        salt = b"test_salt_16byte"
        k1 = derive_key("passwordA", salt=salt, iterations=1000)
        k2 = derive_key("passwordB", salt=salt, iterations=1000)
        self.assertNotEqual(k1, k2)

    def test_derive_key_different_salts(self):
        k1 = derive_key("password", salt=b"salt111111111111", iterations=1000)
        k2 = derive_key("password", salt=b"salt222222222222", iterations=1000)
        self.assertNotEqual(k1, k2)


class TestAuthenticatedEncryptionRoundtrip(unittest.TestCase):
    """Test encrypt/decrypt bytes, strings, and tamper detection."""

    def test_encrypt_decrypt_bytes_roundtrip(self):
        key = generate_key()
        original = b"For God so loved the world, that he gave his one and only Son."
        encrypted = encrypt_bytes(original, key)

        self.assertTrue(encrypted.startswith(MAGIC_HEADER))
        self.assertNotEqual(encrypted, original)

        decrypted = decrypt_bytes(encrypted, key)
        self.assertEqual(decrypted, original)

    def test_encrypt_decrypt_string_roundtrip(self):
        password = "bible-engine-test-key-2026"
        original = "In the beginning was the Word, and the Word was with God, and the Word was God."
        encrypted = encrypt_string(original, password, iterations=1000)

        self.assertTrue(encrypted.startswith(MAGIC_HEADER))

        decrypted = decrypt_string(encrypted, password)
        self.assertEqual(decrypted, original)

    def test_wrong_password_fails_mac_verification(self):
        original = "Trust in the Lord with all your heart."
        encrypted = encrypt_string(original, "correct-password", iterations=1000)

        with self.assertRaises(CryptoError) as ctx:
            decrypt_string(encrypted, "wrong-password")
        self.assertIn("MAC verification failed", str(ctx.exception))

    def test_tampered_ciphertext_fails_mac_verification(self):
        key = generate_key()
        original = b"The Lord is my shepherd; I shall not want."
        encrypted = bytearray(encrypt_bytes(original, key))

        # Tamper with one byte in the payload
        encrypted[-1] ^= 0x01

        with self.assertRaises(CryptoError) as ctx:
            decrypt_bytes(bytes(encrypted), key)
        self.assertIn("MAC verification failed", str(ctx.exception))

    def test_invalid_magic_header(self):
        corrupted = b"BOGUS_HEADER" + bytes(80)
        with self.assertRaises(CryptoError) as ctx:
            decrypt_bytes(corrupted, b"A" * 32)
        self.assertIn("Invalid magic header", str(ctx.exception))

    def test_truncated_payload(self):
        short = MAGIC_HEADER + bytes(10)
        with self.assertRaises(CryptoError) as ctx:
            decrypt_bytes(short, b"A" * 32)
        self.assertIn("Payload too short", str(ctx.exception))

    def test_empty_string_roundtrip(self):
        empty = ""
        encrypted = encrypt_string(empty, "password", iterations=1000)
        decrypted = decrypt_string(encrypted, "password")
        self.assertEqual(decrypted, empty)

    def test_unicode_text_roundtrip(self):
        text = "Ἐν ἀρχῇ ἦν ὁ λόγος / בְּרֵאשִׁית בָּרָא אֱלֹהִים / ✝️ 🕊️ 📖"
        encrypted = encrypt_string(text, "greek-hebrew-key", iterations=1000)
        decrypted = decrypt_string(encrypted, "greek-hebrew-key")
        self.assertEqual(decrypted, text)


class TestTextPackFileOperations(unittest.TestCase):
    """Test text pack bundle encryption and decryption on filesystem."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.test_dir = self.tmpdir.name
        self.plain_path = os.path.join(self.test_dir, "sample.txt")
        self.enc_path = os.path.join(self.test_dir, "sample.bpack")
        self.dec_path = os.path.join(self.test_dir, "sample_dec.txt")

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_file_pack_roundtrip(self):
        sample_corpus = (
            "Book,Chapter,Verse,Text\n"
            "JHN,1,1,\"In the beginning was the Word, and the Word was with God, and the Word was God.\"\n"
            "JHN,1,2,\"He was in the beginning with God.\"\n"
            "JHN,1,3,\"All things were made through him, and without him was not any thing made that was made.\"\n"
        )
        with open(self.plain_path, "w", encoding="utf-8") as f:
            f.write(sample_corpus)

        password = "esv-licensed-passphrase-2026"
        encrypt_text_pack(self.plain_path, self.enc_path, password, iterations=1000)

        self.assertTrue(os.path.exists(self.enc_path))
        with open(self.enc_path, "rb") as f:
            header = f.read(len(MAGIC_HEADER))
            self.assertEqual(header, MAGIC_HEADER)

        decrypt_text_pack(self.enc_path, self.dec_path, password)
        with open(self.dec_path, "r", encoding="utf-8") as f:
            restored = f.read()

        self.assertEqual(restored, sample_corpus)


if __name__ == "__main__":
    unittest.main()
