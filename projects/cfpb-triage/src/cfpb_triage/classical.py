"""Real TF-IDF/logistic regression baseline. No pickles or holdout fitting."""

import importlib
import warnings
from typing import Any

from cfpb_triage.evaluation_v2 import Observation, Reference, validate_groups


class TfidfBaseline:
    def __init__(self) -> None:
        feature = importlib.import_module("sklearn.feature_extraction.text")
        linear = importlib.import_module("sklearn.linear_model")
        self.vectorizer: Any = feature.TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=20000,
            sublinear_tf=True,
        )
        self.classifier: Any = linear.LogisticRegression(
            max_iter=2000,
            random_state=0,
            class_weight="balanced",
            C=1.0,
        )
        self.training_groups: set[str] = set()
        self.training_text: set[str] = set()
        self.training_parents: set[str] = set()

    def fit(self, cases: tuple[Reference, ...]) -> None:
        validate_groups(cases)
        if not cases or any(c.split != "training" for c in cases):
            raise ValueError("training-only fitting required")
        labels = [c.scope + "|" + (c.product or "") + "|" + (c.issue or "") for c in cases]
        if len(set(labels)) < 2:
            raise ValueError("at least two classes required")
        with warnings.catch_warnings():
            # Non-convergence is a failed baseline, not a silent valid result.
            warnings.simplefilter("error")
            self.classifier.fit(self.vectorizer.fit_transform([c.text for c in cases]), labels)
        self.training_groups = {c.family for c in cases}
        self.training_text = {c.text for c in cases}
        self.training_parents = {c.parent for c in cases}

    def predict(self, cases: tuple[Reference, ...]) -> list[dict[str, object]]:
        if not self.training_groups:
            raise ValueError("fit before prediction")
        validate_groups(cases)
        if any(
            c.family in self.training_groups
            or c.text in self.training_text
            or c.parent in self.training_parents
            or c.split == "training"
            for c in cases
        ):
            raise ValueError("evaluation overlaps training")
        probabilities = self.classifier.predict_proba(
            self.vectorizer.transform([c.text for c in cases])
        )
        return [
            {
                "case_id": c.case_id,
                "label": str(self.classifier.classes_[int(p.argmax())]),
                "confidence": float(p.max()),
                "priority": "unqualified",
                "action": "review_required",
                "variant": "tfidf",
            }
            for c, p in zip(cases, probabilities, strict=True)
        ]

    def metadata(self) -> dict[str, object]:
        return {
            "implementation": "sklearn_tfidf_logistic_regression",
            "sklearn_version": importlib.import_module("sklearn").__version__,
            "training_families": len(self.training_groups),
            "priority_or_ambiguity_qualification": False,
            "configuration": {
                "ngram_range": [1, 2],
                "max_features": 20000,
                "C": 1.0,
                "class_weight": "balanced",
                "random_state": 0,
            },
        }

    def observations(self, cases: tuple[Reference, ...]) -> tuple[Observation, ...]:
        rows = []
        for prediction in self.predict(cases):
            scope, product, issue = str(prediction["label"]).split("|", 2)
            rows.append(
                Observation.model_validate(
                    {
                        "case_id": prediction["case_id"],
                        "variant": "tfidf",
                        "trial": 1,
                        "action": "review_required",
                        "scope": scope,
                        "product": product or None,
                        "issue": issue or None,
                        "confidence": prediction["confidence"],
                    }
                )
            )
        return tuple(rows)
