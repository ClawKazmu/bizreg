# Philippine Business Registration Checker

Unified web app to check business name availability across DTI and SEC, get required registrations, estimate fees and processing times.

## Features (MVP)
- DTI and SEC name search (simultaneous)
- Business type advisor (sole proprietorship, corporation, cooperative)
- National fee calculator
- Step-by-step checklist (PDF download)

## Tech
- FastAPI (Python)
- PostgreSQL (optional for MVP)
- Playwright for scraping DTI/SEC

## Quickstart
```bash
cp .env.example .env
# edit .env with any needed config
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open http://localhost:8000/docs for API.

## Endpoints
- `GET /` – health
- `POST /api/check-name` – check name across DTI/SEC
- `GET /api/advisor` – business type recommendations
- `GET /api/fees` – fee calculator

## Project status
Early MVP. Data sources: DTI BNRS, SEC CRS (scraping).
