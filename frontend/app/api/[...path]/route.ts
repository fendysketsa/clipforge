import { NextRequest } from "next/server";
import { createBackendProxy } from "../../../lib/backendProxy";

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

const proxy = createBackendProxy({
  backendBases: BACKEND_API_BASES,
  browserApiBase: process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8010",
});
const proxyRequest = (request: NextRequest, path: string[]) => proxy(request, `/api/${path.join("/")}`);

export const GET = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const POST = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const PATCH = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));

export const DELETE = (request: NextRequest, context: { params: Promise<{ path: string[] }> }) =>
  context.params.then(({ path }) => proxyRequest(request, path));
