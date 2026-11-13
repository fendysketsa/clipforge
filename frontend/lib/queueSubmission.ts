type UploadRecord = {
  id: string; source_job_id: string; clip_url: string; status: string;
  created_at?: string; updated_at?: string; upload_confirmed?: boolean; dry_run?: boolean; error?: string | null;
};
type Store = Pick<Storage, "getItem" | "setItem" | "removeItem">;
type Reservation = { baseline: Record<string, string> };
type Input = { platform: "youtube" | "tiktok"; jobId: string; clipUrl: string; baseUrl: string; fallbackBaseUrls?: string[] };

/** Only loopback aliases refer to the same server; never guess a new host. */
export function uploadApiBases(configured: string): string[] {
  const bases = [configured.replace(/\/$/, "")];
  try {
    const url = new URL(configured);
    if (["localhost", "127.0.0.1", "[::1]"].includes(url.hostname)) {
      url.hostname = "127.0.0.1";
      bases.push(url.toString().replace(/\/$/, ""));
      url.hostname = "localhost";
      bases.push(url.toString().replace(/\/$/, ""));
    }
  } catch { /* Relative API bases already share the page's origin. */ }
  bases.push("");
  return [...new Set(bases)];
}

/** Recover lost responses through the server's serialized admission check. */
export function createQueueSubmitter(
  fetcher: typeof fetch, getStore: () => Store | null,
  errorMessage: (response: Response, fallback: string) => Promise<string>,
) {
  const active = new Map<string, Promise<UploadRecord>>();
  const reservations = new Map<string, Reservation>();
  const signature = (row: UploadRecord) => `${row.status}:${row.updated_at ?? row.created_at ?? ""}`;
  return function submit<T extends UploadRecord>(input: Input): Promise<T> {
    const key = `clipforge:upload-request:${input.platform}:${input.jobId}:${input.clipUrl}`;
    const ongoing = active.get(key);
    if (ongoing) return ongoing as Promise<T>;
    const run = async (): Promise<UploadRecord> => {
      const bases = [...new Set([input.baseUrl, ...(input.fallbackBaseUrls ?? [])])];
      let preferredBase = input.baseUrl;
      let store: Store | null = null;
      try { store = getStore(); } catch { /* Private-mode storage may be disabled. */ }
      let reservation = reservations.get(key);
      try {
        const saved = store?.getItem(key);
        if (!reservation && saved) {
          const parsed = JSON.parse(saved) as Reservation;
          if (!parsed.baseline || typeof parsed.baseline !== "object") throw new Error("Invalid reservation");
          reservation = parsed;
        }
      } catch {
        throw new Error("Catatan pengiriman belum dapat diperiksa. Periksa antrean sebelum mengirim ulang.");
      }
      const clear = () => {
        reservations.delete(key);
        try { store?.removeItem(key); } catch { /* Memory reservation is already cleared. */ }
      };
      const read = async () => {
        for (const base of [preferredBase, ...bases.filter(base => base !== preferredBase)]) {
          try {
            const response = await fetcher(`${base}/api/${input.platform}/uploads`, {
              cache: "no-store", signal: AbortSignal.timeout(15_000),
            });
            if (!response.ok) continue;
            const rows = await response.json() as UploadRecord[];
            if (!Array.isArray(rows)) continue;
            preferredBase = base;
            return rows.filter((row) => !row.dry_run && row.source_job_id === input.jobId && row.clip_url === input.clipUrl);
          } catch { /* A GET can safely try another address of this backend. */ }
        }
        throw new Error("Layanan antrean upload belum dapat dihubungi. Periksa koneksi ke server dan coba lagi.");
      };
      const known = (rows: UploadRecord[]) => rows.find((row) => row.status === "running" || row.status === "queued"
        || row.status === "completed" && row.upload_confirmed);
      const finish = (row: UploadRecord) => {
        clear();
        if (row.dry_run) throw new Error("Mode simulasi aktif; video belum diunggah ke platform.");
        if (row.status === "failed" || row.status === "cancelled") throw new Error(row.error || "Upload belum berhasil masuk proses.");
        return row;
      };
      const payload = JSON.stringify({ clip_url: input.clipUrl,
        visibility: input.platform === "tiktok" ? "only_you" : "private" });
      const endpointPath = `/api/jobs/${input.jobId}/${input.platform}-uploads`;
      const platformName = input.platform === "youtube" ? "YouTube" : "TikTok";
      const recoverMissing = async (): Promise<UploadRecord> => {
        // An empty GET does not prove the original request stopped. This
        // endpoint waits for its creation lock and reuses ANY persisted
        // attempt, including failed/Post-unknown records, before admitting one.
        let response: Response | undefined;
        const unavailableBases = new Set<string>();
        let lastServerResponse: Response | undefined;
        for (let attempt = 0; attempt < 3; attempt++) {
          if (attempt) {
            await new Promise(resolve => setTimeout(resolve, attempt * 500));
            const current = await read().catch(() => []);
            const accepted = known(current) ?? current.find(row => reservation!.baseline[row.id] !== signature(row));
            if (accepted) return finish(accepted);
          }
          const base = [preferredBase, ...bases.filter(base => base !== preferredBase)]
            .find(base => !unavailableBases.has(base)) ?? preferredBase;
          try {
            response = await fetcher(`${base}${endpointPath}/reconcile`, {
              method: "POST", headers: { "Content-Type": "application/json" }, body: payload,
              signal: AbortSignal.timeout(90_000),
            });
            if (response.status < 500) { preferredBase = base; break; }
            lastServerResponse = response;
            unavailableBases.add(base);
          } catch { response = undefined; unavailableBases.add(base); }
        }
        // Even the last lost response may have admitted the request. Check
        // its durable record once more before reporting a connection failure.
        if (!response || response.status >= 500) {
          const current = await read().catch(() => []);
          const accepted = known(current) ?? current.find(row => reservation!.baseline[row.id] !== signature(row));
          if (accepted) return finish(accepted);
        }
        response ??= lastServerResponse;
        if (!response) {
          throw new Error(`Layanan upload ${platformName} belum dapat dihubungi setelah 3 percobaan. Permintaan tetap dicatat agar video tidak terkirim dua kali; periksa antrean sebelum mencoba lagi.`);
        }
        if ([404, 405].includes(response.status)) {
          const detail = await errorMessage(response, "Not Found");
          if (response.status === 405 || detail.trim().toLowerCase() === "not found") {
            // Old backend: do not replay a normal POST or discard the guard.
            throw new Error("Backend belum mendukung pemeriksaan pengiriman. Perbarui backend agar upload yang tertahan dapat dilanjutkan dengan aman.");
          }
          clear();
          throw new Error(detail);
        }
        if (!response.ok) {
          if (response.status >= 400 && response.status < 500) {
            clear();
            throw new Error(await errorMessage(response, "Upload ditahan pemeriksaan backend."));
          }
          throw new Error(await errorMessage(response, `Layanan upload ${platformName} sedang bermasalah. Permintaan tetap dicatat untuk pemeriksaan berikutnya.`));
        }
        let recovered: UploadRecord;
        try { recovered = await response.json() as UploadRecord; } catch {
          throw new Error("Balasan layanan upload terputus. Permintaan tetap dicatat untuk pemeriksaan berikutnya.");
        }
        if (!recovered || !recovered.id || recovered.source_job_id !== input.jobId || recovered.clip_url !== input.clipUrl) {
          throw new Error("Identitas balasan upload tidak cocok. Pengiriman ditahan untuk mencegah duplikat.");
        }
        return finish(recovered);
      };
      const rows = await read();
      const existing = known(rows);
      if (existing) return finish(existing);
      if (reservation) {
        const changed = rows.find((row) => reservation!.baseline[row.id] !== signature(row));
        if (changed) return finish(changed);
        return recoverMissing();
      }
      reservation = { baseline: Object.fromEntries(rows.map((row) => [row.id, signature(row)])) };
      reservations.set(key, reservation);
      try { store?.setItem(key, JSON.stringify(reservation)); } catch { /* Keep the in-memory guard. */ }
      const reconcile = async (): Promise<UploadRecord> => {
        const current = await read().catch(() => []);
        const accepted = known(current) ?? current.find((row) => reservation!.baseline[row.id] !== signature(row));
        if (accepted) return finish(accepted);
        return recoverMissing();
      };
      let response: Response;
      try {
        response = await fetcher(`${preferredBase}${endpointPath}`, {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: payload,
          signal: AbortSignal.timeout(90_000),
        });
      } catch { return reconcile(); }
      if (!response.ok) {
        if (response.status >= 400 && response.status < 500) {
          clear();
          throw new Error(await errorMessage(response, "Upload ditahan pemeriksaan backend."));
        }
        return reconcile();
      }
      let result: UploadRecord;
      try { result = await response.json() as UploadRecord; } catch { return reconcile(); }
      if (!result || !result.id || result.source_job_id !== input.jobId || result.clip_url !== input.clipUrl) return reconcile();
      return finish(result);
    };
    const promise = run().finally(() => active.delete(key));
    active.set(key, promise);
    return promise as Promise<T>;
  };
}
