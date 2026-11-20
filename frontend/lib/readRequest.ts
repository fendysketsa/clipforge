/** Share only simultaneous reads. Finished/error responses are never cached. */
export function createReadRequest(fetcher: typeof fetch) {
  const active = new Map<string, Promise<unknown>>();
  return function read<T>(url: string, errorMessage: string, timeoutMs = 15_000): Promise<T> {
    const pending = active.get(url);
    if (pending) return pending as Promise<T>;
    const request = Promise.resolve().then(async () => {
      try {
        const response = await fetcher(url, {
          cache: "no-store", signal: AbortSignal.timeout(timeoutMs),
        });
        if (!response.ok) {
          const payload = await response.json().catch(() => null) as { detail?: unknown } | null;
          throw new Error(typeof payload?.detail === "string" ? payload.detail : errorMessage);
        }
        return await response.json() as T;
      } finally {
        // Also release rejected requests, so the next poll can recover.
        active.delete(url);
      }
    });
    active.set(url, request);
    return request;
  };
}
