# Deployment

The user requires this exact standard deployment command for this repository:

```bash
sudo docker-compose --env-file .env up -d --build --force-recreate backend frontend telegram-bot
```

Integrate feature installation, source verification and readiness checks into
the normal Dockerfiles, Compose configuration and service startup. Do not
require or recommend a separate activation script or a different deployment
command. Preserve persisted operator settings, publication holds and remote
upload identity across rebuilds. Verify the running services before claiming
deployment success; a build or a prepared command alone is not activation.
