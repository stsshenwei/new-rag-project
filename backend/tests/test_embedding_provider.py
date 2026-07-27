import unittest
from types import SimpleNamespace

from app.services.embedding_provider import OpenAIEmbeddingProvider


class FakeEmbeddings:
    def create(self, model, input):
        if isinstance(input, str):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0, 2.0])])
        return SimpleNamespace(data=[SimpleNamespace(embedding=[float(i), 2.0]) for i, _ in enumerate(input)])


class FakeClient:
    embeddings = FakeEmbeddings()


class EmbeddingProviderTests(unittest.TestCase):
    def test_embed_text_uses_configured_client(self):
        provider = OpenAIEmbeddingProvider(client=FakeClient(), model="test-model")
        self.assertEqual([1.0, 2.0], provider.embed_text("hello"))

    def test_embed_batch_returns_vectors_in_order(self):
        provider = OpenAIEmbeddingProvider(client=FakeClient(), model="test-model")
        self.assertEqual([[0.0, 2.0], [1.0, 2.0]], provider.embed_batch(["a", "b"]))


if __name__ == "__main__":
    unittest.main()
