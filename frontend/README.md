# Fendy Clipper Frontend

Next.js UI for running the local Fendy Clipper backend.

## Setup

```powershell
npm install
```

## Run

Pastikan backend API sudah jalan:

```powershell
cd ..\backend
.\.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8010
```

Lalu jalankan frontend:

```powershell
npm run dev
```

Open:

```text
http://127.0.0.1:3000
```

## Environment

Copy `.env.example` when needed:

```powershell
Copy-Item .env.example .env
```

`NEXT_PUBLIC_API_BASE` must point to the browser-accessible backend URL for generated video files.

The app proxies API requests through `/api/[...path]`, using `BACKEND_API_BASE` on the server side.
