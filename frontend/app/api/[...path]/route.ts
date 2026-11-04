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

let backendSelection: Promise<string> | null = null;
let backendSelectedAt = 0;

const selectBackend = () => {
  if (!backendSelection || Date.now() - backendSelectedAt > 30_000) {
    backendSelectedAt = Date.now();
    backendSelection = Promise.any(BACKEND_API_BASES.map(async (baseUrl) => {
      const response = await fetch(new URL("/api/health", baseUrl), {
        cache: "no-store",
        signal: AbortSignal.timeout(2_500),
      });
      if (!response.ok) throw new Error(`Backend health returned ${response.status}`);
      return baseUrl;
    })).catch((error) => {
      backendSelection = null;
      throw error;
    });
  }
  return backendSelection;
};

const proxyRequest = async (request: NextRequest, path: string[]) => {
  const isBodyless = request.method === "GET" || request.method === "HEAD";
  const body = isBodyless ? undefined : await request.arrayBuffer();
  try {
    // Probe candidates concurrently with a short deadline. An obsolete Docker
    // bridge must not stall every queue refresh before trying the healthy host.
    const baseUrl = await selectBackend();
    const target = new URL(`/api/${path.join("/")}`, baseUrl);
    target.search = request.nextUrl.search;

    const response = await fetch(target, {
      method: request.method,
      headers: {
        "content-type": request.headers.get("content-type") ?? "application/json",
      },
      // Forward the raw bytes; decoding as text corrupts binary uploads.
      body,
      cache: "no-store",
      ...(isBodyless ? { signal: AbortSignal.timeout(15_000) } : {}),
    });

    return new Response(response.body, {
      status: response.status,
      headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
      },
    });
  } catch (error) {
    backendSelection = null;
    const message = error instanceof Error ? error.message : "Unknown proxy error";
    // A failed POST may already have reached the server. Do not replay a
    // mutation against another address and create duplicate jobs/uploads.
    return Response.json({ detail: `Backend API is not reachable: ${message}` }, { status: 502 });
  }
};

export const GET = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const POST = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const PATCH = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const DELETE = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));
