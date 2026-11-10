type QueueItem = {
  id: string;
  status: string;
  queue_position?: number | null;
  queue_total?: number | null;
};

export type UploadQueuePosition = {
  position: number | null;
  total: number;
  ahead: number;
  hint: string;
};

/** Backend ranks waiting items; the displayed order also includes active work. */
export function uploadQueuePosition(upload: QueueItem | undefined, uploads: QueueItem[]): UploadQueuePosition | null {
  if (!upload || !["queued", "running"].includes(upload.status)) return null;
  const running = uploads.filter((item) => item.status === "running").length;
  const waiting = uploads.filter((item) => item.status === "queued");
  const waitingTotal = Math.max(waiting.length, ...waiting.map((item) => item.queue_total ?? 0));
  if (upload.status === "running") {
    return {
      position: running <= 1 ? 1 : null,
      total: Math.max(1, running) + waitingTotal,
      ahead: 0,
      hint: running > 1 ? `${running} proses aktif · ${waitingTotal} menunggu`
        : waitingTotal ? `${waitingTotal} video menunggu setelah ini` : "Giliran sedang diproses",
    };
  }
  const rank = upload.queue_position;
  if (rank == null || !Number.isInteger(rank) || rank < 1) return null;
  const position = rank + running;
  return {
    position,
    total: Math.max(waitingTotal, upload.queue_total ?? 0, rank) + running,
    ahead: position - 1,
    hint: position === 1 ? "Giliran berikutnya" : `${position - 1} video di depan`,
  };
}
