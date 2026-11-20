"""Serialize validated checkpoint models without intermediate Python dicts."""
from functools import lru_cache

from pydantic import TypeAdapter


@lru_cache(maxsize=8)
def _encoder(model_type):
    return TypeAdapter(list[model_type])


def encode_records(records, model_type, *, exclude=None) -> str:
    return _encoder(model_type).dump_json(records, indent=2, exclude=exclude).decode("utf-8")
