import unittest

from app.auth.mongo import ensure_optional_unique_identity_index


class FakeCollection:
    def __init__(self, indexes=None):
        self._indexes = indexes or {
            "_id_": {"key": [("_id", 1)]},
        }
        self.dropped_indexes = []
        self.created_indexes = []

    def index_information(self):
        return dict(self._indexes)

    def drop_index(self, name):
        self.dropped_indexes.append(name)
        self._indexes.pop(name, None)

    def create_index(self, keys, **kwargs):
        index_name = kwargs.get("name") or "_".join(f"{field}_{direction}" for field, direction in keys)
        self.created_indexes.append((keys, kwargs))
        self._indexes[index_name] = {
            "key": list(keys),
            **kwargs,
        }
        return index_name


class AuthMongoIndexTests(unittest.TestCase):
    def test_recreates_legacy_non_sparse_optional_identity_index(self):
        collection = FakeCollection(
            indexes={
                "_id_": {"key": [("_id", 1)]},
                "telegram_id_1": {
                    "key": [("telegram_id", 1)],
                    "unique": True,
                },
            }
        )

        ensure_optional_unique_identity_index(collection, "telegram_id")

        self.assertEqual(collection.dropped_indexes, ["telegram_id_1"])
        self.assertEqual(len(collection.created_indexes), 1)
        keys, kwargs = collection.created_indexes[0]
        self.assertEqual(keys, [("telegram_id", 1)])
        self.assertTrue(kwargs["unique"])
        self.assertTrue(kwargs["sparse"])

    def test_keeps_existing_compatible_optional_identity_index(self):
        collection = FakeCollection(
            indexes={
                "_id_": {"key": [("_id", 1)]},
                "google_id_1": {
                    "key": [("google_id", 1)],
                    "unique": True,
                    "sparse": True,
                },
            }
        )

        ensure_optional_unique_identity_index(collection, "google_id")

        self.assertEqual(collection.dropped_indexes, [])
        self.assertEqual(collection.created_indexes, [])


if __name__ == "__main__":
    unittest.main()
