import sys
import json
from pathlib import Path
from langchain_openai import ChatOpenAI

sys.path.append("..") 
from drug_fibrosis_agent import evaluate_drug

def main():
    print("Evaluating Colchicine for cardiac fibrosis effects...")
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
    result = evaluate_drug("givinostat", llm=llm)

    print("\nEvaluation Results:")
    print("-" * 50)
    print(f"Conclusion: {result['conclusion']}")
    print(f"Relevance:  {result['relevance']}/100")
    print(f"Confidence: {result['confidence']}/100")
    print("-" * 50)
    print("Rationale:")
    print(result['rationale'])
    print("-" * 50)
    
    output_path = Path(__file__).parent / "givinostat_evaluation.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
    
    print(f"\nResults saved to {output_path}")
    
    print("\nAPI Requests:")
    for i, path in enumerate(result['tool_trace'], 1):
        print(f"{i}. {path}")

if __name__ == "__main__":
    main()