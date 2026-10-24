"""Fixed result matrices for domain reports; no missing-row deletion or retries."""


def validate_matrix(
    case_ids: tuple[str, ...], trial_ids: tuple[str, ...], keys: tuple[tuple[str, str], ...]
) -> None:
    if (
        not case_ids
        or not trial_ids
        or any(not value.strip() for value in (*case_ids, *trial_ids))
        or len(set(case_ids)) != len(case_ids)
        or len(set(trial_ids)) != len(trial_ids)
    ):
        raise ValueError("nonempty unique scheduled case/trial inventories required")
    expected = {(case, trial) for case in case_ids for trial in trial_ids}
    if len(set(keys)) != len(keys) or not set(keys).issubset(expected):
        raise ValueError("duplicate or unexpected observed case/trial")


def ratio(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None
