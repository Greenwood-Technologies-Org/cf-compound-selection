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
    """
    Condense PubChem blobs to fields relevant for cardiac fibrosis analysis.
    
    Focuses on:
    - Basic chemical properties
    - Bioactivity data particularly related to TGF-β and fibrosis pathways
    - Classifications and biological targets
    - Epigenetic mechanisms including BRD4 inhibition
    """
    summary: Dict[str, Any] = {}
    
    # Basic chemical properties
    for path, blob in records.items():
        if "/property/" in path:
            props = blob.get("PropertyTable", {}).get("Properties", [{}])[0]
            summary["formula"] = props.get("MolecularFormula")
            summary["mol_weight"] = props.get("MolecularWeight")
            summary["canonical_smiles"] = props.get("CanonicalSMILES")
            summary["hydrogen_bond_donors"] = props.get("HBondDonorCount")
            summary["hydrogen_bond_acceptors"] = props.get("HBondAcceptorCount")
            summary["rotatable_bonds"] = props.get("RotatableBondCount")
            summary["xlogp"] = props.get("XLogP")  # Lipophilicity
            summary["topological_polar_surface_area"] = props.get("TPSA")
            break
    
    # Chemical classification
    for path, blob in records.items():
        if "/classification/" in path:
            class_tree = blob.get("HierarchicalClassificationTree", {})
            class_node = class_tree.get("ClassificationNode", {})
            
            # Extract hierarchical classification
            cl = class_node.get("ToOne", {})
            levels = []
            while isinstance(cl, dict) and "NodeName" in cl and len(levels) < 5:
                levels.append(cl["NodeName"])
                cl = cl.get("ToOne", {})
            summary["classification"] = " ⭢ ".join(levels) if levels else None
            
            # Extract alternate classifications if available
            summary["pharmacological_class"] = None
            summary["mechanism_of_action"] = None
            if "AlternateNodes" in class_node:
                alt_nodes = class_node.get("AlternateNodes", {}).get("AlternateNode", [])
                if not isinstance(alt_nodes, list):
                    alt_nodes = [alt_nodes]
                
                for node in alt_nodes:
                    category = node.get("CategoryName", "")
                    node_name = node.get("NodeName", "")
                    if "Pharmacologic" in category:
                        summary["pharmacological_class"] = node_name
                    elif "Mechanism" in category:
                        summary["mechanism_of_action"] = node_name
            break
    
    # Enhanced fibrosis-related terms based on research
    _FIBROSIS_TERMS = [
        # Direct fibrosis and cardiac terms
        "fibro", "cardiac", "heart", "cardio", "myocard", 
        
        # Growth factors and signaling pathways critical in fibrosis
        "tgf", "transforming growth factor", "smad", "wnt", "mapk", "nf-kb",
        "gsk3", "ctgf", "pdgf", "fgf", "egf", "igf",
        
        # Cell types and processes involved in fibrosis
        "myofibro", "fibroblast", "epithelial-mesenchymal", "emt",
        "endothelial-mesenchymal", "endmt", "inflamm",
        
        # ECM components and remodeling
        "collagen", "extracellular matrix", "ecm", "mmp", "timp",
        "fibronectin", "laminin", "elastin", "proteoglycan",
        
        # Receptors and signaling molecules important in fibrosis
        "integrin", "angiotensin", "aldosterone", "endothelin", 
        "thrombospondin", "interleukin", "cytokine", "chemokine",
        
        # Epigenetic regulators (important for capturing BRD4 inhibitors)
        "brd4", "brd", "bromodomain", "bet", "epigenetic", "histone",
        "acetyl", "methylation", "chromatin", "hdac", "sirtuin",
        
        # Anti-fibrotic compounds
        "pirfenidone", "nintedanib", "tranilast", "relaxin",
        
        # Cardiomyopathy-related terms
        "hypertrophy", "cardiomyopathy", "heart failure"
    ]
    
    # Fibrosis-related bioassays
    assays = []
    brd4_inhibitor_evidence = False
    anti_fibrotic_evidence = False
    tgf_beta_evidence = False
    
    for path, blob in records.items():
        if "/assaysummary/" in path:
            rows = blob.get("AssayTable", {}).get("Rows", [])
            for row in rows:
                title = row.get("Name", "").lower()
                outcome = row.get("ActivityOutcome", "")
                
                # Check for BRD4 inhibitor evidence
                if ("brd4" in title or "bromodomain" in title or "bet" in title) and outcome == "Active":
                    brd4_inhibitor_evidence = True
                
                # Check for anti-fibrotic evidence
                if any(term in title for term in ["anti-fibrotic", "antifibrotic", "fibrosis inhibit"]) and outcome == "Active":
                    anti_fibrotic_evidence = True
                
                # Check for TGF-β activity
                if ("tgf" in title or "transforming growth factor" in title) and outcome == "Active":
                    tgf_beta_evidence = True
                
                # Include assays related to fibrosis terms
                if any(t in title for t in _FIBROSIS_TERMS):
                    assay_data = {
                        "aid": row.get("AID"),
                        "title": row.get("Name"),
                        "outcome": outcome,
                        "activity_value": row.get("ActivityValue"),
                        "activity_unit": row.get("ActivityUnit"),
                    }
                    
                    # Add assay type if available
                    assay_type = row.get("AssayType")
                    if assay_type:
                        assay_data["assay_type"] = assay_type
                    
                    assays.append(assay_data)
                
                # Limit to reasonable number while prioritizing active results
                if len(assays) >= 15 and outcome != "Active":
                    break
    
    if assays:
        summary["assays"] = assays
    
    # Add detected mechanisms
    detected_mechanisms = {}
    if brd4_inhibitor_evidence:
        detected_mechanisms["BRD4_inhibitor"] = True
    if anti_fibrotic_evidence:
        detected_mechanisms["anti_fibrotic"] = True
    if tgf_beta_evidence:
        detected_mechanisms["tgf_beta_modulator"] = True
    
    if detected_mechanisms:
        summary["detected_mechanisms"] = detected_mechanisms
    
    # Target interactions - particularly important for fibrosis
    targets = []
    for path, blob in records.items():
        if "/target/" in path or "/protein/" in path:
            target_data = blob.get("ProteinTargets", {}).get("Targets", [])
            if not isinstance(target_data, list):
                target_data = [target_data]
                
            for target in target_data:
                target_name = target.get("Name", "").lower() if target.get("Name") else ""
                important_targets = [
                    "tgf", "smad", "integrin", "receptor", "kinase", "brd", 
                    "bromodomain", "hdac", "acetyltransferase", "methyltransferase"
                ]
                if any(t in target_name for t in important_targets):
                    target_info = {
                        "name": target.get("Name"),
                        "id": target.get("ID"),
                        "interaction_type": target.get("InteractionType", "Unknown"),
                    }
                    targets.append(target_info)
                    
                    # Update mechanism info based on targets
                    if "brd4" in target_name or "bromodomain" in target_name:
                        if not "detected_mechanisms" in summary:
                            summary["detected_mechanisms"] = {}
                        summary["detected_mechanisms"]["BRD4_inhibitor"] = True
                    
                    if "tgf" in target_name or "transforming growth factor" in target_name:
                        if not "detected_mechanisms" in summary:
                            summary["detected_mechanisms"] = {}
                        summary["detected_mechanisms"]["tgf_beta_modulator"] = True
    
    if targets:
        summary["targets"] = targets
    
    # Pathways information
    pathways = []
    for path, blob in records.items():
        if "/pathway/" in path:
            pathway_data = blob.get("PathwayList", {}).get("Pathways", [])
            if not isinstance(pathway_data, list):
                pathway_data = [pathway_data]
                
            for pathway in pathway_data:
                pathway_name = pathway.get("Name", "").lower() if pathway.get("Name") else ""
                important_pathways = [
                    "tgf", "smad", "wnt", "mapk", "fibrosis", "cardiac", "brd", 
                    "bromodomain", "inflammatory", "nf-kb"
                ]
                if any(t in pathway_name for t in important_pathways):
                    pathway_info = {
                        "name": pathway.get("Name"),
                        "id": pathway.get("ID"),
                        "source": pathway.get("Source")
                    }
                    pathways.append(pathway_info)
                    
                    # Update mechanism info based on pathways
                    if "fibrosis" in pathway_name:
                        if not "detected_mechanisms" in summary:
                            summary["detected_mechanisms"] = {}
                        summary["detected_mechanisms"]["fibrosis_related"] = True
    
    if pathways:
        summary["pathways"] = pathways
    
    # Literature mentions - search for fibrosis-related terms in title or abstract
    literature_mentions = []
    for path, blob in records.items():
        if "/literature/" in path:
            refs = blob.get("References", [])
            if not isinstance(refs, list):
                refs = [refs]
            
            for ref in refs:
                title = ref.get("Title", "").lower() if ref.get("Title") else ""
                abstract = ref.get("Abstract", "").lower() if ref.get("Abstract") else ""
                
                if any(t in title or t in abstract for t in _FIBROSIS_TERMS):
                    lit_info = {
                        "pmid": ref.get("PMID"),
                        "title": ref.get("Title"),
                        "year": ref.get("Year")
                    }
                    literature_mentions.append(lit_info)
                    
                    # Update mechanism info based on literature
                    if any(t in title or t in abstract for t in ["anti-fibrotic", "antifibrotic", "reduces fibrosis"]):
                        if not "detected_mechanisms" in summary:
                            summary["detected_mechanisms"] = {}
                        summary["detected_mechanisms"]["anti_fibrotic_literature"] = True
    
    if literature_mentions:
        summary["literature_mentions"] = literature_mentions
    
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