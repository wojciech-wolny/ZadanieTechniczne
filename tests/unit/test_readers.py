"""Component tests for chunked file readers."""

import math
import struct
from pathlib import Path

import pytest

from producer.constants import MAX_TOKEN_LENGTH
from producer.readers import parse_token, read_binary_samples, read_text_samples


@pytest.mark.parametrize("chunk_size", [1, 2, 3, 7, 65536], ids=["1", "2", "3", "7", "default"])
def test_read_text_samples_chunk_size_does_not_change_values(
    tmp_path: Path,
    chunk_size: int,
) -> None:
    """Verify PRD-9: a token split across reads stays one sample."""
    path = tmp_path / "samples.txt"
    path.write_text("1.5\n\n2.25 3\n-40", encoding="utf-8")

    values = list(read_text_samples(path, chunk_size=chunk_size))

    assert values == [1.5, 2.25, 3.0, -40.0]


def test_read_text_samples_ignores_a_byte_order_mark(tmp_path: Path) -> None:
    """Verify PRD-4: a text file saved with a byte order mark keeps its first sample."""
    path = tmp_path / "bom.txt"
    path.write_bytes(b"\xef\xbb\xbf1.5 2.5 3.5\n")

    values = list(read_text_samples(path))

    assert values == [1.5, 2.5, 3.5]


def test_read_text_samples_skips_invalid_and_non_finite_tokens(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify PRD-4 and H9: invalid and non finite text tokens are skipped with one summary."""
    path = tmp_path / "mixed.txt"
    path.write_text("1 nope nan inf 8", encoding="utf-8")

    values = list(read_text_samples(path, chunk_size=2))

    assert values == [1.0, 8.0]
    assert "skipped 3 text tokens" in caplog.text


@pytest.mark.parametrize("chunk_size", [7, 65536], ids=["7", "default"])
def test_read_text_samples_accepts_token_at_length_limit(
    tmp_path: Path,
    chunk_size: int,
) -> None:
    """Verify PRD-9: a token of 1024 characters is still parsed."""
    token = "0." + "1" * (MAX_TOKEN_LENGTH - 2)
    path = tmp_path / "boundary.txt"
    path.write_text(f"{token} 2\n", encoding="utf-8")

    values = list(read_text_samples(path, chunk_size=chunk_size))

    assert len(token) == MAX_TOKEN_LENGTH
    assert values == [float(token), 2.0]


@pytest.mark.parametrize("chunk_size", [1, 7, 700, 65536], ids=["1", "7", "700", "default"])
def test_read_text_samples_skips_token_above_length_limit(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    chunk_size: int,
) -> None:
    """Verify PRD-9: a token longer than 1024 characters is skipped as a whole."""
    token = "0." + "1" * (MAX_TOKEN_LENGTH * 3)
    path = tmp_path / "long.txt"
    path.write_text(f"1 {token} 4\n", encoding="utf-8")

    values = list(read_text_samples(path, chunk_size=chunk_size))

    assert values == [1.0, 4.0]
    assert "skipped 1 text tokens" in caplog.text
    assert "longer than 1024 characters" in caplog.text
    assert len(caplog.records) == 1


def test_read_text_samples_skips_long_token_at_end_of_file(tmp_path: Path) -> None:
    """Verify PRD-9: an overlong final token without trailing whitespace is skipped."""
    path = tmp_path / "long_tail.txt"
    path.write_text("5 " + "9" * (MAX_TOKEN_LENGTH + 1), encoding="utf-8")

    values = list(read_text_samples(path, chunk_size=100))

    assert values == [5.0]


@pytest.mark.parametrize(
    ("token", "expected"),
    [("2.5", 2.5), ("abc", None), ("inf", None), ("nan", None)],
    ids=["decimal", "text", "infinity", "nan"],
)
def test_parse_token_partitions(token: str, expected: float | None) -> None:
    """Verify PRD-4: only finite numeric tokens become samples."""
    assert parse_token(token) == expected


def test_read_binary_samples_chunk_size_does_not_change_values(tmp_path: Path) -> None:
    """Verify PRD-9: a float32 value split across reads stays one sample."""
    path = tmp_path / "samples.bin"
    path.write_bytes(struct.pack("<fff", 1.0, -2.5, 4.0))

    whole = list(read_binary_samples(path))
    split = list(read_binary_samples(path, chunk_size=1))

    assert whole == split == [1.0, -2.5, 4.0]


def test_read_binary_samples_skips_non_finite_values(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify PRD-4 and H9: non finite binary samples are skipped with one summary."""
    path = tmp_path / "special.bin"
    path.write_bytes(struct.pack("<fff", 1.0, math.nan, 2.0))

    values = list(read_binary_samples(path, chunk_size=5))

    assert values == [1.0, 2.0]
    assert "skipped 1 non finite binary samples" in caplog.text


def test_read_binary_samples_ignores_trailing_bytes(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify PRD-9: trailing bytes shorter than one sample are ignored with a warning."""
    path = tmp_path / "tail.bin"
    path.write_bytes(struct.pack("<ff", 1.0, 2.0) + b"\x01\x02")

    values = list(read_binary_samples(path, chunk_size=3))

    assert values == [1.0, 2.0]
    assert "ignoring 2 trailing bytes" in caplog.text


def test_read_binary_samples_shorter_than_one_sample_yields_nothing(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify PRD-4: a binary file shorter than one sample yields nothing."""
    path = tmp_path / "short.bin"
    path.write_bytes(b"\x01\x02\x03")

    values = list(read_binary_samples(path))

    assert values == []
    assert "ignoring 3 trailing bytes" in caplog.text
