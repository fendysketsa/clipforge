type ProxyOptions = {
  backendBases: string[];
  browserApiBase: string;
  fetcher?: typeof fetch;
};

/** A failed discovery never submitted the caller's mutation. */
export function createBackendProxy({ backendBases, browserApiBase, fetcher = fetch }: ProxyOptions) {
  let selection: Promise<string> | null = null;
  let selectedAt = 0;
  const select = () => {
    if (!selection || Date.now() - selectedAt > 30_000) {
      selectedAt = Date.now();
      selection = Promise.any(backendBases.map(async base => {
        const response = await fetcher(new URL("/api/health", base), {
          cache: "no-store", signal: AbortSignal.timeout(2_500),
        });
        if (!response.ok) throw new Error(`Backend health returned ${response.status}`);
        return base;
      })).catch(error => { selection = null; throw error; });
    }
    return selection;
  };

  return async (request: Request, apiPath: string): Promise<Response> => {
    const incoming = new URL(request.url);
    const targetAt = (base: string) => {
      const target = new URL(apiPath, base);
      target.search = incoming.search;
      return target;
    };
    let base: string;
    try {
      base = await select();
    } catch {
      // Docker bridge-to-host access can fail while the same API is healthy
      // from the browser. A 307 preserves JSON POST bodies, and this branch
      // has not read/forwarded the mutation, so it cannot duplicate delivery.
      try {
        const direct = targetAt(browserApiBase);
        if (["http:", "https:"].includes(direct.protocol)
            && !direct.username && !direct.password && direct.origin !== incoming.origin) {
          return new Response(null, { status: 307, headers: {
            location: direct.toString(), "cache-control": "no-store",
            "x-clipforge-transport": "browser-direct-before-forward",
          } });
        }
      } catch { /* No valid public API base: return an explicit outage. */ }
      return Response.json({ detail: "Layanan API belum dapat dijangkau. Permintaan belum diteruskan ke backend." }, {
        status: 502, headers: { "x-clipforge-submission": "not-forwarded" },
      });
    }

    try {
      const bodyless = request.method === "GET" || request.method === "HEAD";
      const body = bodyless ? undefined : await request.arrayBuffer();
      const response = await fetcher(targetAt(base), {
        method: request.method,
        headers: { "content-type": request.headers.get("content-type") ?? "application/json" },
        body, cache: "no-store",
        ...(bodyless ? { signal: AbortSignal.timeout(15_000) } : {}),
      });
      return new Response(response.body, { status: response.status, headers: {
        "content-type": response.headers.get("content-type") ?? "application/json",
      } });
    } catch {
      selection = null;
      // Once forwarding started, never redirect/replay a POST. The upload
      // submitter reconciles its durable record before another admission.
      return Response.json({ detail: "Balasan API terputus. Periksa status antrean sebelum mengirim ulang." }, {
        status: 502, headers: { "x-clipforge-submission": "unknown" },
      });
    }
  };
}
