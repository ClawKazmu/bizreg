# Philippine Business Registration Checker

Unified web app to check business name availability across DTI and SEC, get required registrations, estimate fees and processing times.

## Features
- ✅ DTI and SEC name search (live scraping)
- Business type advisor (sole proprietorship, corporation, cooperative)
- National fee calculator based on official government schedules
- Step-by-step checklist
- Interactive frontend UI

## Tech Stack
- **Backend**: FastAPI (Python 3.11+)
- **Frontend**: Plain HTML + JavaScript (no build step)
- **Scraping**: Playwright (headless Chromium)
- **Deployment**: Render.com (or any container host)

## Quickstart

```bash
# Clone and setup
cp .env.example .env
pip install -r requirements.txt
playwright install chromium

# Run the server
uvicorn app.main:app --reload

# Open in browser
# API docs: http://localhost:8000/docs
# Frontend UI: http://localhost:8000/ui
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/api/check-name` | POST | Check name across DTI/SEC (live scrapers) |
| `/api/advisor` | GET | Business type recommendations and checklist |
| `/api/fees` | GET | Fee calculator for agencies (DTI, SEC, BIR, LGU) |
| `/ui` | GET | Frontend interface (HTML) |
| `/docs` | GET | Interactive API docs (Swagger) |

### Check Name Request Example

```bash
curl -X POST "http://localhost:8000/api/check-name" \
  -H "Content-Type: application/json" \
  -d '{
    "business_name": "Mabuhay Coffee",
    "include_dti": true,
    "include_sec": false,
    "dti_scope": "national"
  }'
```

### Response Example

```json
{
  "name": "Mabuhay Coffee",
  "dti_available": true,
  "sec_available": null,
  "dti_message": "Business name appears to be available",
  "sec_message": null,
  "notes": "DTI: Business name appears to be available"
}
```

## Deployment on Render

1. Push this repository to GitHub
2. Create a new Web Service on Render
3. Connect your repository
4. Render will auto-detect `render.yaml` and configure:
   - Build: `pip install -r requirements.txt && playwright install chromium && playwright install-deps`
   - Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Set environment variables if needed (LOG_LEVEL, SCRAPER_DELAY)
6. Deploy!

The service will be available at: `https://bizreg-api.onrender.com`

### Notes for Production
- Free tier may sleep after inactivity. Use a paid plan for always-on.
- Add DATABASE_URL to .env if using PostgreSQL for caching/rate limiting.
- Consider adding API key authentication for public deployment.
- Adjust `SCRAPER_DELAY` to be polite to government servers (default 1 second).

## Project Structure

```
bizreg/
├── app/
│   ├── main.py          # FastAPI app and routes
│   ├── scrapers.py      # DTI and SEC scrapers (Playwright)
│   ├── static/
│   │   └── index.html   # Frontend UI
│   └── __init__.py
├── requirements.txt
├── render.yaml
├── .env.example
└── README.md
```

## Validating Code

Check that all Python files compile:

```bash
python -m py_compile app/main.py
python -m py_compile app/scrapers.py
```

## Disclaimer

This tool provides estimates and checks for informational purposes only. Always verify with official government sources and consult with a registered business consultant. The scrapers interact with live government systems, which may change without notice. We respect rate limits and terms of service—please do as well.

## License

MIT (or your preferred license)
