from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import os
from litellm import Router
from dotenv import load_dotenv
import json
from datetime import datetime
import logging
from drug_fibrosis_agent.agent import evaluate_drug

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from current directory
load_dotenv(".env")

# Initialize FastAPI app
app = FastAPI()

# Add CORS middleware with more specific configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://birdhouse-omega.vercel.app"],  # Frontend URL
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicitly list allowed methods
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=600,  # Cache preflight requests for 10 minutes
)

# Modal Configuration (Primary)
MODAL_API_KEY = os.getenv("MODAL_API_KEY")
if not MODAL_API_KEY:
    raise ValueError("MODAL_API_KEY not found in environment variables")

# Modal pricing (per 1M tokens)
MODAL_INPUT_COST_PER_MILLION = 0.25  # $0.25 per 1M input tokens
MODAL_OUTPUT_COST_PER_MILLION = 0.25  # $0.25 per 1M output tokens

MODAL_CONFIG = {
    "model_list": [
        {
            "model_name": "llama3.1-modal",
            "litellm_params": {
                "model": "hosted_vllm/neuralmagic/Meta-Llama-3.1-8B-Instruct-quantized.w4a16",
                "api_base": "https://rsk119--birdhouse-backend-vllm-serve.modal.run/v1",
                "api_key": MODAL_API_KEY
            },
        }
    ]
}
MODAL_MODEL_NAME = "llama3.1-modal"

# OpenAI Configuration (Fallback)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    OPENAI_CONFIG = {
        "model_list": [
            {
                "model_name": "gpt-4o-mini",
                "litellm_params": {
                    "model": "gpt-4o-mini",
                    "api_key": OPENAI_API_KEY,
                },
            }
        ]
    }
    OPENAI_MODEL_NAME = "gpt-4o-mini"

# Initialize routers with cost tracking
modal_router = Router(model_list=MODAL_CONFIG["model_list"], set_verbose=True)
if OPENAI_API_KEY:
    openai_router = Router(model_list=OPENAI_CONFIG["model_list"], set_verbose=True)

class Message(BaseModel):
    role: str
    content: str

class CompletionRequest(BaseModel):
    messages: List[Message]

class CostResponse(BaseModel):
    cost: float
    model: str
    timestamp: str
    usage: Dict[str, int]

class DrugAnalysisRequest(BaseModel):
    drug_name: str

def calculate_modal_cost(usage: Dict[str, int]) -> float:
    """Calculate cost based on Modal's pricing model."""
    input_cost = (usage.get("prompt_tokens", 0) / 1_000_000) * MODAL_INPUT_COST_PER_MILLION
    output_cost = (usage.get("completion_tokens", 0) / 1_000_000) * MODAL_OUTPUT_COST_PER_MILLION
    return input_cost + output_cost

def log_cost_info(response: Any, model_name: str):
    """Log cost information from the response."""
    try:
        # Calculate cost based on usage for Modal
        cost = calculate_modal_cost(response.usage)
        usage = response.usage
        timestamp = datetime.now().isoformat()
        
        cost_info = {
            "cost": cost,
            "model": model_name,
            "timestamp": timestamp,
            "usage": {
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens
            }
        }
        
        logger.info(f"Cost information: {json.dumps(cost_info, indent=2)}")
        return cost_info
    except Exception as e:
        logger.error(f"Error logging cost info: {str(e)}")
        return None

@app.post("/completion")
async def get_completion(request: CompletionRequest):
    """Default endpoint that uses Modal's model"""
    try:
        response = await modal_router.acompletion(
            model=MODAL_MODEL_NAME,
            messages=[{"role": msg.role, "content": msg.content} for msg in request.messages],
        )
        cost_info = log_cost_info(response, MODAL_MODEL_NAME)
        return {
            "response": response,
            "cost_info": cost_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/modal/completion")
async def get_modal_completion(request: CompletionRequest):
    """Explicit Modal endpoint"""
    try:
        response = await modal_router.acompletion(
            model=MODAL_MODEL_NAME,
            messages=[{"role": msg.role, "content": msg.content} for msg in request.messages],
        )
        cost_info = log_cost_info(response, MODAL_MODEL_NAME)
        return {
            "response": response,
            "cost_info": cost_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/openai/completion")
async def get_openai_completion(request: CompletionRequest):
    """OpenAI fallback endpoint"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI service not configured")
    try:
        response = await openai_router.acompletion(
            model=OPENAI_MODEL_NAME,
            messages=[{"role": msg.role, "content": msg.content} for msg in request.messages],
        )
        cost_info = log_cost_info(response, OPENAI_MODEL_NAME)
        return {
            "response": response,
            "cost_info": cost_info
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/analyze_fibrosis")
async def analyze_fibrosis(request: DrugAnalysisRequest):
    """Analyze a drug's effect on cardiac fibrosis using LangChain agent"""
    try:
        result = evaluate_drug(request.drug_name)
        return {
            "conclusion": result["conclusion"],
            "rationale": result["rationale"],
            "tool_trace": result["tool_trace"],
            "relevance": result["relevance"],
            "confidence": result["confidence"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 