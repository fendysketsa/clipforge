"use client";
import { useEffect, useState } from "react";
import { getAIOffice } from "../../lib/apiClient";
import type { AIOfficeSnapshot } from "../../lib/aiOffice";
import { Office3DFloor } from "../_components/OfficeLivingFloor";

/** Distraction-free full-page view of the realtime AI Office floor. */
export default function OfficePage() {
  const [snapshot, setSnapshot] = useState<AIOfficeSnapshot | null>(null);
  const [now, setNow] = useState(Date.now);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let active = true;
    const poll = async () => {
      try {
        const value = await getAIOffice();
        if (active) { setSnapshot(value); setFailed(false); setNow(Date.now()); }
      } catch { if (active) { setFailed(true); setNow(Date.now()); } }
    };
    void poll();
    const timer = window.setInterval(poll, 5_000);
    const clock = window.setInterval(() => setNow(Date.now()), 1_000);
    return () => { active = false; window.clearInterval(timer); window.clearInterval(clock); };
  }, []);
  return <main className="officeFullPage">
    {snapshot ? <Office3DFloor snapshot={snapshot} now={now} refreshFailed={failed}
      selected="all" onSelect={() => {}} animate /> :
      <div className="officeFloorLoading"><strong>{failed ? "Kantor belum dapat dihubungi" : "Menyiapkan ruangan & tim Anda"}</strong></div>}
  </main>;
}
