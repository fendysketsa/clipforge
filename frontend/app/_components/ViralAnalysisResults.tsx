"use client";

import {
  ArrowUpRight,
  BarChart3,
  CheckCircle2,
  Clock3,
  Gauge,
  ShieldAlert,
  Sparkles,
  Target,
  XCircle,
} from "lucide-react";
import type { ClipCandidate } from "../../types/clip.type";
import { VIRAL_QUALITY_FLOOR } from "../../lib/constants";
import { formatDuration } from "../../lib/utils";

type Props = {
  candidates: ClipCandidate[];
  sourceTitle?: string | null;
};

const SCORE_PARTS: Array<{
  key: keyof NonNullable<ClipCandidate["viral_score_breakdown"]>;
  label: string;
  max: number;
}> = [
  { key: "hook_immediacy", label: "Hook", max: 20 },
  { key: "standalone_clarity", label: "Kejelasan", max: 20 },
  { key: "payoff_ending", label: "Payoff", max: 15 },
  { key: "retention_density", label: "Retention", max: 15 },
  { key: "emotional_practical_value", label: "Value", max: 10 },
  { key: "specificity_novelty", label: "Novelty", max: 10 },
  { key: "editability", label: "Editability", max: 5 },
  { key: "metadata_fit", label: "Packaging", max: 5 },
];

function scoreTone(score: number) {
  if (score >= 90) return "exceptional";
  if (score >= VIRAL_QUALITY_FLOOR) return "strong";
  return "weak";
}

function scoreLabel(score: number) {
  if (score >= 90) return "Exceptional";
  if (score >= VIRAL_QUALITY_FLOOR) return "Layak untuk diuji";
  return "Tidak layak";
}

function timestamp(seconds: number) {
  const whole = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(whole / 3600);
  const minutes = Math.floor((whole % 3600) / 60);
  const secs = whole % 60;
  return [hours, minutes, secs]
    .map((value) => value.toString().padStart(2, "0"))
    .join(":");
}

export function ViralAnalysisResults({ candidates, sourceTitle }: Props) {
  const ranked = [...candidates].sort(
    (left, right) => (right.viral_score ?? right.score) - (left.viral_score ?? left.score),
  );
  const strongCount = ranked.filter(
    (candidate) => candidate.viral_quality_gate_passed,
  ).length;
  const bestScore = ranked[0]?.viral_score ?? ranked[0]?.score ?? 0;

  const prepareRender = () => {
    document.getElementById("quick-start-title")?.scrollIntoView({
      behavior: "smooth",
      block: "center",
    });
  };

  return (
    <section className="viralAnalysis" id="viral-analysis" aria-labelledby="viral-analysis-title">
      <header className="viralAnalysisHero">
        <div className="viralAnalysisHeading">
          <span className="viralAnalysisIcon"><BarChart3 size={22} /></span>
          <div>
            <span className="viralAnalysisEyebrow">AI VIRAL SCAN · ANALYSIS ONLY</span>
            <h2 id="viral-analysis-title">Ranking potensi viral siap</h2>
            <p>{sourceTitle || "Video YouTube"} · kandidat dipilih dari ucapan asli, bukan hook buatan.</p>
          </div>
        </div>
        <div className="viralAnalysisStats">
          <span><b>{bestScore}</b><small>skor terbaik</small></span>
          <span><b>{strongCount}</b><small>lolos gate {VIRAL_QUALITY_FLOOR}</small></span>
          <span><b>{ranked.length}</b><small>kandidat diaudit</small></span>
        </div>
      </header>

      <div className="viralRealityCheck">
        <Gauge size={17} />
        <p><strong>Ini estimasi kualitas, bukan jaminan views.</strong> Distribusi nyata tetap dipengaruhi respons penonton, topik, waktu upload, judul, dan thumbnail.</p>
        <span><ShieldAlert size={14} /> Hak sumber tetap perlu diverifikasi sebelum render/upload</span>
      </div>

      <div className="viralCandidateGrid">
        {ranked.map((candidate, rank) => {
          const score = candidate.viral_score ?? candidate.score;
          const tone = scoreTone(score);
          const breakdown = candidate.viral_score_breakdown;
          const passes = Boolean(candidate.viral_quality_gate_passed);
          return (
            <article className={`viralCandidate viralCandidate--${tone}`} key={`${candidate.index}-${candidate.start}`}>
              <div className="viralCandidateTop">
                <span className="viralRank">#{rank + 1}</span>
                <div className="viralCandidateTitle">
                  <span>{passes ? <CheckCircle2 size={14} /> : <XCircle size={14} />}{passes ? "LOLOS QUALITY GATE" : "BELUM LOLOS GATE"}</span>
                  <h3>{candidate.title}</h3>
                </div>
                <div className="viralScoreDial">
                  <b>{score}</b>
                  <small>/100</small>
                </div>
              </div>

              <div className="viralCandidateMeta">
                <span><Clock3 size={13} /> {timestamp(candidate.start)}–{timestamp(candidate.end)}</span>
                <span>{formatDuration(candidate.duration)}</span>
                <span className={`viralTone viralTone--${tone}`}>{scoreLabel(score)}</span>
              </div>

              <blockquote>“{candidate.hook || candidate.text}”</blockquote>
              <p className="viralCandidateReason">{candidate.reason}</p>

              {breakdown ? (
                <div className="viralBreakdown" aria-label={`Breakdown skor ${score} dari 100`}>
                  {SCORE_PARTS.map((part) => {
                    const value = breakdown[part.key] ?? 0;
                    return (
                      <span key={part.key}>
                        <small>{part.label}<b>{value}/{part.max}</b></small>
                        <i><em style={{ width: `${Math.min(100, (value / part.max) * 100)}%` }} /></i>
                      </span>
                    );
                  })}
                </div>
              ) : null}

              <footer>
                <span><Target size={14} /> Native ClipForge {candidate.score}/100</span>
                <span>{candidate.boundary_quality || "Batas kalimat diaudit"}</span>
              </footer>
            </article>
          );
        })}
      </div>

      <div className="viralAnalysisCta">
        <div><Sparkles size={18} /><span><strong>Siap membuat versi final?</strong><small>Konfirmasi hak sumber, lalu ClipForge merender kandidat terbaik dengan subtitle dan polish.</small></span></div>
        <button type="button" onClick={prepareRender}>Lanjut buat Short <ArrowUpRight size={16} /></button>
      </div>
    </section>
  );
}
