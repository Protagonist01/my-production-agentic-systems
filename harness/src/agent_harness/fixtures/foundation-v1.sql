-- Invented, evaluator-owned bootstrap; contains no source rows or expected labels.
INSERT INTO runtime.checkpoints (checkpoint_key, payload)
VALUES ('invented-checkpoint', '{"step": "start", "source_kind": "synthetic"}');
INSERT INTO runtime.reviews (review_key, payload, status)
VALUES ('invented-review', '{"reason": "fixture only"}', 'pending');
INSERT INTO runtime.ledger (entry_key, payload)
VALUES ('invented-baseline', '{"effect": "none", "source_kind": "synthetic"}');
