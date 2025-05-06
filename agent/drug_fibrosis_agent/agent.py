"""
Cardiac-fibrosis assessor (LangChain 0.2 + LangGraph 0.0.21)
"""

from __future__ import annotations

import collections
import json
import time
from typing import Any, Dict, List, TypedDict

import httpx
from langchain_core.tools import BaseTool
from langchain_openai import ChatOpenAI
from langgraph.graph import START, END, StateGraph

class PubChemTool(BaseTool):
    name: str = "pubchem_api"
    description: str = (
        "Sync wrapper around PubChem PUG-REST. "
        "Call with the URL suffix beginning '/compound/...'."
    )
    _BASE = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    _window: collections.deque = collections.deque(maxlen=5)

    def _run(self, path: str) -> Dict[str, Any]:
        if len(self._window) == 5 and time.time() - self._window[0] < 1:
            time.sleep(1 - (time.time() - self._window[0]))
        self._window.append(time.time())

        url = f"{self._BASE}{path}"
        with httpx.Client(timeout=30) as client:
            r = client.get(url)
            r.raise_for_status()
            return r.json()

class FibrosisState(TypedDict, total=False):
    drug_name: str
    cid: int
    raw_records: Dict[str, Any]
    relevance: int
    confidence: int
    conclusion: str
    rationale: str
    trace: List[str]

def identify_cid(state: FibrosisState, tool: PubChemTool) -> FibrosisState:
    path = f"/compound/name/{state['drug_name']}/cids/JSON"
    data = tool.run(path)
    cids = data.get("IdentifierList", {}).get("CID", [])
    return {"cid": cids[0] if cids else None, "trace": state["trace"] + [path]}

def fetch_details(state: FibrosisState, tool: PubChemTool) -> FibrosisState:
    cid = state.get("cid")
    if cid is None:
        return {}
    paths = [
        f"/compound/cid/{cid}/property/"
        "MolecularFormula,MolecularWeight,CanonicalSMILES/JSON",
        f"/compound/cid/{cid}/classification/JSON",
        f"/compound/cid/{cid}/assaysummary/JSON",
    ]
    rec: Dict[str, Any] = {}
    for p in paths:
        rec[p] = tool.run(p)
    return {
        "raw_records": rec,
        "trace": state["trace"] + paths,
    }

_FIBROSIS_TERMS = (
    "fibro", "cardiac", "heart", "tgf", "brd4", "collagen", "myofibro"
)

def _summarise_pubchem(records: Dict[str, Any]) -> Dict[str, Any]:
    """Condense PubChem blobs to the few fields relevant for fibrosis."""
    summary: Dict[str, Any] = {}

    for path, blob in records.items():
        if "/property/" in path:
            props = blob.get("PropertyTable", {}).get("Properties", [{}])[0]
            summary["formula"] = props.get("MolecularFormula")
            summary["mol_weight"] = props.get("MolecularWeight")
            break

    for path, blob in records.items():
        if "/classification/" in path:
            cl = (
                blob.get("HierarchicalClassificationTree", {})
                    .get("ClassificationNode", {})
                    .get("ToOne", {})
            )
            levels = []
            while isinstance(cl, dict) and "NodeName" in cl and len(levels) < 3:
                levels.append(cl["NodeName"])
                cl = cl.get("ToOne", {})
            summary["classification"] = " ⭢ ".join(levels)
            break

    assays = []
    for path, blob in records.items():
        if "/assaysummary/" in path:
            rows = (
                blob.get("AssayTable", {})
                    .get("Rows", [])
            )
            for row in rows:
                title = row.get("Name", "").lower()
                outcome = row.get("ActivityOutcome", "")
                if outcome != "Inactive" and any(t in title for t in _FIBROSIS_TERMS):
                    assays.append({
                        "aid": row.get("AID"),
                        "title": row.get("Name"),
                        "outcome": outcome,
                    })
                if len(assays) == 5:
                    break
    if assays:
        summary["assays"] = assays
    return summary

def analyze_fibrosis(state: FibrosisState, llm: ChatOpenAI) -> FibrosisState:
    records = state.get("raw_records", {})
    concise = _summarise_pubchem(records)

    llm_json = llm.bind(response_format={"type": "json_object"})
    prompt = (
        "You are a biomedical expert. For the compound described below, decide "
        "whether its implications for reversing cardiac fibrosis are POSITIVE, "
        "NEGATIVE, or INDETERMINATE, and produce quantitative relevance and "
        "confidence scores.\n\n"
        "Scoring guidelines:\n"
        "  • relevance (0-100):\n"
        "        0   = actively harmful / promotes fibrosis\n"
        "       50   = neutral or unclear effect\n"
        "      100   = strongly beneficial / anti-fibrotic\n"
        "  • confidence (0-100):\n"
        "        0   = completely unsure\n"
        "      100   = absolutely certain\n\n"
        "Decision label guidelines:\n"
        "  • POSITIVE  = inhibits BRD4 or TGF-β signaling, reduces collagen "
        "deposition or fibroblast activation.\n"
        "  • NEGATIVE  = activates pro-fibrotic pathways or is cardiotoxic.\n"
        "  • INDETERMINATE = evidence is insufficient or conflicting.\n\n"
        f"COMPOUND_BRIEF = {json.dumps(concise, ensure_ascii=False)}\n\n"
        "Return a JSON object with exactly these keys:\n"
        "  conclusion  — one of POSITIVE, NEGATIVE, INDETERMINATE\n"
        "  relevance   — integer 0-100\n"
        "  confidence  — integer 0-100\n"
        "  rationale   — brief explanation supporting the scores\n"
    )
    msg = llm_json.invoke(prompt)
    try:
        obj = json.loads(msg.content)
    except json.JSONDecodeError:
        obj = {"conclusion": "Indeterminate", "rationale": "Could not parse LLM output"}
    return {
        "conclusion": obj.get("conclusion", "Indeterminate").title(),
        "relevance": obj.get("relevance", 50),
        "confidence": obj.get("confidence", 0),
        "rationale": obj.get("rationale", ""),
    }


def conclude(state: FibrosisState) -> Dict[str, Any]:
    return {
        "conclusion": state.get("conclusion", "Indeterminate"),
        "relevance": state.get("relevance", 50),
        "confidence": state.get("confidence", 0),
        "rationale": state.get("rationale", "No rationale produced."),
        "tool_trace": state.get("trace", []),
    }

def build_graph(llm: ChatOpenAI | None = None):
    llm = llm or ChatOpenAI(model="gpt-4o-mini", temperature=0)
    tool = PubChemTool()

    g = StateGraph(FibrosisState)
    g.add_node("identify_cid", lambda s: identify_cid(s, tool))
    g.add_node("fetch_details", lambda s: fetch_details(s, tool))
    g.add_node("analyze_fibrosis", lambda s: analyze_fibrosis(s, llm))
    g.add_node("conclude", conclude)

    g.add_edge(START, "identify_cid")
    g.add_edge("identify_cid", "fetch_details")
    g.add_edge("fetch_details", "analyze_fibrosis")
    g.add_edge("analyze_fibrosis", "conclude")
    g.set_finish_point("conclude")
    return g.compile()

def evaluate_drug(drug_name: str, llm: ChatOpenAI | None = None) -> Dict[str, Any]:
    graph = build_graph(llm)
    result: FibrosisState = graph.invoke({"drug_name": drug_name, "trace": []})

    # ----  canonical output schema  --------------------------------------
    return {
        "conclusion": result.get("conclusion", "Indeterminate"),
        "relevance": result.get("relevance", 50),
        "confidence": result.get("confidence", 0),
        "rationale" : result.get("rationale", "No rationale generated."),
        "tool_trace": result.get("tool_trace", result.get("trace", [])),
    }


if __name__ == "__main__":
    from langchain_openai import ChatOpenAI
    result = evaluate_drug("JQ1", llm=ChatOpenAI(model="gpt-4o-mini", temperature=0))
    print(result)