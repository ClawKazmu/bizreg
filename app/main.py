from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
import os
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("bizreg")

app = FastAPI(title="Philippine Business Registration Checker", version="0.1.0")

class NameCheckRequest(BaseModel):
    business_name: str
    include_dti: bool = True
    include_sec: bool = True

class NameCheckResponse(BaseModel):
    name: str
    dti_available: Optional[bool] = None
    sec_available: Optional[bool] = None
    notes: str = ""

@app.get("/")
def health():
    return {"status": "ok", "service": "bizreg"}

@app.post("/api/check-name", response_model=NameCheckResponse)
async def check_name(req: NameCheckRequest):
    """
    Check business name availability across DTI and SEC.
    This is a stub; implement scrapers later.
    """
    logger.info(f"Checking name: {req.business_name}")
    # Placeholder: always return available
    return NameCheckResponse(
        name=req.business_name,
        dti_available=True if req.include_dti else None,
        sec_available=True if req.include_sec else None,
        notes="This is a mock response. Implement DTI/SEC scrapers to get real data."
    )

@app.get("/api/advisor")
def advisor(business_type: Optional[str] = None, sole_proprietor: bool = False, corporation: bool = False):
    """
    Recommend required registrations based on business type.
    """
    # Stub
    return {
        "business_type": business_type or "sole_proprietorship",
        "required_agencies": ["DTI", "LGU", "BIR"],
        "estimated_cost_peso": 5000,
        "estimated_days": 14,
        "notes": "Stub data; will be replaced by rule engine."
    }

@app.get("/api/fees")
def fees(agency: str = "DTI", business_type: str = "sole_proprietorship"):
    """
    Return fee schedule for a given agency and business type.
    """
    # Stub
    return {
        "agency": agency,
        "business_type": business_type,
        "fees": [
            {"item": "Registration", "amount": 1000},
            {"item": "Permit", "amount": 2000},
            {"item": "Misc", "amount": 500}
        ],
        "total": 3500
    }
