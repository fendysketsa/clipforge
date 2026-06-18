# ClipForge

ClipForge turns long YouTube videos into ready-to-post vertical clips with transcription, subtitles, and smart crop options.

## Docker

Copy the Docker env example, then adjust the public backend URL for your server:

```powershell
Copy-Item .env.docker.example .env
```

For local Docker usage, the defaults are enough:

```env
FRONTEND_PORT=3000
BACKEND_PORT=8010
NEXT_PUBLIC_API_BASE=http://localhost:8010
```

On a server, `NEXT_PUBLIC_API_BASE` must be the browser-accessible backend URL, for example:

```env
NEXT_PUBLIC_API_BASE=https://api.your-domain.com
```

Build and run:

```powershell
docker compose --env-file .env up -d --build
```

Services:

```text
frontend: http://localhost:3000
backend:  http://localhost:8010
```

Persistent local data:

```text
backend/outputs -> /app/outputs
backend/jobs.json -> /app/jobs.json
```
