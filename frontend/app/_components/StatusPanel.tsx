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
  const values = history.slice(-maxPoints).map(pick);
  const padded: Array<number | null> = [
    ...Array(Math.max(0, maxPoints - values.length)).fill(null),
    ...values,
  ];
  return padded.map((value, index) => {
    const x = index * (width / (maxPoints - 1));
    const y = value === null ? height - 8 : height - 8 - clampPercent(value) * 0.7;
    return `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
  }).join(" ");
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
  const cpuPath = useMemo(() => historyPath(telemetry?.history ?? [], (point) => point.job_cpu_percent), [telemetry?.history]);
  const serverPath = useMemo(() => historyPath(telemetry?.history ?? [], (point) => point.server_cpu_percent), [telemetry?.history]);
  const gpuPath = useMemo(
    () => historyPath(telemetry?.history ?? [], (point) => point.gpu_utilization_percent),
    [telemetry?.history],
  );
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
                <small>{stageLabel}</small>
                <code>{telemetry ? `PID ${telemetry.root_pid ?? "—"} / ${telemetry.process_count} PROC` : "WAITING FOR PID TREE"}</code>
              </div>
            </div>

            <div className="signalModule">
              <div className="signalHeader">
                <span><Activity size={12} /> RESOURCE TRACE / {stageKey.toUpperCase()}</span>
                <div className="signalLegend">
                  <span className="is-job">JOB CPU</span>
                  <span className="is-server">SERVER CPU</span>
                  <span className="is-gpu">GPU</span>
                </div>
                <div className="signalMetrics">
                  <span><small>SEQ</small><b>#{telemetry?.sequence ?? 0}</b></span>
                  <span><small>PROGRESS</small><b>{Math.round(progress)}%</b></span>
                  <span><small>EVENTS</small><b>{job.logs.length}</b></span>
                </div>
              </div>
              <div className="telemetryWave" aria-label="Grafik histori CPU job, CPU server, dan GPU">
                <svg viewBox="0 0 900 86" preserveAspectRatio="none" role="img">
                  <path className="telemetryWaveServer" d={serverPath} />
                  {gpu?.available && gpu.utilization_percent !== null ? <path className="telemetryWaveGpu" d={gpuPath} /> : null}
                  <path className="telemetryWaveLive" d={cpuPath} />
                </svg>
                <span className="telemetryScanner" />
                <span className="telemetryAxis telemetryAxis--top">100</span>
                <span className="telemetryAxis telemetryAxis--bottom">0</span>
              </div>
              <div className={`statusProgress statusProgress--${job.status}`} aria-label={`Status job: ${job.status}`}>
                <span style={{ width: `${progress}%` }} />
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
                <b>{Math.max(0, activeStageIndex)}/{PIPELINE_STAGES.length} PASSED</b>
              </div>
              <div className="currentOperation">
                <span>CURRENT OPERATION</span>
                <strong>{job.progress_detail || stageLabel}</strong>
              </div>
              <ol className="pipelineRoute">
                {PIPELINE_STAGES.map((stage, index) => {
                  const event = [...(job.progress_history ?? [])].reverse().find((item) => item.stage === stage.key);
                  const isComplete = job.status === "completed" || index < activeStageIndex;
                  const isCurrent = index === activeStageIndex;
                  return (
                    <li key={stage.key} className={`${isComplete ? "is-complete" : ""}${isCurrent ? " is-current" : ""}`}>
                      <span className="routeNode">{isComplete ? <CheckCircle2 size={11} /> : String(index + 1).padStart(2, "0")}</span>
                      <div><strong>{stage.label}</strong><small>{isCurrent ? stageLabel : stage.help}</small></div>
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
                <span><small>PEAK JOB</small><b>{fixed(telemetry?.peaks.job_cpu_percent, 0)}%</b></span>
                <span><small>PEAK SERVER</small><b>{fixed(telemetry?.peaks.server_cpu_percent, 0)}%</b></span>
                <span><small>PEAK GPU</small><b>{gpu?.available ? `${fixed(telemetry?.peaks.gpu_utilization_percent, 0)}%` : "N/A"}</b></span>
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
