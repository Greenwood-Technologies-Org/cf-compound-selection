import json
import os
from types import SimpleNamespace

import pytest
from drug_fibrosis_agent import evaluate_drug, PubChemTool

class DummyLLM:
    def bind(self, **_unused):
        return self
    def invoke(self, _prompt: str):
        return SimpleNamespace(content=json.dumps({
            "conclusion": "Indeterminate",
            "rationale": "mock"
        }))

@pytest.fixture
def dummy_llm():
    return DummyLLM()

# ------------------------------------------------------------------ #
# Tests                                                              #
# ------------------------------------------------------------------ #
def test_bad_name_indeterminate(monkeypatch, dummy_llm):
    monkeypatch.setattr(
        PubChemTool,
        "_run",
        lambda self, path: {"IdentifierList": {"CID": []}},
    )
    out = evaluate_drug("NotARealDrug", llm=dummy_llm)
    assert out["conclusion"] == "Indeterminate"
    assert "/compound/name/NotARealDrug/cids/JSON" in out["tool_trace"]

def test_schema_keys(monkeypatch, dummy_llm):
    monkeypatch.setattr(
        PubChemTool,
        "_run",
        lambda self, path: {"IdentifierList": {"CID": []}},
    )
    out = evaluate_drug("AnotherFake", llm=dummy_llm)
    assert {"conclusion", "rationale", "tool_trace"} <= out.keys()

# @pytest.mark.skip(reason="Hits live PubChem & OpenAI")
def test_jq1_integration():
    from langchain_openai import ChatOpenAI
    out = evaluate_drug("JQ1", llm=ChatOpenAI(model="gpt-4o-mini", temperature=0))
    assert out["conclusion"] in {"Positive", "Indeterminate"}
