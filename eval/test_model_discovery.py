"""Focused tests for private GGUF model discovery."""

import hashlib
import os
from pathlib import Path

import pytest

from eval.model_discovery import (
    DuplicateModelError,
    ModelCountError,
    ModelRootError,
    UnsafeModelSymlinkError,
    discover_models,
)


def _write_models(root: Path, names: tuple[str, ...]) -> None:
    for index, name in enumerate(names):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(f"model-{index}".encode())


def test_discovery_returns_exactly_six_in_relative_posix_order(tmp_path: Path) -> None:
    # Given
    names = ("z.GGUF", "nested/c.gguf", "A.gguf", "nested/B.GgUf", "d.gguf", "e.gguf")
    _write_models(tmp_path, names)
    (tmp_path / "ignored.txt").write_text("not a model", encoding="utf-8")

    # When
    discovered = discover_models(tmp_path)

    # Then
    assert tuple(model.relative_path for model in discovered.models) == (
        "A.gguf",
        "d.gguf",
        "e.gguf",
        "nested/B.GgUf",
        "nested/c.gguf",
        "z.GGUF",
    )
    assert all(not Path(model.relative_path).is_absolute() for model in discovered.models)


def test_discovery_hashes_complete_file_content(tmp_path: Path) -> None:
    # Given
    _write_models(tmp_path, tuple(f"model-{index}.gguf" for index in range(5)))
    payload = (b"streamed-content" * 100_000) + b"end"
    (tmp_path / "large.gguf").write_bytes(payload)

    # When
    discovered = discover_models(tmp_path)

    # Then
    large = next(model for model in discovered.models if model.relative_path == "large.gguf")
    assert large.sha256 == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("create_root", [False, True])
def test_discovery_rejects_missing_or_non_directory_root(tmp_path: Path, create_root: bool) -> None:
    # Given
    root = tmp_path / "root"
    if create_root:
        root.write_text("not a directory", encoding="utf-8")

    # When / Then
    with pytest.raises(ModelRootError):
        discover_models(root)


@pytest.mark.parametrize("count", [0, 5, 7])
def test_discovery_rejects_counts_other_than_six(tmp_path: Path, count: int) -> None:
    # Given
    _write_models(tmp_path, tuple(f"model-{index}.gguf" for index in range(count)))

    # When / Then
    with pytest.raises(ModelCountError) as raised:
        discover_models(tmp_path)
    assert raised.value.actual == count
    assert raised.value.expected == 6


def test_discovery_rejects_symlink_escaping_root(tmp_path: Path) -> None:
    # Given
    root = tmp_path / "models"
    root.mkdir()
    _write_models(root, tuple(f"model-{index}.gguf" for index in range(5)))
    outside = tmp_path / "outside.gguf"
    outside.write_bytes(b"outside")
    try:
        (root / "escaped.gguf").symlink_to(outside)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    # When / Then
    with pytest.raises(UnsafeModelSymlinkError):
        discover_models(root)


def test_discovery_does_not_follow_symlinked_directories(tmp_path: Path) -> None:
    # Given
    root = tmp_path / "models"
    root.mkdir()
    _write_models(root, tuple(f"model-{index}.gguf" for index in range(6)))
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "seventh.gguf").write_bytes(b"outside")
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
    except OSError as error:
        pytest.skip(f"symlinks unavailable: {error}")

    # When
    discovered = discover_models(root)

    # Then
    assert len(discovered.models) == 6


def test_discovery_rejects_duplicate_model_content(tmp_path: Path) -> None:
    # Given
    _write_models(tmp_path, tuple(f"model-{index}.gguf" for index in range(4)))
    duplicate = b"same-model"
    (tmp_path / "copy-one.gguf").write_bytes(duplicate)
    (tmp_path / "copy-two.gguf").write_bytes(duplicate)

    # When / Then
    with pytest.raises(DuplicateModelError) as raised:
        discover_models(tmp_path)
    assert raised.value.relative_paths == ("copy-one.gguf", "copy-two.gguf")


def test_discovery_rejects_duplicate_hardlinks(tmp_path: Path) -> None:
    # Given
    _write_models(tmp_path, tuple(f"model-{index}.gguf" for index in range(4)))
    original = tmp_path / "original.gguf"
    original.write_bytes(b"hard-linked")
    try:
        os.link(original, tmp_path / "alias.gguf")
    except OSError as error:
        pytest.skip(f"hard links unavailable: {error}")

    # When / Then
    with pytest.raises(DuplicateModelError):
        discover_models(tmp_path)
