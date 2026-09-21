import unittest

from auth import PASSWORD_MIN_LENGTH, hash_password, verify_password


class PasswordHashTests(unittest.TestCase):
    def test_roundtrip(self):
        stored = hash_password("secret-1")
        self.assertTrue(verify_password("secret-1", stored))
        self.assertFalse(verify_password("secret-2", stored))

    def test_rejects_short_password(self):
        with self.assertRaises(ValueError):
            hash_password("123")

    def test_empty_hash_is_not_valid(self):
        self.assertFalse(verify_password("secret-1", ""))
        self.assertFalse(verify_password("secret-1", "not-a-hash"))

    def test_min_length_constant(self):
        self.assertEqual(PASSWORD_MIN_LENGTH, 4)


if __name__ == "__main__":
    unittest.main()
