from pathlib import Path
from types import SimpleNamespace

from src import voice_cli


class FakeResponse:
    def __init__(self, *, payload=None, content=b""):
        self._payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeClient:
    def __init__(self, responses, calls):
        self.responses = iter(responses)
        self.calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def post(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return next(self.responses)


def test_voice_cli_captures_processes_plays_and_cleans_up(monkeypatch):
    subprocess_calls = []
    temporary_paths = []

    def fake_run(command, check):
        subprocess_calls.append(command)
        path = Path(command[-1])
        temporary_paths.append(path)
        if command[0] == "arecord":
            path.write_bytes(b"RIFF-test")
        return SimpleNamespace(returncode=0)

    http_calls = []
    responses = [
        FakeResponse(payload={"transcript": "bật đèn"}),
        FakeResponse(payload={"response": "Đã bật đèn."}),
        FakeResponse(content=b"RIFF-reply"),
    ]
    monkeypatch.setattr(voice_cli.subprocess, "run", fake_run)
    monkeypatch.setattr(voice_cli.httpx, "Client", lambda **_kwargs: FakeClient(responses, http_calls))

    result = voice_cli.run_voice_command("http://hub/api/v1/", 5)

    assert result == 0
    assert [call[0] for call in subprocess_calls] == ["arecord", "aplay"]
    assert [call[0] for call in http_calls] == [
        "http://hub/api/v1/voice/transcribe",
        "http://hub/api/v1/voice/process",
        "http://hub/api/v1/voice/synthesize",
    ]
    assert all(not path.exists() for path in temporary_paths)
