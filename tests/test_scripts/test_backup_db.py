"""Tests for scripts/backup_db.py."""

import json
import zipfile
from pathlib import Path

import pytest

import scripts.backup_db as backup_tool


def test_create_and_verify_backup(tmp_path, monkeypatch):
    monkeypatch.setattr(backup_tool, "BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr(backup_tool, "DATA_DIR", tmp_path / "data")
    monkeypatch.setattr(backup_tool, "RUNTIME_DIR", tmp_path / "runtime")

    # Create dummy data file
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "devices.json").write_text('[{"id": "test-dev"}]', encoding="utf-8")

    archive = backup_tool.create_backup(keep=3)
    assert archive.is_file()
    assert archive.suffix == ".zip"

    with zipfile.ZipFile(archive, "r") as z:
        names = z.namelist()
        assert "manifest.json" in names
        assert "devices.json" in names
        manifest = json.loads(z.read("manifest.json").decode("utf-8"))
        assert "created_at" in manifest
        assert "devices.json" in manifest["files"]


def test_rotate_backups(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(parents=True)
    monkeypatch.setattr(backup_tool, "BACKUP_DIR", backup_dir)

    # Create 5 dummy backup files
    for i in range(5):
        (backup_dir / f"homing_backup_20261014_{i:02d}0000.zip").write_text("dummy")

    assert len(list(backup_dir.glob("*.zip"))) == 5

    deleted = backup_tool.rotate_backups(keep=3)
    assert len(deleted) == 2
    assert len(list(backup_dir.glob("*.zip"))) == 3


def test_restore_backup(tmp_path, monkeypatch):
    backup_dir = tmp_path / "backups"
    data_dir = tmp_path / "data"
    runtime_dir = tmp_path / "runtime"
    backup_dir.mkdir(parents=True)
    data_dir.mkdir(parents=True)
    runtime_dir.mkdir(parents=True)

    monkeypatch.setattr(backup_tool, "BACKUP_DIR", backup_dir)
    monkeypatch.setattr(backup_tool, "DATA_DIR", data_dir)
    monkeypatch.setattr(backup_tool, "RUNTIME_DIR", runtime_dir)

    zip_file = backup_dir / "homing_backup_test.zip"
    with zipfile.ZipFile(zip_file, "w") as z:
        z.writestr("manifest.json", json.dumps({"version": "1.0", "created_at": "2026-10-14T00:00:00Z"}))
        z.writestr("devices.json", '[{"id": "restored-light"}]')

    success = backup_tool.restore_backup(zip_file)
    assert success is True
    assert (data_dir / "devices.json").exists()
    assert "restored-light" in (data_dir / "devices.json").read_text(encoding="utf-8")
