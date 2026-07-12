import { NextRequest } from "next/server";

const BACKEND_API_BASE = process.env.BACKEND_API_BASE ?? "http://127.0.0.1:8010";
const BACKEND_API_BASES = [
  ...(process.env.BACKEND_API_BASES ?? "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean),
  BACKEND_API_BASE,
  "http://172.18.0.1:8010",
  "http://172.17.0.1:8010",
  "http://host.docker.internal:8010",
  "http://127.0.0.1:8010",
].filter((item, index, items) => items.indexOf(item) === index);

const proxyRequest = async (request: NextRequest, path: string[]) => {
  const isBodyless = request.method === "GET" || request.method === "HEAD";
  const body = isBodyless ? undefined : await request.arrayBuffer();
  const errors: string[] = [];

  for (const baseUrl of BACKEND_API_BASES) {
    const target = new URL(`/api/${path.join("/")}`, baseUrl);
    target.search = request.nextUrl.search;

    try {
      const response = await fetch(target, {
        method: request.method,
        headers: {
          "content-type": request.headers.get("content-type") ?? "application/json",
        },
        // Forward the raw bytes; decoding as text corrupts binary uploads.
        body,
        cache: "no-store",
      });

      return new Response(response.body, {
        status: response.status,
        headers: {
          "content-type": response.headers.get("content-type") ?? "application/json",
        },
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : "Unknown proxy error";
      errors.push(`${baseUrl}: ${message}`);
    }
  }

  return Response.json(
    { detail: `Backend API is not reachable. Tried: ${errors.join("; ") || BACKEND_API_BASE}` },
    { status: 502 },
  );
};

export const GET = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const POST = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const PATCH = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const DELETE = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));
