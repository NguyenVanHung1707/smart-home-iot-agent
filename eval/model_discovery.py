"""Discover and identify an exact set of six private GGUF model files."""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final, NewType

EXPECTED_MODEL_COUNT: Final = 6
HASH_CHUNK_SIZE: Final = 1024 * 1024

ModelSha256 = NewType("ModelSha256", str)
ModelSetSha256 = NewType("ModelSetSha256", str)
RelativeModelPath = NewType("RelativeModelPath", str)


class ModelDiscoveryError(Exception):
    """Base error for model discovery failures."""


@dataclass(frozen=True, slots=True)
class ModelRootError(ModelDiscoveryError):
    root: Path

    def __str__(self) -> str:
        return f"model root is not an existing directory: {self.root}"


@dataclass(frozen=True, slots=True)
class ModelCountError(ModelDiscoveryError):
    expected: int
    actual: int

    def __str__(self) -> str:
        return f"expected exactly {self.expected} GGUF models, found {self.actual}"


@dataclass(frozen=True, slots=True)
class UnsafeModelSymlinkError(ModelDiscoveryError):
    relative_path: RelativeModelPath

    def __str__(self) -> str:
        return f"model symlink escapes discovery root: {self.relative_path}"


@dataclass(frozen=True, slots=True)
class DuplicateModelError(ModelDiscoveryError):
    relative_paths: tuple[RelativeModelPath, ...]

    def __str__(self) -> str:
        return f"duplicate GGUF models: {', '.join(self.relative_paths)}"


@dataclass(frozen=True, slots=True)
class ModelIdentity:
    relative_path: RelativeModelPath
    sha256: ModelSha256
    size_bytes: int


@dataclass(frozen=True, slots=True)
class DiscoveredModels:
    models: tuple[ModelIdentity, ...]
    identity_sha256: ModelSetSha256


def discover_models(root: Path) -> DiscoveredModels:
    """Return identities only when root contains exactly six safe, unique GGUF files."""
    if not root.is_dir():
        raise ModelRootError(root=root)

    resolved_root = root.resolve(strict=True)
    candidates: list[tuple[RelativeModelPath, Path]] = []
    for directory, directory_names, file_names in os.walk(resolved_root, followlinks=False):
        directory_names.sort()
        file_names.sort()
        current = Path(directory)
        for file_name in file_names:
            if Path(file_name).suffix.casefold() != ".gguf":
                continue
            path = current / file_name
            relative_path = RelativeModelPath(path.relative_to(resolved_root).as_posix())
            if path.is_symlink():
                target = path.resolve(strict=False)
                if not target.is_relative_to(resolved_root):
                    raise UnsafeModelSymlinkError(relative_path=relative_path)
                continue
            if path.is_file():
                candidates.append((relative_path, path))

    candidates.sort(key=lambda candidate: candidate[0])
    if len(candidates) != EXPECTED_MODEL_COUNT:
        raise ModelCountError(expected=EXPECTED_MODEL_COUNT, actual=len(candidates))

    identities: list[ModelIdentity] = []
    physical_files: dict[tuple[int, int], RelativeModelPath] = {}
    hashes: dict[ModelSha256, RelativeModelPath] = {}
    for relative_path, path in candidates:
        stat = path.stat()
        physical_key = (stat.st_dev, stat.st_ino)
        previous_path = physical_files.get(physical_key)
        if previous_path is not None:
            raise DuplicateModelError(relative_paths=(previous_path, relative_path))
        physical_files[physical_key] = relative_path

        digest = hashlib.sha256()
        with path.open("rb") as model_file:
            while chunk := model_file.read(HASH_CHUNK_SIZE):
                digest.update(chunk)
        sha256 = ModelSha256(digest.hexdigest())
        duplicate_path = hashes.get(sha256)
        if duplicate_path is not None:
            raise DuplicateModelError(relative_paths=(duplicate_path, relative_path))
        hashes[sha256] = relative_path
        identities.append(ModelIdentity(relative_path=relative_path, sha256=sha256, size_bytes=stat.st_size))

    models = tuple(identities)
    set_digest = hashlib.sha256()
    for model in models:
        identity_record = f"{model.relative_path}\0{model.size_bytes}\0{model.sha256}\n"
        set_digest.update(identity_record.encode())
    return DiscoveredModels(models=models, identity_sha256=ModelSetSha256(set_digest.hexdigest()))
