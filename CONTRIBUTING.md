# Contributing

Thanks for improving Fendy Clipper.

## Local setup

Backend:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8010
```

Frontend:

```powershell
cd frontend
npm install
npm run dev
```

Open `http://127.0.0.1:3000`.

## Checks

Run these before sending a change:

```powershell
py -m py_compile backend\api.py backend\clipper.py
cd frontend
npm run build
```

## Pull requests

- Keep changes focused.
- Include screenshots or short notes for UI changes.
- Mention tested commands.
- Do not commit generated clips, local outputs, `.env` files, or `jobs.json`.

## Good first issues

- Better clip scoring.
- Queue controls and job cancellation.
- Auth/rate limiting for server deployments.
- Export presets for TikTok, Reels, and Shorts.
- Better transcript cleanup for more languages.
