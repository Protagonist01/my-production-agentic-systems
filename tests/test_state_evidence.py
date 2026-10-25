"""State artifacts need canonical bytes and an externally retained pin."""

import pytest
from agent_harness.contracts import Contract
from agent_harness.release_contracts import sha256
from agent_harness.state_evidence import read_state, save_state


class InventedState(Contract):
    observed: bool


@pytest.mark.parametrize("change", ["bytes", "pin", "extra", "noncanonical", "missing"])
def test_state_reader_rejects_changed_inventory_or_external_pin(tmp_path, change):
    root = tmp_path / "private"
    value = InventedState(observed=True)
    digest = save_state(root, value)
    assert read_state(root, digest, InventedState) == value
    with pytest.raises(FileExistsError):
        save_state(root, value)
    path = root / "state.json"
    if change == "bytes":
        path.write_text("{}", encoding="utf-8")
    elif change == "pin":
        digest = "0" * 64
    elif change == "extra":
        (root / "extra").write_text("invented", encoding="utf-8")
    elif change == "missing":
        path.unlink()
    else:
        raw = value.canonical_json() + "\n"
        path.write_bytes(raw.encode())
        digest = sha256(raw.encode())
    with pytest.raises((ValueError, OSError)):
        read_state(root, digest, InventedState)
