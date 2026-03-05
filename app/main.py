from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from .scrapers import DTIBNRSScraper, SECCRSScraper, ScraperError

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("bizreg")

app = FastAPI(title="Philippine Business Registration Checker", version="0.2.0")

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

class NameCheckRequest(BaseModel):
    business_name: str
    include_dti: bool = True
    include_sec: bool = True
    dti_scope: str = "national"  # barangay, city, regional, national
    sec_company_type: str = "corporation"  # corporation, partnership, foreign

class NameCheckResponse(BaseModel):
    name: str
    dti_available: Optional[bool] = None
    sec_available: Optional[bool] = None
    dti_message: Optional[str] = None
    sec_message: Optional[str] = None
    notes: str = ""

@app.get("/")
def health():
    return {"status": "ok", "service": "bizreg"}

@app.get("/ui", response_class=HTMLResponse)
async def serve_ui():
    """Serve the frontend UI"""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(str(index_path))
    return HTMLResponse(content="<h1>Frontend not found. Please ensure static/index.html exists.</h1>", status_code=404)

@app.post("/api/check-name", response_model=NameCheckResponse)
async def check_name(req: NameCheckRequest):
    """
    Check business name availability across DTI and SEC using live scrapers.
    """
    logger.info(f"Checking name: {req.business_name}")
    response = NameCheckResponse(name=req.business_name)

    # Check DTI if requested
    if req.include_dti:
        try:
            dti_result = await DTIBNRSScraper().check_name(req.business_name, req.dti_scope)
            response.dti_available = dti_result["available"]
            response.dti_message = dti_result["message"]
        except ScraperError as e:
            logger.error(f"DTI check failed: {e}")
            response.dti_message = f"DTI check failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected DTI error: {e}")
            response.dti_message = f"Unexpected error checking DTI: {str(e)}"

    # Check SEC if requested
    if req.include_sec:
        try:
            sec_result = await SECCRSScraper().check_name(req.business_name, req.sec_company_type)
            response.sec_available = sec_result["available"]
            response.sec_message = sec_result["message"]
        except ScraperError as e:
            logger.error(f"SEC check failed: {e}")
            response.sec_message = f"SEC check failed: {str(e)}"
        except Exception as e:
            logger.error(f"Unexpected SEC error: {e}")
            response.sec_message = f"Unexpected error checking SEC: {str(e)}"

    # Build notes
    notes = []
    if response.dti_message:
        notes.append(f"DTI: {response.dti_message}")
    if response.sec_message:
        notes.append(f"SEC: {response.sec_message}")
    response.notes = " | ".join(notes) if notes else "Name check completed"

    return response

@app.get("/api/advisor")
def advisor(business_type: Optional[str] = None, sole_proprietor: bool = False, corporation: bool = False):
    """
    Recommend required registrations based on business type.
    """
    # Determine business type from parameters
    if corporation:
        biz_type = "corporation"
    elif sole_proprietor:
        biz_type = "sole_proprietorship"
    else:
        biz_type = business_type or "sole_proprietorship"

    # Define requirements based on business type
    requirements = {
        "sole_proprietorship": {
            "agencies": ["DTI", "LGU (Mayor's Permit)", "BIR", "SSS/PhilHealth/Pag-IBIG"],
            "estimated_cost_peso": 5000,
            "estimated_days": 14,
            "steps": [
                "Reserve business name with DTI",
                "Secure Barangay Clearance",
                "Obtain Mayor's Permit from LGU",
                "Register with BIR for TIN and authority to print receipts",
                "Register with SSS, PhilHealth, and Pag-IBIG if hiring employees"
            ]
        },
        "corporation": {
            "agencies": ["SEC", "LGU", "BIR", "SSS/PhilHealth/Pag-IBIG"],
            "estimated_cost_peso": 15000,
            "estimated_days": 30,
            "steps": [
                "Reserve company name with SEC",
                "Prepare and notarize Articles of Incorporation and By-laws",
                "File incorporation with SEC",
                "Obtain Barangay Clearance and Mayor's Permit",
                "Register with BIR",
                "Register with SSS, PhilHealth, and Pag-IBIG"
            ]
        },
        "partnership": {
            "agencies": ["SEC", "LGU", "BIR", "SSS/PhilHealth/Pag-IBIG"],
            "estimated_cost_peso": 12000,
            "estimated_days": 25,
            "steps": [
                "Reserve partnership name with SEC",
                "Prepare and notarize Partnership Agreement",
                "File registration with SEC",
                "Secure LGU permits",
                "Register with BIR",
                "Register with social security systems"
            ]
        },
        "cooperative": {
            "agencies": ["SEC (Cooperative Development Authority)", "LGU", "BIR", "SSS/PhilHealth/Pag-IBIG"],
            "estimated_cost_peso": 10000,
            "estimated_days": 35,
            "steps": [
                "Conduct pre-registration seminar",
                "Reserve cooperative name",
                "Prepare Articles of Cooperation and By-laws",
                "Register with SEC/CDA",
                "Obtain LGU permits",
                "Register with BIR",
                "Comply with cooperative regulations"
            ]
        }
    }

    if biz_type not in requirements:
        biz_type = "sole_proprietorship"

    result = requirements[biz_type].copy()
    result["business_type"] = biz_type
    result["notes"] = "Estimates vary by location and specific circumstances. Consult a professional for precise figures."

    return result

@app.get("/api/fees")
def fees(agency: str = "DTI", business_type: str = "sole_proprietorship", include_sec: bool = False):
    """
    Return official fee schedule for a given agency and business type.
    Based on latest government fee structures as of 2024.
    """
    # DTI Fees (from DTI BNRS fee schedule)
    dti_fees = {
        "sole_proprietorship": {
            "Registration fee": {
                "barangay": 200,
                "city": 500,
                "regional": 1000,
                "national": 2000
            },
            "Name reservation": 100,
            "Certificates": 150,
            "Processing fee": 300
        }
    }

    # SEC Fees (from SEC fee schedule - Title III, SEC Memorandum Circulars)
    sec_fees = {
        "corporation": {
            "Name reservation": 100,
            "Registration fee (with 25% TV tax)": 2500,  # For domestic corporations with PAUW of 200k
            "Articles of Incorporation": 2000,
            "By-laws": 1000,
            "Legal Research Fee": 30,
            "SEC Clearance for permits": 500
        },
        "partnership": {
            "Name reservation": 100,
            "Registration fee (with 25% TV tax)": 2000,
            "Partnership Agreement registration": 1500,
            "Legal Research Fee": 30,
            "SEC Clearance": 500
        },
        "foreign corporation": {
            "Name reservation": 200,
            "Registration fee": 5000,
            "License to do business": 3000,
            "Legal Research Fee": 50
        }
    }

    # Additional fees
    bir_estimated = {
        "sole_proprietorship": 1500,  # BIR registration, print receipts, etc.
        "corporation": 2500,
        "partnership": 2000
    }

    lgu_estimated = {
        "sole_proprietorship": 2000,  # Mayor's permit, business plate, etc.
        "corporation": 3500,
        "partnership": 3000
    }

    # Build response
    result = {
        "agency": agency,
        "business_type": business_type,
        "fees": [],
        "total": 0
    }

    if agency.upper() == "DTI":
        if business_type in dti_fees:
            scope = "national"  # default, could be parameterized
            fees_dict = dti_fees[business_type]
            for item, amount in fees_dict.items():
                if isinstance(amount, dict):
                    # Scope-dependent fee
                    actual = amount.get(scope, 0)
                else:
                    actual = amount
                result["fees"].append({"item": item, "amount": actual})
                result["total"] += actual
        else:
            result["fees"] = [{"item": "Contact DTI for specific fee schedule", "amount": 0}]
    elif agency.upper() == "SEC":
        if business_type in sec_fees:
            fees_dict = sec_fees[business_type]
            for item, amount in fees_dict.items():
                result["fees"].append({"item": item, "amount": amount})
                result["total"] += amount
        else:
            result["fees"] = [{"item": "Contact SEC for specific fee schedule", "amount": 0}]
    else:
        # Return estimates for other agencies
        if agency.upper() == "BIR":
            result["fees"] = [{"item": "Registration, printing receipts, authority to use receipts", "amount": bir_estimated.get(business_type, 2000)}]
            result["total"] = bir_estimated.get(business_type, 2000)
        elif agency.upper() == "LGU":
            result["fees"] = [{"item": "Mayor's Permit, Business Plate, Sanitary Permit, etc.", "amount": lgu_estimated.get(business_type, 2500)}]
            result["total"] = lgu_estimated.get(business_type, 2500)
        else:
            result["fees"] = [{"item": f"Unknown agency: {agency}", "amount": 0}]

    result["total"] = round(result["total"], 2)
    return result
