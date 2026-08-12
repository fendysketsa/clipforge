# Security

Fendy Clipper is designed for local-first use.

## Public deployments

Do not expose the backend to the public internet without protection. The API accepts user-provided URLs and starts CPU-heavy download/transcription/render jobs. Public access can cause:

- Server-side request forgery risk from arbitrary URLs.
- Disk, CPU, and bandwidth abuse.
- Unwanted processing of copyrighted or private content.

Use authentication, rate limits, request validation, job quotas, and output cleanup before running a public service.

## Reporting issues

Open a private security advisory if your hosting platform supports it. Otherwise, contact the maintainer privately before publishing exploit details.
