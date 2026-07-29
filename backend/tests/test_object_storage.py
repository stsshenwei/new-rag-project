import tempfile
import unittest
from pathlib import Path

from app.services.documents.object_storage import LocalObjectStorage


class LocalObjectStorageTests(unittest.TestCase):
    def test_put_read_delete(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalObjectStorage(tmp)
            key = store.put(b"image", suffix="jpg", prefix="kb/images")
            self.assertTrue(store.exists(key))
            self.assertEqual(b"image", store.read(key))
            store.delete(key)
            self.assertFalse(store.exists(key))

    def test_traversal_and_absolute_keys_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = LocalObjectStorage(tmp)
            for key in ("../secret", str(Path(tmp).resolve() / "absolute")):
                with self.assertRaises(ValueError):
                    store.read(key)
                with self.assertRaises(ValueError):
                    store.exists(key)
                with self.assertRaises(ValueError):
                    store.delete(key)

    def test_size_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                LocalObjectStorage(tmp, max_object_bytes=2).put(b"123")


if __name__ == "__main__":
    unittest.main()
