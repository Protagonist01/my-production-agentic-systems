"""Private mechanism artifacts; an external byte pin, not an attestation or release gate."""

from pathlib import Path

from agent_harness.contracts import Contract
from agent_harness.release_contracts import sha256
from agent_harness.trials import _write_exclusive


def save_state(root: Path, evidence: Contract) -> str:
    root.mkdir(mode=0o700)
    raw = evidence.canonical_json()
    _write_exclusive(root / "state.json", raw)
    return sha256(raw.encode())


def read_state[T: Contract](root: Path, expected_sha256: str, model: type[T]) -> T:
    path = root / "state.json"
    if root.is_symlink() or path.is_symlink() or {p.name for p in root.iterdir()} != {"state.json"}:
        raise ValueError("state evidence inventory differs")
    raw = path.read_bytes()
    if sha256(raw) != expected_sha256:
        raise ValueError("state evidence differs from external pin")
    value = model.model_validate_json(raw)
    if value.canonical_json().encode() != raw:
        raise ValueError("state evidence is not canonical")
    return value
