/** At most one read cycle at a time; stopping never cancels backend work. */
export function createPollingTask(
  task: (isCurrent: () => boolean) => Promise<void>,
  allowed: () => boolean = () => true,
) {
  let busy = false;
  let stopped = false;
  return {
    async run() {
      if (busy || stopped || !allowed()) return;
      busy = true;
      try {
        await task(() => !stopped);
      } catch {
        // A failed status read preserves the last state; the next tick retries.
      } finally {
        busy = false;
      }
    },
    stop() { stopped = true; },
  };
}
