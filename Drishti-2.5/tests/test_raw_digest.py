"""Compatibility oracle for the frozen schema-5 byte stream."""

import hashlib
import json
from dataclasses import dataclass, fields, is_dataclass
from enum import IntEnum, StrEnum
from typing import Any

import numpy as np
import pytest

from drishti.product_result import _canonical, _feed_raw


def _reference(digest: Any, value: object) -> None:
    """Original schema-5 encoder, retained independently of the optimized dispatch."""
    if isinstance(value, np.ndarray):
        header = f"A{value.dtype.str.replace('=', '<')}{list(value.shape)}:{value.nbytes};"
        digest.update(header.encode())
        if value.size:
            digest.update(memoryview(value.reshape(-1)).cast("B"))
    elif is_dataclass(value) and not isinstance(value, type):
        digest.update(f"D{type(value).__name__}{{".encode())
        for field in fields(value):
            digest.update(f"{field.name}=".encode())
            _reference(digest, getattr(value, field.name))
        digest.update(b"}")
    elif isinstance(value, tuple):
        digest.update(f"T{len(value)}[".encode())
        if value and all(type(item) is int for item in value):
            digest.update(b"i")
            digest.update(np.asarray(value, dtype=np.int64).tobytes())
        else:
            for item in value:
                _reference(digest, item)
        digest.update(b"]")
    else:
        scalar = value if type(value) in (int, str, bool) or value is None else _canonical(value)
        digest.update(b"S")
        digest.update(json.dumps(scalar, allow_nan=False, sort_keys=True).encode())
        digest.update(b";")


class Number(IntEnum):
    ONE = 1


class Text(StrEnum):
    LABEL = "observed"


@dataclass(frozen=True)
class Payload:
    scalar: object
    support: tuple[int, ...]
    geometry: object


@pytest.mark.parametrize(
    "scalar",
    [
        None,
        True,
        False,
        0,
        -1,
        2**63 - 1,
        -0.0,
        0.0,
        1e-7,
        1e20,
        float.fromhex("0x1.fffffffffffffp+1023"),
        np.float64(1.25),
        "",
        'quotes"\n\\',
        "terrain \u2603 \U0001f680",
        Number.ONE,
        Text.LABEL,
    ],
)
def test_raw_digest_matches_frozen_stream(scalar: object) -> None:
    value = Payload(
        scalar,
        (0, 7, 2**63 - 1),
        ((), (True, 1, -0.0), np.arange(12, dtype=np.int64).reshape(4, 3)),
    )
    expected = hashlib.sha256()
    actual = hashlib.sha256()
    _reference(expected, value)
    _feed_raw(actual, value)
    assert actual.digest() == expected.digest()


@pytest.mark.parametrize("scalar", [float("nan"), float("inf"), -float("inf")])
def test_raw_digest_still_rejects_nonfinite_scalars(scalar: float) -> None:
    with pytest.raises(ValueError, match="nonfinite"):
        _feed_raw(hashlib.sha256(), Payload(scalar, (), ()))
