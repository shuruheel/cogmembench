import os

from cogmembench.config import load_env_file


def test_env_file_loads_without_overriding_process_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("COGMEMBENCH_EXISTING", "process")
    monkeypatch.delenv("COGMEMBENCH_NEW", raising=False)
    path = tmp_path / ".env"
    path.write_text(
        "# ignored\nexport COGMEMBENCH_NEW='from file'\nCOGMEMBENCH_EXISTING=file\n"
    )

    load_env_file(path)

    assert os.environ["COGMEMBENCH_NEW"] == "from file"
    assert os.environ["COGMEMBENCH_EXISTING"] == "process"
