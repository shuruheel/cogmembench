from cogmembench.cli import _protocol_metadata


def test_protocol_metadata_handles_unlocked_run_manifest() -> None:
    assert _protocol_metadata({"protocol_lock": None}) == {}
    assert _protocol_metadata({}) == {}
    assert _protocol_metadata(
        {"protocol_lock": {"evaluator_version": "development-v2"}}
    ) == {"evaluator_version": "development-v2"}
