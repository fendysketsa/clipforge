# ClipForge frontend

Next.js UI untuk menjalankan backend clipper lokal.

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

Buka:

```text
http://127.0.0.1:3000
```
