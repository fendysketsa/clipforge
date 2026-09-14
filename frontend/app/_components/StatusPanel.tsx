import { useEffect, useMemo, useRef, useState, type CSSProperties, type ReactNode } from "react";
import {
  Activity,
  AlertTriangle,
  Battery,
  CheckCircle2,
  Clock3,
  Cpu,
  HardDrive,
  Leaf,
  MemoryStick,
  Network,
  Radio,
  Server,
  Terminal,
  Volume2,
  VolumeX,
  XCircle,
  Zap,
} from "lucide-react";
import { statusIcon } from "../../lib/constants";
import { formatDuration, isActiveJob, jobElapsedSeconds } from "../../lib/utils";
import type { ClipJob, JobTelemetryPoint } from "../../types/clip.type";

type StatusPanelProps = {
  job: ClipJob | null;
  latestLogs: string[];
  onCancelJob: () => void;
};

type LoadProfile = {
  intensity: number;
  label: string;
  tone: "idle" | "low" | "medium" | "high" | "critical";
  speed: number;
  waveScale: number;
  isReal: boolean;
};

const STAGE_LABELS: Record<string, string> = {
  queued: "Menunggu worker",
  source: "Akuisisi sumber",
  transcript: "Transkripsi audio",
  selection: "Analisis momen",
  render: "Render & encoding",
  finalize: "Finalisasi output",
  complete: "Pipeline selesai",
};

const PIPELINE_STAGES = [
  { key: "source", label: "SOURCE", help: "Probe & download" },
  { key: "transcript", label: "TRANSCRIPT", help: "Audio to text" },
  { key: "selection", label: "ANALYSIS", help: "Rank moments" },
  { key: "render", label: "RENDER", help: "FFmpeg pipeline" },
  { key: "finalize", label: "FINALIZE", help: "Audit output" },
] as const;

const clampPercent = (value: number | null | undefined) => Math.max(0, Math.min(100, value ?? 0));
const fixed = (value: number | null | undefined, digits = 1) => (value ?? 0).toFixed(digits);

function shortTime(value: string | undefined): string {
  if (!value) return "--:--:--";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "--:--:--"
    : date.toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false });
}

function playAlertTone(kind: "ready" | "warning" | "critical") {
  if (typeof window === "undefined" || !("AudioContext" in window)) return;
  const context = new AudioContext();
  const frequencies = kind === "critical" ? [880, 620, 880] : kind === "warning" ? [720, 720] : [520];
  const start = context.currentTime + 0.02;
  frequencies.forEach((frequency, index) => {
    const oscillator = context.createOscillator();
    const gain = context.createGain();
    const at = start + index * 0.16;
    oscillator.type = kind === "critical" ? "sawtooth" : "sine";
    oscillator.frequency.setValueAtTime(frequency, at);
    gain.gain.setValueAtTime(0.0001, at);
    gain.gain.exponentialRampToValueAtTime(kind === "critical" ? 0.075 : 0.045, at + 0.018);
    gain.gain.exponentialRampToValueAtTime(0.0001, at + 0.11);
    oscillator.connect(gain);
    gain.connect(context.destination);
    oscillator.start(at);
    oscillator.stop(at + 0.12);
  });
  window.setTimeout(() => { void context.close(); }, 900);
}

function getLoadProfile(job: ClipJob | null, latestLogs: string[]): LoadProfile {
  if (!job) return { intensity: 0, label: "STANDBY", tone: "idle", speed: 2.8, waveScale: 0.38, isReal: false };
  if (job.status === "failed" || job.status === "cancelled") {
    return { intensity: 0, label: job.status === "failed" ? "FAULT" : "STOPPED", tone: "critical", speed: 2.4, waveScale: 0.32, isReal: Boolean(job.telemetry) };
  }
  if (job.status === "completed") {
    return { intensity: 0, label: "COMPLETE", tone: "low", speed: 2.2, waveScale: 0.4, isReal: Boolean(job.telemetry?.available) };
  }

  const telemetry = job.telemetry;
  if (telemetry?.available) {
    const gpuLoad = telemetry.gpu.job_attributed ? telemetry.gpu.utilization_percent ?? 0 : 0;
    const ioLoad = Math.min(100, (telemetry.read_mb_s + telemetry.write_mb_s) * 2.5);
    const intensity = Math.round(clampPercent(Math.max(telemetry.job_cpu_percent, gpuLoad, ioLoad)));
    const tone = intensity >= 75 ? "high" : intensity >= 42 ? "medium" : "low";
    return {
      intensity,
      label: intensity >= 75 ? "HEAVY" : intensity >= 42 ? "ACTIVE" : intensity >= 8 ? "LIGHT" : "IDLE",
      tone,
      speed: Math.max(0.58, 2.15 - intensity * 0.015),
      waveScale: 0.4 + intensity * 0.006,
      isReal: true,
    };
  }

  const activity = `${job.progress_stage || "queued"} ${latestLogs.slice(-3).join(" ")}`.toLowerCase();
  if (/render|encod|ffmpeg|transcri|whisper|subtitle|crop|blur|audio|model|analys/.test(activity)) {
    return { intensity: 72, label: "SAMPLING", tone: "medium", speed: 1, waveScale: 0.74, isReal: false };
  }
  return { intensity: job.status === "queued" ? 8 : 24, label: "SAMPLING", tone: "low", speed: 1.8, waveScale: 0.5, isReal: false };
}

function historyPath(
  history: JobTelemetryPoint[],
  pick: (point: JobTelemetryPoint) => number | null,
): string {
  const width = 900;
  const height = 86;
  const maxPoints = 48;
  const plotInset = 24;
  const values = history.slice(-maxPoints).map(pick);
  if (!values.length) return "";

  // One horizontal cell is one real one-second sample. A fresh clip starts at
  // the left instead of stretching two samples across the whole chart.
  const xStep = (width - plotInset * 2) / (maxPoints - 1);
  let drawing = false;
  const commands = values.flatMap((value, index) => {
    if (value === null) {
      drawing = false;
      return [];
    }
    const x = plotInset + index * xStep;
    const y = height - 8 - clampPercent(value) * 0.7;
    const command = `${drawing ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`;
    drawing = true;
    return [command];
  });

  // Render one measurement as a short point-like stroke without inventing a trend.
  if (commands.length === 1) {
    const point = commands[0].match(/^M([\d.]+) ([\d.]+)$/);
    if (point) {
      const x = Number(point[1]);
      const y = point[2];
      commands.splice(
        0,
        1,
        `M${Math.max(0, x - 1).toFixed(1)} ${y}`,
        `L${Math.min(width, x + 1).toFixed(1)} ${y}`,
      );
    }
  }
  return commands.join(" ");
}

function pointWorkload(point: JobTelemetryPoint, gpuAttributed: boolean): number {
  const ioLoad = Math.min(100, (point.read_mb_s + point.write_mb_s) * 2.5);
  const gpuLoad = gpuAttributed ? point.gpu_utilization_percent ?? 0 : 0;
  return clampPercent(Math.max(point.job_cpu_percent, gpuLoad, ioLoad));
}

function workPulsePath(history: JobTelemetryPoint[], gpuAttributed: boolean): string {
  const width = 900;
  const maxPoints = 48;
  const inset = 24;
  const baseline = 61;
  const xStep = (width - inset * 2) / (maxPoints - 1);
  const points = history.slice(-maxPoints);
  if (!points.length) return "";

  return points.flatMap((point, index) => {
    const x = inset + index * xStep;
    const workload = pointWorkload(point, gpuAttributed);
    // Square-root scaling keeps light real work visible; peak height still
    // increases monotonically with the measured task load.
    const amplitude = workload <= 0 ? 2 : 6 + Math.sqrt(workload / 100) * 43;
    const lead = Math.max(inset, x - 6);
    return [
      `${index ? "L" : "M"}${lead.toFixed(1)} ${baseline}`,
      `L${Math.max(inset, x - 3).toFixed(1)} ${(baseline - amplitude * 0.14).toFixed(1)}`,
      `L${x.toFixed(1)} ${(baseline - amplitude).toFixed(1)}`,
      `L${Math.min(width - inset, x + 2.2).toFixed(1)} ${(baseline + amplitude * 0.24).toFixed(1)}`,
      `L${Math.min(width - inset, x + 5.5).toFixed(1)} ${baseline}`,
    ];
  }).join(" ");
}

function traceXPercent(sampleCount: number): number {
  if (!sampleCount) return 2.7;
  const visibleIndex = Math.min(47, sampleCount - 1);
  return ((24 + visibleIndex * ((900 - 48) / 47)) / 900) * 100;
}

function taskName(operation: string | undefined, fallback: string): string {
  return (operation?.split(" · ")[0] || fallback).trim();
}

function MetricCell({
  icon,
  label,
  value,
  detail,
  percent,
  muted = false,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  detail: string;
  percent: number;
  muted?: boolean;
}) {
  return (
    <div className={`telemetryMetricCell${muted ? " is-muted" : ""}`}>
      <div className="telemetryMetricLabel"><span>{icon}</span>{label}</div>
      <strong>{value}</strong>
      <small title={detail}>{detail}</small>
      <i><b style={{ width: `${clampPercent(percent)}%` }} /></i>
    </div>
  );
}

export function StatusPanel({ job, latestLogs, onCancelJob }: StatusPanelProps) {
  const [now, setNow] = useState(() => Date.now());
  const [soundEnabled, setSoundEnabled] = useState(false);
  const [ecoMode, setEcoMode] = useState(false);
  const lastAlertKey = useRef("");
  const StatusIcon = job ? statusIcon[job.status] : Activity;
  const canCancel = isActiveJob(job);
  const elapsedSeconds = jobElapsedSeconds(job, now);
  const loadProfile = useMemo(() => getLoadProfile(job, latestLogs), [job, latestLogs]);
  const telemetry = job?.telemetry ?? null;
  const gpu = telemetry?.gpu ?? null;
  const battery = telemetry?.battery ?? null;
  const stageKey = (job?.progress_stage || (job ? job.status : "standby")).toLowerCase();
  const stageLabel = STAGE_LABELS[stageKey] || stageKey.replaceAll("_", " ");
  const progress = clampPercent(job?.progress_percent ?? (job?.status === "completed" ? 100 : 0));
  const sampleAge = telemetry ? Math.max(0, Math.floor((now - Date.parse(telemetry.sampled_at)) / 1000)) : null;
  const autoEco = Boolean(battery?.available && battery.plugged === false && (battery.percent ?? 100) <= 20);
  const ecoActive = ecoMode || autoEco;
  const activeStageIndex = stageKey === "complete"
    ? PIPELINE_STAGES.length
    : PIPELINE_STAGES.findIndex((stage) => stage.key === stageKey);
  const alerts = telemetry?.alerts ?? [];
  const newestAlert = alerts.at(-1);
  const audibleAlertKey = job?.error
    ? `${job.id}:error:${job.error}`
    : newestAlert
      ? `${job?.id}:${newestAlert.sequence}:${newestAlert.code}`
      : "";
  const traceStageKey = useMemo(() => {
    const history = telemetry?.history ?? [];
    const hasCurrentStage = history.some((point) => point.stage === stageKey);
    return !canCancel && !hasCurrentStage ? history.at(-1)?.stage ?? stageKey : stageKey;
  }, [canCancel, stageKey, telemetry?.history]);
  const traceStageLabel = STAGE_LABELS[traceStageKey] || traceStageKey.replaceAll("_", " ");
  const traceClipIndex = traceStageKey === "render" ? job?.progress_clip_index ?? null : null;
  const traceClipTotal = traceStageKey === "render" ? job?.progress_clip_total ?? null : null;
  const traceUnitLabel = job?.request.clip_mode === "highlight_5m" ? "PART" : "CLIP";
  const traceScopeLabel = traceClipIndex !== null
    ? `${traceUnitLabel} ${traceClipIndex}/${traceClipTotal ?? "?"}`
    : traceStageKey.toUpperCase();
  const traceHistory = useMemo(
    () => (telemetry?.history ?? []).filter((point) => (
      point.stage === traceStageKey
      && (traceClipIndex === null || point.clip_index === traceClipIndex)
    )),
    [telemetry?.history, traceClipIndex, traceStageKey],
  );
  const cpuPath = useMemo(() => historyPath(traceHistory, (point) => point.job_cpu_percent), [traceHistory]);
  const serverPath = useMemo(() => historyPath(traceHistory, (point) => point.server_cpu_percent), [traceHistory]);
  const pulsePath = useMemo(
    () => workPulsePath(traceHistory, Boolean(gpu?.job_attributed)),
    [gpu?.job_attributed, traceHistory],
  );
  const latestTracePoint = traceHistory.at(-1);
  const currentWorkload = latestTracePoint
    ? pointWorkload(latestTracePoint, Boolean(gpu?.job_attributed))
    : 0;
  const traceOperations = useMemo(() => {
    const operations: string[] = [];
    for (const point of traceHistory) {
      const name = taskName(point.operation, traceStageLabel);
      if (name && operations.at(-1) !== name) operations.push(name);
    }
    return operations.slice(-5);
  }, [traceHistory, traceStageLabel]);
  const renderHistory = useMemo(
    () => (telemetry?.history ?? []).filter((point) => point.stage === "render" && point.clip_index !== null),
    [telemetry?.history],
  );
  const knownClipTotal = traceClipTotal
    ?? renderHistory.at(-1)?.clip_total
    ?? null;
  const knownActiveClip = traceClipIndex
    ?? renderHistory.at(-1)?.clip_index
    ?? null;
  const renderIsFinished = ["finalize", "complete"].includes(stageKey) || job?.status === "completed";
  const clipJourney = useMemo(() => {
    if (!knownClipTotal || knownClipTotal < 1) return [];
    return Array.from({ length: Math.min(knownClipTotal, 20) }, (_, offset) => {
      const clipIndex = offset + 1;
      const samples = renderHistory.filter((point) => point.clip_index === clipIndex);
      const operations = samples.reduce<string[]>((result, point) => {
        const name = taskName(point.operation, "Render");
        if (name && result.at(-1) !== name) result.push(name);
        return result;
      }, []);
      const peak = samples.reduce(
        (highest, point) => Math.max(highest, pointWorkload(point, Boolean(gpu?.job_attributed))),
        0,
      );
      const complete = renderIsFinished || (knownActiveClip !== null && clipIndex < knownActiveClip);
      const active = !renderIsFinished && knownActiveClip === clipIndex;
      return { clipIndex, samples: samples.length, operations, peak, complete, active };
    });
  }, [gpu?.job_attributed, knownActiveClip, knownClipTotal, renderHistory, renderIsFinished]);
  const telemetryStyle = {
    "--telemetry-speed": `${loadProfile.speed}s`,
    "--telemetry-wave-scale": loadProfile.waveScale,
    "--telemetry-load": `${loadProfile.intensity}%`,
  } as CSSProperties;

  useEffect(() => {
    if (!canCancel && !job?.telemetry) return;
    setNow(Date.now());
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, [canCancel, job?.id, job?.telemetry]);

  useEffect(() => {
    if (!soundEnabled) {
      lastAlertKey.current = audibleAlertKey;
      return;
    }
    if (!audibleAlertKey || audibleAlertKey === lastAlertKey.current) return;
    lastAlertKey.current = audibleAlertKey;
    playAlertTone(job?.error || newestAlert?.severity === "critical" ? "critical" : "warning");
  }, [audibleAlertKey, job?.error, newestAlert?.severity, soundEnabled]);

  return (
    <section
      className={`panel statusPanel statusPanel--${loadProfile.tone} statusPanel--state-${job?.status ?? "idle"}${ecoActive ? " statusPanel--eco" : ""}${job ? "" : " statusPanel--empty"}`}
      style={telemetryStyle}
    >
      <div className="panelHeader statusPanelHeader">
        <div className="panelHeaderTitle">
          <span className="panelHeaderIcon statusHeaderIcon">
            <StatusIcon className={job?.status === "running" ? "spin" : ""} size={18} />
          </span>
          <div className="panelTitleCopy">
            <span className="panelEyebrow">SYS.MONITOR / RESOURCE TELEMETRY</span>
            <h2>Process Command Deck</h2>
          </div>
        </div>
        <div className="statusHeaderActions">
          {job ? (
            <span className={`telemetryDataProof${loadProfile.isReal ? " is-real" : ""}`}>
              <i /> {loadProfile.isReal ? `REAL DATA · ${sampleAge ?? 0}s` : "ACQUIRING METRICS"}
            </span>
          ) : null}
          <button
            className={`hudControlButton${ecoActive ? " is-active" : ""}`}
            type="button"
            title={autoEco ? "Eco HUD aktif otomatis karena baterai rendah" : "Kurangi animasi untuk menghemat baterai"}
            aria-pressed={ecoActive}
            onClick={() => setEcoMode((current) => !current)}
          >
            <Leaf size={12} /> <span>ECO</span>
          </button>
          <button
            className={`hudControlButton${soundEnabled ? " is-active" : ""}`}
            type="button"
            title="Bunyikan alert hanya saat threshold nyata terlewati"
            aria-pressed={soundEnabled}
            onClick={() => {
              const next = !soundEnabled;
              lastAlertKey.current = audibleAlertKey;
              setSoundEnabled(next);
              if (next) playAlertTone("ready");
            }}
          >
            {soundEnabled ? <Volume2 size={12} /> : <VolumeX size={12} />} <span>SOUND</span>
          </button>
          <span className={`telemetryOnline${canCancel ? " is-live" : ""}`}>
            <i /> {canCancel ? "SIGNAL ACTIVE" : job ? job.status.toUpperCase() : "SYSTEM READY"}
          </span>
          {canCancel ? (
            <button className="uiButton uiButton--ghostDanger cancelJobButton" type="button" onClick={onCancelJob}>
              <XCircle size={16} /><span>Batalkan</span>
            </button>
          ) : null}
        </div>
      </div>

      {job ? (
        <div className="activityContent telemetryContent">
          <div className="telemetryDeck">
            <div className="radarModule" aria-label={`Beban task aktual ${loadProfile.intensity}%`}>
              <div className="radarScope" aria-hidden="true">
                <span className="radarSweep" />
                <span className="radarPing radarPing--one" />
                <span className="radarPing radarPing--two" />
                <span className="radarPing radarPing--three" />
                <span className="radarCore"><Cpu size={17} /></span>
              </div>
              <div className="radarReadout">
                <span><Radio size={11} /> LIVE PROCESS LOAD</span>
                <strong>{loadProfile.label} · {loadProfile.intensity}%</strong>
                <small>{traceClipIndex !== null ? `${traceUnitLabel} ${traceClipIndex}/${traceClipTotal ?? "?"} · ${stageLabel}` : stageLabel}</small>
                <code>{telemetry ? `PID ${telemetry.root_pid ?? "—"} / ${telemetry.process_count} PROC` : "WAITING FOR PID TREE"}</code>
              </div>
            </div>

            <div className="signalModule">
              <div className="signalHeader">
                <span><Activity size={12} /> RESOURCE TRACE / {traceScopeLabel}</span>
                <div className="signalLegend">
                  <span className="is-pulse" title="Satu denyut per sampel nyata; tinggi denyut mengikuti beban terbesar CPU job, GPU job, atau process I/O">TASK PULSE</span>
                  <span className="is-job">JOB CPU</span>
                  <span className="is-server" title="Metrik seluruh host pada window clip aktif">HOST CPU</span>
                </div>
                <div className="signalMetrics">
                  <span><small>LOAD</small><b>{fixed(currentWorkload, 0)}%</b></span>
                  <span><small>SAMPLES</small><b>{traceHistory.length}</b></span>
                  <span><small>PROGRESS</small><b>{Math.round(progress)}%</b></span>
                  <span><small>EVENTS</small><b>{job.logs.length}</b></span>
                </div>
              </div>
              {clipJourney.length ? (
                <div className="clipJourney" aria-label={`Perjalanan proses ${knownClipTotal} ${traceUnitLabel.toLowerCase()}`}>
                  <div className="clipJourneyLabel">
                    <span>PER-{traceUnitLabel} EXECUTION</span>
                    <small>1 denyut = 1 sampel nyata · tinggi = task load</small>
                  </div>
                  <div className="clipJourneyTrack">
                    {clipJourney.map((item) => (
                      <div
                        className={`clipJourneyNode${item.complete ? " is-complete" : ""}${item.active ? " is-active" : ""}`}
                        key={item.clipIndex}
                        title={item.operations.length ? item.operations.join(" → ") : `${traceUnitLabel} belum diproses`}
                      >
                        <i>{item.complete ? <CheckCircle2 size={10} /> : String(item.clipIndex).padStart(2, "0")}</i>
                        <span>{traceUnitLabel} {String(item.clipIndex).padStart(2, "0")}</span>
                        <b>{item.active
                          ? taskName(latestTracePoint?.operation, job.progress_detail || "Processing")
                          : item.complete
                            ? item.samples
                              ? `${item.operations.length} TASK · PEAK ${fixed(item.peak, 0)}%`
                              : "DONE"
                            : "WAITING"}</b>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
              <div className="telemetryWave" aria-label={`Grafik telemetry ${traceStageLabel}, scope ${traceScopeLabel}`}>
                <svg viewBox="0 0 900 86" preserveAspectRatio="none" role="img">
                  <path className="telemetryWaveServer" d={serverPath} />
                  <path className="telemetryWaveLive" d={cpuPath} />
                  <path className="telemetryWavePulse" d={pulsePath} />
                </svg>
                {!traceHistory.length ? <span className="telemetryWaveEmpty">ACQUIRING {traceScopeLabel} TRACE</span> : null}
                {traceHistory.length ? (
                  <span
                    className="telemetryBeatCursor"
                    key={`${traceScopeLabel}-${telemetry?.sequence ?? 0}`}
                    style={{ left: `${traceXPercent(traceHistory.length)}%` }}
                  />
                ) : null}
                <span className="telemetryAxis telemetryAxis--top">LOAD</span>
                <span className="telemetryAxis telemetryAxis--bottom">TIME →</span>
              </div>
              <div className="clipTaskTrail" aria-label="Urutan task aktual">
                {(traceOperations.length ? traceOperations : [job.progress_detail || traceStageLabel]).map((operation, index) => (
                  <span className={index === (traceOperations.length || 1) - 1 ? "is-current" : "is-done"} key={`${operation}-${index}`}>
                    <i />{operation}
                  </span>
                ))}
              </div>
            </div>
          </div>

          <div className="realTelemetryGrid">
            <MetricCell
              icon={<Cpu size={12} />}
              label="JOB CPU"
              value={telemetry ? `${fixed(telemetry.job_cpu_percent)}%` : "—"}
              detail={telemetry ? `${fixed(telemetry.job_cpu_core_percent / 100, 2)} core / ${fixed(telemetry.cpu_capacity_cores, 1)} dialokasikan` : "Menunggu sampel pertama"}
              percent={telemetry?.job_cpu_percent ?? 0}
            />
            <MetricCell
              icon={<Server size={12} />}
              label="SERVER CPU"
              value={telemetry ? `${fixed(telemetry.server_cpu_percent)}%` : "—"}
              detail={telemetry ? `load ${fixed(telemetry.load_1m, 2)} / ${fixed(telemetry.load_5m, 2)} / ${fixed(telemetry.load_15m, 2)}` : "Menunggu host metrics"}
              percent={telemetry?.server_cpu_percent ?? 0}
            />
            <MetricCell
              icon={<MemoryStick size={12} />}
              label="MEMORY"
              value={telemetry ? `${fixed(telemetry.job_memory_mb, 0)} MB` : "—"}
              detail={telemetry ? `server ${fixed(telemetry.server_memory_used_mb / 1024, 1)} / ${fixed(telemetry.server_memory_total_mb / 1024, 1)} GB` : "Cgroup-aware memory"}
              percent={telemetry?.server_memory_percent ?? 0}
            />
            <MetricCell
              icon={<Zap size={12} />}
              label="GPU / VRAM"
              value={gpu?.available
                ? gpu.utilization_percent !== null
                  ? `${fixed(gpu.utilization_percent, 0)}%${gpu.job_attributed ? "" : " SRV"}`
                  : "DETECTED"
                : "N/A"}
              detail={gpu?.available
                ? `${gpu.name ?? "GPU"} · ${gpu.reason ?? "counter driver aktif"} · VRAM job ${fixed(gpu.job_memory_mb, 0)} MB · device ${fixed(gpu.memory_used_mb, 0)}/${fixed(gpu.memory_total_mb, 0)} MB${gpu.job_attributed ? "" : " · tidak teratribusi ke PID job"}`
                : gpu?.reason ?? "Menunggu deteksi GPU"}
              percent={gpu?.job_attributed ? gpu.utilization_percent ?? 0 : 0}
              muted={!gpu?.available}
            />
            <MetricCell
              icon={<HardDrive size={12} />}
              label="PROCESS I/O"
              value={telemetry ? `${fixed(telemetry.read_mb_s + telemetry.write_mb_s, 2)} MB/s` : "—"}
              detail={telemetry ? `R ${fixed(telemetry.read_mb_s, 2)} · W ${fixed(telemetry.write_mb_s, 2)} MB/s` : "Delta disk process tree"}
              percent={Math.min(100, (telemetry?.read_mb_s ?? 0) + (telemetry?.write_mb_s ?? 0))}
            />
            <MetricCell
              icon={<Network size={12} />}
              label="SERVER NET"
              value={telemetry ? `${fixed(telemetry.network_rx_mb_s + telemetry.network_tx_mb_s, 2)} MB/s` : "—"}
              detail={telemetry ? `RX ${fixed(telemetry.network_rx_mb_s, 2)} · TX ${fixed(telemetry.network_tx_mb_s, 2)}` : "Interface aggregate"}
              percent={Math.min(100, ((telemetry?.network_rx_mb_s ?? 0) + (telemetry?.network_tx_mb_s ?? 0)) * 2)}
            />
          </div>

          <div className="telemetryFacts">
            <span><b>{telemetry?.process_count ?? 0}</b> processes</span>
            <span><b>{telemetry?.thread_count ?? 0}</b> threads</span>
            <span><b>{telemetry?.cpu_frequency_mhz ? `${fixed(telemetry.cpu_frequency_mhz, 0)} MHz` : "N/A"}</b> CPU clock</span>
            <span><b>{telemetry?.cpu_temperature_c ? `${fixed(telemetry.cpu_temperature_c, 0)}°C` : "N/A"}</b> CPU temp</span>
            <span><b>{fixed(telemetry?.disk_free_gb, 1)} GB</b> disk free</span>
            <span><b>{gpu?.available ? `${fixed(gpu.temperature_c, 0)}°C` : "N/A"}</b> GPU temp</span>
            <span><b>{gpu?.available ? `${fixed(gpu.power_w, 0)} W` : "N/A"}</b> GPU power</span>
            <span><Battery size={9} /><b>{battery?.available ? `${fixed(battery.percent, 0)}% ${battery.plugged ? "AC" : "BAT"}` : "N/A"}</b> battery</span>
            <span title="Pipeline saat ini memakai faster-whisper CPU dan FFmpeg libx264"><b>CPU / LIBX264</b> encode path</span>
            <span><b>{telemetry?.source || "awaiting collector"}</b> source</span>
          </div>

          <div className="processIntelligenceGrid">
            <section className="pipelineRoutePanel">
              <div className="intelPanelHeader">
                <span><Zap size={11} /> EXECUTION ROUTE</span>
                <b>{Math.max(0, activeStageIndex)}/{PIPELINE_STAGES.length} PASSED · {Math.round(progress)}%</b>
              </div>
              <div className="currentOperation">
                <span>CURRENT OPERATION</span>
                <strong>{traceClipIndex !== null ? `${traceUnitLabel} ${traceClipIndex}/${traceClipTotal ?? "?"} · ` : ""}{job.progress_detail || stageLabel}</strong>
              </div>
              <div className="pipelineRouteMeterWrap">
                <div
                  className={`pipelineRouteMeter${canCancel ? " is-live" : ""}`}
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={Math.round(progress)}
                  aria-label={`Progres pipeline ${Math.round(progress)} persen`}
                >
                  <span style={{ width: `${progress}%` }} />
                  {canCancel ? (
                    <i
                      className="workflowSparkEmitter"
                      style={{ left: `${Math.min(progress, 99.2)}%` }}
                      aria-hidden="true"
                    >
                      <b /><b /><b /><b /><b /><b /><b /><b />
                    </i>
                  ) : null}
                </div>
              </div>
              <ol className="pipelineRoute">
                {PIPELINE_STAGES.map((stage, index) => {
                  const event = [...(job.progress_history ?? [])].reverse().find((item) => item.stage === stage.key);
                  const isComplete = job.status === "completed" || index < activeStageIndex;
                  const isCurrent = index === activeStageIndex;
                  return (
                    <li key={stage.key} className={`${isComplete ? "is-complete" : ""}${isCurrent ? " is-current" : ""}`}>
                      <span className="routeNode">{isComplete ? <CheckCircle2 size={11} /> : String(index + 1).padStart(2, "0")}</span>
                      <div><strong>{stage.label}</strong><small>{isCurrent ? traceClipIndex !== null ? traceScopeLabel : stageLabel : stage.help}</small></div>
                      <time>{shortTime(event?.at)}</time>
                    </li>
                  );
                })}
              </ol>
            </section>

            <section className={`telemetryAlertPanel${alerts.length || job.error ? " has-alerts" : ""}`}>
              <div className="intelPanelHeader">
                <span><AlertTriangle size={11} /> THRESHOLD HISTORY</span>
                <b>{alerts.length + (job.error ? 1 : 0)} EVENTS</b>
              </div>
              <div className="telemetryPeaks">
                <span><small>JOB RUN PEAK</small><b>{fixed(telemetry?.peaks.job_cpu_percent, 0)}%</b></span>
                <span><small>HOST PEAK</small><b>{fixed(telemetry?.peaks.server_cpu_percent, 0)}%</b></span>
                <span><small>DEVICE GPU</small><b>{gpu?.available ? `${fixed(telemetry?.peaks.gpu_utilization_percent, 0)}%` : "N/A"}</b></span>
                <span><small>PEAK I/O</small><b>{fixed(telemetry?.peaks.io_mb_s, 1)} MB/s</b></span>
              </div>
              <div className="alertHistoryList">
                {job.error ? (
                  <div className="alertHistoryItem is-critical">
                    <i /><span><b>PIPELINE FAULT</b><small>{job.error}</small></span><time>NOW</time>
                  </div>
                ) : null}
                {alerts.slice(-4).reverse().map((alert) => (
                  <div className={`alertHistoryItem is-${alert.severity}`} key={`${alert.sequence}-${alert.code}`}>
                    <i /><span><b>{alert.code.replaceAll("_", " ")}</b><small>{alert.message}</small></span>
                    <time>{fixed(alert.value, 1)}{alert.unit}</time>
                  </div>
                ))}
                {!alerts.length && !job.error ? (
                  <div className="alertHistoryEmpty"><CheckCircle2 size={15} /><span><b>ALL SYSTEMS NOMINAL</b><small>Belum ada threshold yang terlewati.</small></span></div>
                ) : null}
              </div>
            </section>
          </div>

          <div className="jobMeta telemetryMeta">
            <span><Zap size={11} /> {job.request.clip_mode === "highlight_5m" ? "Long Story · 16:9" : `${job.request.top ?? "Auto"} clip · 9:16`}</span>
            <span>{job.request.min_duration}s–{job.request.max_duration}s</span>
            <span>{job.request.enhanced_edit ? "Smart edit ON" : "Smart split ON"}</span>
            <span>Crop: {job.request.crop_mode === "person" ? "follow person" : job.request.crop_mode}</span>
            <span><Clock3 size={12} /> T+{formatDuration(elapsedSeconds)}</span>
          </div>

          <div className="terminalShell">
            <div className="terminalHeader">
              <span><Terminal size={12} /> PROCESS_STREAM.LOG</span>
              <span className="terminalJobId">JOB::{job.id.slice(0, 8).toUpperCase()}</span>
              <span className="terminalRecording"><i /> LIVE TAIL</span>
            </div>
            <div className="logBox telemetryLogBox">
              {latestLogs.length ? latestLogs.map((line, index) => (
                <div className="terminalLine" key={`${line}-${index}`}>
                  <span>{String(Math.max(1, job.logs.length - latestLogs.length + index + 1)).padStart(3, "0")}</span>
                  <p>{line}</p>
                </div>
              )) : (
                <div className="terminalLine terminalLine--pending"><span>001</span><p>Memulai proses pipeline...</p></div>
              )}
            </div>
          </div>
          {job.error ? <p className="error errorWithSpacing">{job.error}</p> : null}
        </div>
      ) : (
        <div className="statusIdleDeck">
          <div className="idleRadar"><span /><Activity size={18} /></div>
          <div><strong>TELEMETRY STANDBY</strong><span>Monitor PID tree akan tersambung otomatis saat pipeline dimulai.</span></div>
          <code>AWAITING_PROCESS_SIGNAL...</code>
        </div>
      )}
    </section>
  );
}
