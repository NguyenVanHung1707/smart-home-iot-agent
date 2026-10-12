"""Tests for FloorplanService separating Real hardware and Simulator 3D flows."""

import json
from pathlib import Path
from src.services.floorplan import (
    get_floorplan_state,
    save_floorplan_walls,
    update_floorplan_device,
    reset_floorplan_state,
)


def test_get_floorplan_real_mode():
    state = get_floorplan_state("real")
    assert state["mode"] == "real"
    assert "walls" in state
    assert len(state["walls"]) >= 4
    assert "devices" in state
    # Should have real devices
    dev_ids = {d["id"] for d in state["devices"]}
    assert "living-light" in dev_ids
    assert "bedroom-light" in dev_ids
    assert "entry-lock" in dev_ids


def test_get_floorplan_simulator_mode():
    state = get_floorplan_state("simulator")
    assert state["mode"] == "simulator"
    assert "walls" in state
    assert "devices" in state
    assert "faults" in state


def test_update_and_save_real_floorplan(tmp_path, monkeypatch):
    test_path = tmp_path / "floorplan_real.json"
    monkeypatch.setattr("src.services.floorplan.REAL_FLOORPLAN_PATH", test_path)

    new_walls = [
        {"x1": 10.0, "y1": 10.0, "x2": 100.0, "y2": 10.0},
        {"x1": 100.0, "y1": 10.0, "x2": 100.0, "y2": 100.0},
    ]
    saved = save_floorplan_walls(new_walls, mode="real")
    assert len(saved) == 2

    # Update device position
    update_floorplan_device("living-light", {"x": 120.0, "y": 85.0}, mode="real")

    state = get_floorplan_state("real")
    living_light = next(d for d in state["devices"] if d["id"] == "living-light")
    assert living_light["x"] == 120.0
    assert living_light["y"] == 85.0
