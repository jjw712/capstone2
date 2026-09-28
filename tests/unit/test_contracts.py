"""예시 자료가 contracts 형식에 맞는지, 잘못된 값은 거부하는지 확인."""

import pytest
from pydantic import ValidationError

from roboadvisor.contracts import (
    Decision,
    EvaluationResult,
    ResearchResult,
    RiskTag,
    RunManifest,
)

EXAMPLES = [
    ("sample_risk_tag.json", RiskTag),
    ("sample_decision.json", Decision),
    ("sample_research_result.json", ResearchResult),
    ("sample_evaluation.json", EvaluationResult),
    ("sample_run_manifest.json", RunManifest),
]


@pytest.mark.parametrize("filename, model", EXAMPLES)
def test_example_matches_contract(load_fixture, filename, model):
    model.model_validate(load_fixture(filename))


def test_weights_must_sum_to_one(load_fixture):
    data = load_fixture("sample_decision.json")
    data["final_weights"]["SPY"] += 0.1
    with pytest.raises(ValidationError):
        Decision.model_validate(data)


def test_research_result_requires_citation(load_fixture):
    data = load_fixture("sample_research_result.json")
    data["citations"] = []
    with pytest.raises(ValidationError):
        ResearchResult.model_validate(data)


def test_agent_risk_tag_requires_source(load_fixture):
    data = load_fixture("sample_risk_tag.json")
    data["sources"] = []
    with pytest.raises(ValidationError):
        RiskTag.model_validate(data)


def test_unknown_field_is_rejected(load_fixture):
    data = load_fixture("sample_risk_tag.json")
    data["typo_field"] = 1
    with pytest.raises(ValidationError):
        RiskTag.model_validate(data)


def test_risk_severity_is_between_zero_and_one(load_fixture):
    data = load_fixture("sample_risk_tag.json")
    data["severity"] = 1.5
    with pytest.raises(ValidationError):
        RiskTag.model_validate(data)
