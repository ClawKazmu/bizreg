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
| `/api/rate-limit` | GET | Get current rate limit status for the caller |
| `/api/advisor` | GET | Business type recommendations and checklist |
| `/api/fees` | GET | Fee calculator for agencies (DTI, SEC, BIR, LGU) |
| `/ui` | GET | Frontend interface (HTML) |
| `/docs` | GET | Interactive API docs (Swagger) |

### Rate Limiting

- **Free tier**: 20 checks per month per user
- **Tracking**: By `X-User-Email` header or `X-API-Key` (for programmatic access)
- **When limit exceeded**: HTTP 429 response with reset information and upgrade options
- **Reset**: First day of each month (UTC)

#### Request Headers

To track your usage and avoid sharing limits with other users, include one of:

```http
X-User-Email: your-email@example.com
# or
X-API-Key: your-api-key
```

If no headers are provided, usage is tracked by IP address (less reliable, may reset on network changes).

#### Rate Limit Exceeded Response

```json
{
  "error": "rate_limit_exceeded",
  "message": "Free tier monthly limit reached",
  "used": 20,
  "limit": 20,
  "remaining": 0,
  "reset_at": "2025-04-01T00:00:00Z",
  "upgrade_url": "https://bizreg.ph/upgrade",
  "upgrade_message": "Upgrade to Premium for unlimited checks and priority support."
}
```

#### Premium Tier

Unlimited monthly checks, priority support, and higher rate limits on scrapers.
Contact [premium@bizreg.ph](mailto:premium@bizreg.ph) or visit [bizreg.ph/upgrade](https://bizreg.ph/upgrade).

### Check Name Request Example

```bash
curl -X POST "http://localhost:8000/api/check-name" \
  -H "Content-Type: application/json" \
  -H "X-User-Email: user@example.com" \
  -d '{
    "business_name": "Mabuhay Coffee",
    "include_dti": true,
    "include_sec": false,
    "dti_scope": "national"
  }'
```

### Rate Limit Status Example

```bash
curl -X GET "http://localhost:8000/api/rate-limit" \
  -H "X-User-Email: user@example.com"
```

Response:

```json
{
  "user_id": "user@example.com",
  "limit": 20,
  "used": 5,
  "remaining": 15,
  "reset_at": "2025-04-01T00:00:00Z",
  "status": "active"
}
```

### Check Name Response Example

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
