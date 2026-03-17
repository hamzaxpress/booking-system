# LogisticsPro — Setup & Run (Windows / PowerShell)

This project has two parts:
- Backend API (FastAPI) on port `8000`
- Frontend static pages served on port `5500`

## Prerequisites
- Python 3.12.x recommended (Python 3.13 works only with newer SQLAlchemy)
- pip

## 1) Backend (API)
From the project root:

```powershell
cd backend
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

Keep this terminal running.

## 2) Frontend (Static Server)
Open a new terminal at the project root:

```powershell
python -m http.server 5500
```

Then open in your browser:

- Staff Portal: `http://localhost:5500/frontend/logistics_staff_portal.html`
- Public Tracking: `http://localhost:5500/frontend/logistics_tracking_page.html`

## Demo Credentials
- Admin: `admin@logistics.com` / `Admin@123`
- Staff: `staff@logistics.com` / `Staff@123`

## Notes
- If login fails with CORS errors, make sure the backend is running on `http://localhost:8000`.
- If you move the project to another PC, re-run the steps above.
