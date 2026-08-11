"""Sentence embeddings for tweet bodies.

The model is pinned rather than left to fastembed's default: its output is
stored, so a change of default would silently start writing vectors from a
different model into the same column, where nothing could tell them apart.

It is also loaded lazily. ``radius.cli`` imports ``radius.ingest``, which
imports this module, so building the model at import time would have every
command — ``keys show`` included — pay to load onnxruntime.
"""

from functools import cache

import numpy as np
from fastembed import TextEmbedding

MODEL = "BAAI/bge-small-en-v1.5"
DIMENSIONS = 384


@cache
def _model() -> TextEmbedding:
    return TextEmbedding(MODEL)


def embed_tweets(tweets: list[str]) -> list[bytes]:
    """One float32 vector per tweet, in the order given, as libSQL blobs."""
    if not tweets:
        return []
    return [vector.astype(np.float32).tobytes() for vector in _model().embed(tweets)]
