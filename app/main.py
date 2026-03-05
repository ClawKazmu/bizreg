from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import Optional
import logging
import os
from pathlib import Path
from dotenv import load_dotenv
from datetime import datetime, timezone
import json
from .scrapers import DTIBNRSScraper, SECCRSScraper, ScraperError

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("bizreg")

app = FastAPI(title="Philippine Business Registration Checker", version="0.2.0")

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Rate limiting configuration
FREE_TIER_LIMIT = int(os.getenv("FREE_TIER_LIMIT", "20"))  # checks per month
RATE_LIMIT_DB = Path(os.getenv("RATE_LIMIT_DB", "data/rate_limits.json"))

class RateLimiter:
    """Simple file-based rate limiter with monthly reset."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        """Ensure data directory and DB file exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.db_path.exists():
            self._save({})

    def _load(self) -> dict:
        """Load rate limit data from file."""
        try:
            with open(self.db_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return {}

    def _save(self, data: dict):
        """Save rate limit data to file."""
        with open(self.db_path, 'w') as f:
            json.dump(data, f, indent=2)

    def get_current_month_key(self) -> str:
        """Return YYYY-MM string for current month."""
        return datetime.now(timezone.utc).strftime("%Y-%m")

    def check_and_increment(self, user_id: str) -> dict:
        """
        Check if user has quota remaining and increment count.
        Returns dict with 'allowed' (bool), 'remaining' (int), 'reset_at' (str).
        """
        if not user_id:
            return {
                "allowed": False,
                "remaining": 0,
                "reset_at": None,
                "error": "User identifier required (X-User-Email or X-API-Key header)"
            }

        data = self._load()
        current_month = self.get_current_month_key()
        user_key = f"user:{user_id}"

        # Get or initialize user record
        if user_key not in data or data[user_key].get("month") != current_month:
            # New user or new month - reset counter
            data[user_key] = {
                "count": 0,
                "month": current_month,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }

        user_data = data[user_key]
        remaining = FREE_TIER_LIMIT - user_data["count"]

        if remaining <= 0:
            # Calculate next reset (first day of next month)
            now = datetime.now(timezone.utc)
            if now.month == 12:
                next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
            else:
                next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

            return {
                "allowed": False,
                "remaining": 0,
                "reset_at": next_month.isoformat(),
                "used": user_data["count"],
                "limit": FREE_TIER_LIMIT
            }

        # Increment and save
        user_data["count"] += 1
        user_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        data[user_key] = user_data
        self._save(data)

        # Calculate next reset
        now = datetime.now(timezone.utc)
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

        return {
            "allowed": True,
            "remaining": remaining - 1,
            "reset_at": next_month.isoformat(),
            "used": user_data["count"],
            "limit": FREE_TIER_LIMIT
        }

# Initialize rate limiter
rate_limiter = RateLimiter(RATE_LIMIT_DB)

async def get_user_identifier(
    request: Request,
    x_user_email: Optional[str] = Header(None, alias="X-User-Email"),
    x_api_key: Optional[str] = Header(None, alias="X-API-Key")
) -> str:
    """
    Extract user identifier from headers.
    Priority: X-User-Email > X-API-Key
    """
    if x_user_email:
        return x_user_email.strip().lower()
    elif x_api_key:
        return x_api_key.strip()
    else:
        # For unauthenticated requests, use IP address as fallback
        # (not ideal but provides some tracking)
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

class RateLimitError(Exception):
    """Raised when rate limit is exceeded."""
    def __init__(self, remaining: int, reset_at: str, used: int, limit: int):
        self.remaining = remaining
        self.reset_at = reset_at
        self.used = used
        self.limit = limit
        super().__init__(f"Rate limit exceeded. Used {used}/{limit}")

async def enforce_rate_limit(user_id: str) -> dict:
    """
    Enforce rate limit for check-name endpoint.
    Raises RateLimitError if limit exceeded.
    """
    result = rate_limiter.check_and_increment(user_id)

    if not result["allowed"]:
        raise RateLimitError(
            remaining=result["remaining"],
            reset_at=result["reset_at"],
            used=result["used"],
            limit=result["limit"]
        )

    return result

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
async def check_name(
    req: NameCheckRequest,
    request: Request,
    user_id: str = Depends(get_user_identifier)
):
    """
    Check business name availability across DTI and SEC using live scrapers.
    Free tier: 20 checks/month. Provide X-User-Email or X-API-Key header.
    Premium: Unlimited checks. Contact for upgrade.
    """
    # Enforce rate limit
    try:
        rate_info = await enforce_rate_limit(user_id)
        logger.info(f"Rate limit check passed for user {user_id}. Remaining: {rate_info['remaining']}")
    except RateLimitError as e:
        logger.warning(f"Rate limit exceeded for user {user_id}: {e}")
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limit_exceeded",
                "message": "Free tier monthly limit reached",
                "used": e.used,
                "limit": e.limit,
                "remaining": 0,
                "reset_at": e.reset_at,
                "upgrade_url": "https://bizreg.ph/upgrade",  # TODO: Update with actual URL
                "upgrade_message": "Upgrade to Premium for unlimited checks and priority support."
            }
        )
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

@app.get("/api/rate-limit")
async def get_rate_limit_status(
    request: Request,
    user_id: str = Depends(get_user_identifier)
):
    """
    Get current rate limit status for the calling user.
    """
    data = rate_limiter._load()
    current_month = rate_limiter.get_current_month_key()
    user_key = f"user:{user_id}"

    if user_key in data and data[user_key].get("month") == current_month:
        user_data = data[user_key]
        used = user_data["count"]
        remaining = max(0, FREE_TIER_LIMIT - used)

        # Calculate next reset
        now = datetime.now(timezone.utc)
        if now.month == 12:
            next_month = datetime(now.year + 1, 1, 1, tzinfo=timezone.utc)
        else:
            next_month = datetime(now.year, now.month + 1, 1, tzinfo=timezone.utc)

        return {
            "user_id": user_id,
            "limit": FREE_TIER_LIMIT,
            "used": used,
            "remaining": remaining,
            "reset_at": next_month.isoformat(),
            "status": "exceeded" if remaining <= 0 else "active"
        }
    else:
        # No usage yet this month
        return {
            "user_id": user_id,
            "limit": FREE_TIER_LIMIT,
            "used": 0,
            "remaining": FREE_TIER_LIMIT,
            "reset_at": None,
            "status": "active"
        }

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
