"""Tests for evaluate_digest(). Run with: uv run python -m unittest test_eval.py

Mocks the Claude client and the embedding model so this runs offline,
instantly, and free — no real API calls or model downloads.
"""
import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from main import evaluate_digest


def make_digest(headline="today, something happened", tldr=None, categories=None):
    return {
        "iso": "2026-09-30",
        "headline": headline,
        "tldr": tldr if tldr is not None else [{"text": "a bullet"}],
        "categories": categories if categories is not None else [
            {
                "name": "Tools & Products",
                "stories": [
                    {"title": "Story A", "summary": "Summary A", "url": "https://example.com/a"},
                ],
            }
        ],
    }


def mock_claude(grounded=True, unsupported_claims=None):
    """Fake anthropic client whose messages.create() returns a canned
    grounding-check response, so no real API call happens."""
    client = MagicMock()
    payload = json.dumps({"grounded": grounded, "unsupported_claims": unsupported_claims or []})
    fake_block = MagicMock()
    fake_block.text = payload
    fake_response = MagicMock()
    fake_response.content = [fake_block]
    client.messages.create.return_value = fake_response
    return client


class EvaluateDigestTests(unittest.TestCase):
    def setUp(self):
        # Isolate each test in a temp cwd so digests/ and web/embeddings.json
        # never touch the real project files.
        self.tmpdir = tempfile.mkdtemp()
        self._cwd = Path.cwd()
        os.chdir(self.tmpdir)
        Path("digests").mkdir()
        Path("web").mkdir()

    def tearDown(self):
        os.chdir(self._cwd)
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_clean_digest_passes(self):
        result = evaluate_digest(mock_claude(grounded=True), make_digest(), raw="some source text")
        self.assertTrue(result["passed"], result["issues"])

    def test_missing_headline_flagged(self):
        result = evaluate_digest(mock_claude(), make_digest(headline=""), raw="x")
        self.assertTrue(any("Missing headline" in i for i in result["issues"]))

    def test_missing_tldr_flagged(self):
        result = evaluate_digest(mock_claude(), make_digest(tldr=[]), raw="x")
        self.assertTrue(any("Missing TL;DR" in i for i in result["issues"]))

    def test_empty_category_flagged(self):
        digest = make_digest(categories=[{"name": "Empty Cat", "stories": []}])
        result = evaluate_digest(mock_claude(), digest, raw="x")
        self.assertTrue(any("has no stories" in i for i in result["issues"]))

    def test_duplicate_story_title_flagged(self):
        digest = make_digest(categories=[{
            "name": "Cat",
            "stories": [
                {"title": "Same Title", "summary": "A", "url": "https://x.com/1"},
                {"title": "Same Title", "summary": "B", "url": "https://x.com/2"},
            ],
        }])
        result = evaluate_digest(mock_claude(), digest, raw="x")
        self.assertTrue(any("Duplicate story title" in i for i in result["issues"]))

    def test_bad_url_flagged(self):
        digest = make_digest(categories=[{
            "name": "Cat",
            "stories": [{"title": "T", "summary": "S", "url": "not-a-url"}],
        }])
        result = evaluate_digest(mock_claude(), digest, raw="x")
        self.assertTrue(any("Bad/missing URL" in i for i in result["issues"]))

    def test_identical_headline_to_previous_day_flagged(self):
        Path("digests/2026-09-29.json").write_text(json.dumps(make_digest(headline="same headline")))
        result = evaluate_digest(mock_claude(), make_digest(headline="same headline"), raw="x")
        self.assertTrue(any("identical to previous digest" in i for i in result["issues"]))

    def test_unsupported_claim_flagged_by_judge(self):
        claude = mock_claude(grounded=False, unsupported_claims=["a made-up fact"])
        result = evaluate_digest(claude, make_digest(), raw="unrelated source text")
        self.assertTrue(any("Unsupported claim: a made-up fact" in i for i in result["issues"]))

    def test_semantic_duplicate_flagged(self):
        fake_vec = [0.1] * 384
        historical = [{
            "digestIso": "2026-01-01",
            "title": "An old story",
            "url": "https://x.com/old",
            "embedding": fake_vec,
        }]
        Path("web/embeddings.json").write_text(json.dumps(historical))

        fake_model = MagicMock()
        fake_model.embed.return_value = [fake_vec]  # today's story embeds identically to the old one

        result = evaluate_digest(mock_claude(), make_digest(), raw="x", embed_model=fake_model)
        self.assertTrue(any("semantic match" in i for i in result["issues"]))


if __name__ == "__main__":
    unittest.main()
