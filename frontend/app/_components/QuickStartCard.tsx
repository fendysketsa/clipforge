"use client";

import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import {
  AlertTriangle,
  BarChart3,
  Archive,
  ArrowRight,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  ClipboardPaste,
  Clock3,
  Copy,
  Focus,
  Film,
  GripVertical,
  Link2,
  ListVideo,
  Loader2,
  Play,
  RefreshCw,
  Scissors,
  ShieldCheck,
  Sparkles,
  Subtitles,
  Trash2,
  WandSparkles,
} from "lucide-react";
import { formatDuration } from "../../lib/utils";
import { API_BASE, regenerateStoryboardKeyframe, type SourceProbe, type StoryboardProgress } from "../../lib/apiClient";
import type { ClipMode, SourceHistoryCheck, StoryboardPreview } from "../../types/clip.type";
import {articleText, isArticlePresenterPrompt, isHypitAutoPrompt, isHypitQuickPrompt, prepareStoryInput, type StoryInputFormat} from "../../lib/storyInput";

type QuickStartCardProps = {
  url: string;
  storyText: string;
  storyFormat: StoryInputFormat;
  storyAspectRatio: "9:16" | "16:9";
  onStoryAspectRatioChange: (aspect: "9:16" | "16:9") => void;
  onStoryFormatChange: (format: StoryInputFormat) => void;
  storyboardPreview: StoryboardPreview | null;
  isGeneratingStoryboard: boolean;
  storyboardProgress: StoryboardProgress | null;
  storyboardError: string;
  clipMode: ClipMode;
  videoDuration: number | null;
  sourceHistory: SourceHistoryCheck | null;
  sourceProbe: SourceProbe | null;
  isCheckingSourceHistory: boolean;
  allowReprocessSource: boolean;
  confirmSourceRights: boolean;
  isBusy: boolean;
  isSubmitting: boolean;
  error: string;
  onUrlChange: (value: string) => void;
  onStoryTextChange: (value: string) => void;
  onStoryboardChange: (value: StoryboardPreview) => void;
  onGenerateStoryboard: () => void;
  onRenderStoryboard: () => void;
  onClipModeChange: (value: ClipMode) => void;
  onAllowReprocessSourceChange: (value: boolean) => void;
  onConfirmSourceRightsChange: (value: boolean) => void;
  onStart: () => void;
};

const SHORT_STEPS = [
  { icon: Focus, label: "Framing otomatis", detail: "Wajah aman di 9:16" },
  { icon: Subtitles, label: "Caption dinamis", detail: "Nyaman dibaca di feed" },
  { icon: Sparkles, label: "Polish retention", detail: "Hook, ritme, dan payoff" },
];

const LONG_STEPS = [
  { icon: Sparkles, label: "Cold open", detail: "Momen terkuat masuk lebih awal" },
  { icon: Film, label: "Story chapters", detail: "Alur rapi, tanpa filler" },
  { icon: Focus, label: "YouTube packaging", detail: "Thumbnail dan judul selaras" },
];

const STORY_STEPS = [
  { icon: BookOpen, label: "Naskah otomatis", detail: "Pembuka sampai klimaks" },
  { icon: Film, label: "Scene sinematik", detail: "Tokoh, lokasi, dan gerak" },
  { icon: Sparkles, label: "Video lengkap", detail: "Dubbing, subtitle, dan musik" },
];
const PRESENTER_STEPS = [
  { icon: BookOpen, label: "Pahami artikel", detail: "Inti, alur, dan kesimpulan" },
  { icon: Film, label: "Jelaskan lewat gambar", detail: "Objek dan hubungan bergerak" },
  { icon: Sparkles, label: "Presentasi lengkap", detail: "Narasi, animasi, dan subtitle" },
];

const formatCompactNumber = (value?: number | null) => value === null || value === undefined
  ? "—"
  : new Intl.NumberFormat("id-ID", { notation: "compact", maximumFractionDigits: 1 }).format(value);

export function QuickStartCard({
  url,
  storyText,
  storyFormat,
  storyAspectRatio,
  onStoryAspectRatioChange,
  onStoryFormatChange,
  storyboardPreview,
  isGeneratingStoryboard,
  storyboardProgress,
  storyboardError,
  clipMode,
  videoDuration,
  sourceHistory,
  sourceProbe,
  isCheckingSourceHistory,
  allowReprocessSource,
  confirmSourceRights,
  isBusy,
  isSubmitting,
  error,
  onUrlChange,
  onStoryTextChange,
  onStoryboardChange,
  onGenerateStoryboard,
  onRenderStoryboard,
  onClipModeChange,
  onAllowReprocessSourceChange,
  onConfirmSourceRightsChange,
  onStart,
}: QuickStartCardProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [pasteMessage, setPasteMessage] = useState("");
  const [regeneratingKeyframe, setRegeneratingKeyframe] = useState<number | null>(null);
  const [storyboardElapsed, setStoryboardElapsed] = useState(0);
  useEffect(() => {
    if (!isGeneratingStoryboard) return;
    const started = Date.now();
    setStoryboardElapsed(0);
    const timer = window.setInterval(() => setStoryboardElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => window.clearInterval(timer);
  }, [isGeneratingStoryboard]);
  const hasUrl = Boolean(url.trim());
  const invalidUrl = Boolean(hasUrl && sourceHistory && !sourceHistory.valid_youtube_url);
  const duplicateBlocked = Boolean(sourceHistory?.found && !allowReprocessSource);
  const sourceRightsBlocked = Boolean(sourceProbe?.source_rights_risk);
  const quickScore = sourceProbe?.momentum_score ?? null;
  const quickRecommendation = sourceProbe?.quick_check_recommendation ?? "unknown";
  const quickLabel = sourceProbe?.momentum_label || "Data publik belum cukup";
  const quickReason = sourceProbe?.quick_check_reason
    || (quickScore === null
      ? "Gunakan Scan Potensi Viral untuk menilai isi video."
      : `Momentum sumber ${Math.round(quickScore)}/100 hanya sinyal distribusi. Scan transkrip tetap menentukan nilai informasi, hook, konteks, dan payoff.`);
  const isWorking = isBusy || isSubmitting;
  const isStory = clipMode === "long_animate";
  const preparedInput = prepareStoryInput(storyText, storyFormat);
  const isPresenter = isStory && isArticlePresenterPrompt(preparedInput);
  const isHypitPrompt = isStory && isHypitQuickPrompt(preparedInput);
  const isHypitAuto = isStory && isHypitAutoPrompt(preparedInput);
  const landscapeStoryboard = (storyboardPreview?.story_aspect_ratio || storyAspectRatio) === "16:9";
  const hypitPromptWords = storyText
    .replace(/^\s*\/hypit\s*/i, "")
    .trim()
    .split(/\s+/)
    .filter(Boolean).length;
  const storyReady = isPresenter ? articleText(preparedInput).split(/\s+/).filter(Boolean).length >= 12 : isHypitPrompt
    ? hypitPromptWords >= 4
    : storyText.trim().length >= 6 && hypitPromptWords >= 2;
  const canStart = isStory
    ? storyReady && (isHypitPrompt || confirmSourceRights) && !isWorking
    : hasUrl
      && !invalidUrl
      && !isCheckingSourceHistory
      && !duplicateBlocked
      && !sourceRightsBlocked
      && confirmSourceRights
      && !isWorking;
  const allStoryboardKeyframesReady = Boolean(
    storyboardPreview?.scenes.length
    && storyboardPreview.scenes.every((scene) => scene.image_status === "ready" && scene.keyframe_file),
  );

  const replaceScenes = (scenes: StoryboardPreview["scenes"]) => {
    if (!storyboardPreview) return;
    onStoryboardChange({
      ...storyboardPreview,
      scenes: scenes.map((scene, index) => ({ ...scene, index: index + 1 })),
    });
  };

  const updateScene = (position: number, patch: Partial<StoryboardPreview["scenes"][number]>) => {
    if (!storyboardPreview) return;
    replaceScenes(storyboardPreview.scenes.map((scene, index) => (
      index === position ? { ...scene, ...patch } : scene
    )));
  };

  const moveScene = (position: number, offset: -1 | 1) => {
    if (!storyboardPreview) return;
    const target = position + offset;
    if (target < 0 || target >= storyboardPreview.scenes.length) return;
    const scenes = [...storyboardPreview.scenes];
    [scenes[position], scenes[target]] = [scenes[target], scenes[position]];
    replaceScenes(scenes);
  };

  const duplicateScene = (position: number) => {
    if (!storyboardPreview || storyboardPreview.scenes.length >= 36) return;
    const source = storyboardPreview.scenes[position];
    const duplicate = {
      ...source,
      title: `${source.title} — variasi`,
      shot_plan: source.shot_plan.map((shot) => ({ ...shot })),
      shots: [...source.shots],
      dialogue_turns: source.dialogue_turns.map((turn) => ({ ...turn })),
    };
    const scenes = [...storyboardPreview.scenes];
    scenes.splice(position + 1, 0, duplicate);
    replaceScenes(scenes);
  };

  const replaceDialogueTurns = (
    position: number,
    turns: StoryboardPreview["scenes"][number]["dialogue_turns"],
  ) => {
    updateScene(position, {
      dialogue_turns: turns,
      narration: turns.map((turn) => turn.text.trim()).filter(Boolean).join(" "),
    });
  };

  const updateDialogueTurn = (
    position: number,
    turnIndex: number,
    patch: Partial<StoryboardPreview["scenes"][number]["dialogue_turns"][number]>,
  ) => {
    const scene = storyboardPreview?.scenes[position];
    if (!scene) return;
    replaceDialogueTurns(position, scene.dialogue_turns.map((turn, index) => (
      index === turnIndex ? { ...turn, ...patch } : turn
    )));
  };

  const addDialogueTurn = (position: number) => {
    const scene = storyboardPreview?.scenes[position];
    if (!scene || scene.dialogue_turns.length >= 24) return;
    replaceDialogueTurns(position, [
      ...scene.dialogue_turns,
      { speaker: "NARATOR", gender: "neutral", text: "" },
    ]);
  };

  const removeDialogueTurn = (position: number, turnIndex: number) => {
    const scene = storyboardPreview?.scenes[position];
    if (!scene || scene.dialogue_turns.length <= 1) return;
    replaceDialogueTurns(position, scene.dialogue_turns.filter((_, index) => index !== turnIndex));
  };

  const regenerateKeyframe = async (position: number) => {
    const scene = storyboardPreview?.scenes[position];
    if (!storyboardPreview || !scene || regeneratingKeyframe !== null) return;
    setRegeneratingKeyframe(position);
    updateScene(position, { image_status: "pending", image_error: "Membuat keyframe baru…" });
    try {
      const result = await toast.promise(
        regenerateStoryboardKeyframe({
          storyboard_id: storyboardPreview.storyboard_id,
          story_aspect_ratio: storyboardPreview.story_aspect_ratio || storyAspectRatio,
          scene,
          art_bible: storyboardPreview.art_bible,
          character_bible: storyboardPreview.character_bible,
          location_bible: storyboardPreview.location_bible,
          director_bible: storyboardPreview.director_bible,
          property_bible: storyboardPreview.property_bible,
        }),
        {
          loading: `Membuat ulang keyframe adegan ${position + 1}…`,
          success: "Keyframe baru siap.",
          error: "Gagal membuat keyframe",
        },
      );
      updateScene(position, result);
    } catch (keyframeError) {
      updateScene(position, {
        image_status: "error",
        image_error: keyframeError instanceof Error ? keyframeError.message : "Gagal membuat keyframe.",
      });
    } finally {
      setRegeneratingKeyframe(null);
    }
  };

  const removeScene = (position: number) => {
    if (!storyboardPreview || storyboardPreview.scenes.length <= 3) return;
    replaceScenes(storyboardPreview.scenes.filter((_, index) => index !== position));
  };

  const pasteFromClipboard = async () => {
    try {
      const value = (await navigator.clipboard.readText()).trim();
      if (!value) {
        setPasteMessage("Clipboard kosong — tekan Ctrl+V di kolom link.");
        inputRef.current?.focus();
        return;
      }
      onUrlChange(value);
      setPasteMessage("Link berhasil ditempel.");
    } catch {
      setPasteMessage("Clipboard diblokir browser — tekan Ctrl+V.");
      inputRef.current?.focus();
    }
  };

  const sourceReady = Boolean(sourceProbe?.title || videoDuration);
  const isLong = clipMode !== "short";
  const polishSteps = isPresenter ? PRESENTER_STEPS : isStory ? STORY_STEPS : isLong ? LONG_STEPS : SHORT_STEPS;

  return (
    <section className={`clipperHero${isLong ? " isLong" : ""}${isWorking ? " isWorking" : ""}${storyboardPreview ? " hasStoryboard" : ""}`} aria-labelledby="quick-start-title">
      <div className="clipperHeroCopy">
        <span className="clipperKicker">{isStory ? <BookOpen size={14} /> : isLong ? <Film size={14} /> : <Scissors size={14} />} AI PRODUCTION ENGINE</span>
        <h2 id="quick-start-title">
          {isPresenter ? "Cukup tempel artikel." : isStory ? "Satu ide cerita masuk." : "Satu video masuk."}<br />
          <em>{isPresenter ? "Jadi presentasi animasi." : isStory ? "Video lengkap siap direview." : isLong ? "Cerita utuh siap ditonton." : "Short terbaik siap tayang."}</em>
        </h2>
        <p>
          {isPresenter ? "Sistem memahami artikel, menyusun penjelasan seperti presenter, lalu menggambar objek dan menganimasikan hubungan sesuai kalimat. Narasi dan subtitle dirakit otomatis, maksimal lima menit." : isStory
            ? "Tempel premis atau alur cerita. Hypit menyusun naskah semantik, Remotion merakit visual dan animasi, lalu ClipForge mengisi dubbing, subtitle, musik, dan QC otomatis."
            : isLong
            ? "AI memilih chapter terbaik, menyusun alur, lalu menyiapkan video panjang yang rapi dan siap direview."
            : "AI menemukan momen terbaik lalu merapikan framing, caption, ritme, dan audio secara otomatis."}
        </p>

        <div className="clipperPromise">
          {polishSteps.map(({ icon: Icon, label, detail }) => (
            <span key={label}>
              <i><Icon size={16} /></i>
              <b>{label}<small>{detail}</small></b>
            </span>
          ))}
        </div>
      </div>

      <div className="sourceComposer">
        <div className="sourceComposerTop">
          <span><WandSparkles size={16} /> {isWorking ? "Sedang meracik video" : isPresenter ? "Mulai dari artikel" : isStory ? "Mulai dari jalan cerita" : "Mulai dari link video"}</span>
          <b>{isStory ? `${isPresenter || isHypitPrompt ? "9:16" : storyAspectRatio} · AI VIDEO` : isLong ? "16:9 · 5–10 menit" : "9:16 · 25–45 dtk"}</b>
        </div>

        <div className="formatChoice" role="group" aria-label="Pilih jenis hasil video">
          <button className={!isLong ? "active" : ""} type="button" disabled={isSubmitting || isGeneratingStoryboard} onClick={() => onClipModeChange("short")}>
            <span><Scissors size={17} /></span>
            <b>Viral Short<small>Retention feed · 9:16</small></b>
            {!isLong ? <CheckCircle2 size={16} /> : null}
          </button>
          <button className={clipMode === "highlight_5m" ? "active" : ""} type="button" disabled={isSubmitting || isGeneratingStoryboard} onClick={() => onClipModeChange("highlight_5m")}>
            <span><Film size={17} /></span>
            <b>Long Highlight<small>Watch time · 16:9</small></b>
            {clipMode === "highlight_5m" ? <CheckCircle2 size={16} /> : null}
          </button>
          <button className={isStory ? "active" : ""} type="button" disabled={isSubmitting || isGeneratingStoryboard} onClick={() => onClipModeChange("long_animate")}>
            <span><BookOpen size={17} /></span>
            <b>Generator Video<small>Artikel atau cerita → animasi · {isPresenter || isHypitPrompt ? "9:16" : storyAspectRatio}</small></b>
            {isStory ? <CheckCircle2 size={16} /> : null}
          </button>
        </div>

        {isStory ? (
          <div className="storyStudioComposer" aria-busy={isGeneratingStoryboard}>
            <div className="storyPromptInputs" inert={isGeneratingStoryboard}>
            <div className="storyPromptExamples" role="group" aria-label="Jenis teks untuk video">
              <div>
                <button type="button" aria-pressed={storyFormat === "article"} disabled={isWorking} onClick={() => onStoryFormatChange("article")}><BookOpen size={14}/>{storyFormat === "article" ? "✓ " : ""}Artikel → presentasi</button>
                <button type="button" aria-pressed={storyFormat === "article_story"} disabled={isWorking} onClick={() => onStoryFormatChange("article_story")}><Film size={14}/>{storyFormat === "article_story" ? "✓ " : ""}Artikel → film cerita</button>
                <button type="button" aria-pressed={storyFormat === "story"} disabled={isWorking} onClick={() => onStoryFormatChange("story")}><Film size={14}/>{storyFormat === "story" ? "✓ " : ""}Cerita / naskah</button>
              </div>
            </div>
            {!isPresenter && !isHypitPrompt ? <div className="storyPromptExamples" role="group" aria-label="Format gambar film">
              <div>{(["16:9", "9:16"] as const).map((aspect) => <button key={aspect} type="button" aria-pressed={storyAspectRatio === aspect} disabled={isWorking || isGeneratingStoryboard} onClick={() => onStoryAspectRatioChange(aspect)}>
                <Film size={14}/>{storyAspectRatio === aspect ? "✓ " : ""}{aspect === "16:9" ? "16:9 · Film layar lebar" : "9:16 · Film vertikal"}
              </button>)}</div>
            </div> : null}
            <label className="storyInputField">
              <span>{storyFormat === "article_story" ? "Artikel sumber dan arahan gaya film Anda" : isPresenter ? "Tempel artikel yang ingin dijelaskan" : isHypitAuto ? "Analogi dan teks sumber" : "Ide, deskripsi, atau naskah"}</span>
              <textarea
                value={storyText}
                onChange={(event) => onStoryTextChange(event.target.value)}
                placeholder={storyFormat === "article_story" ? "Tempel artikel, lalu tambahkan arahan seperti: durasi 5–10 menit, ilustrasi sinematik hangat, narator tenang. Fakta sumber dipertahankan saat disusun menjadi alur cerita dan adegan." : isPresenter ? "Tempel artikel lengkap di sini. Sistem menyusun alur presentasi, narasi, objek, dan animasi penjelas secara otomatis. Tidak perlu format prompt khusus." : isHypitAuto
                  ? "Analogi: jelaskan perumpamaan visualnya.\nTeks: tempel materi yang harus dijelaskan."
                  : "Contoh: Buat video tentang kucing polisi yang memecahkan misteri kota."}
                rows={storyboardPreview ? 4 : 8}
                maxLength={isPresenter || storyFormat === "article_story" ? 29950 : 30000}
              />
              <small>
                <span>{storyText.trim().length.toLocaleString("id-ID")} / {isPresenter || storyFormat === "article_story" ? "29.950" : "30.000"} karakter</span>
                <span>{storyFormat === "article_story" ? "Film 5–10 menit · durasi mengikuti narasi" : isPresenter ? "Presentasi otomatis · maksimal 5 menit" : isHypitPrompt ? "Render langsung" : "Storyboard dapat direvisi sebelum render"}</span>
              </small>
            </label>
            {!storyText.trim() ? (
              <div className="storyPromptExamples" aria-label="Contoh isi video">
                <span>Mulai dengan contoh</span>
                {storyFormat === "article" ? <div><button type="button" onClick={() => onStoryTextChange("Tumbuhan membutuhkan oksigen untuk menghasilkan energi. Pada permukaan daun terdapat pori-pori kecil bernama stomata. Stomata menjadi tempat pertukaran oksigen dan karbon dioksida. Saat fotosintesis, daun menyerap karbon dioksida dan menghasilkan oksigen. Saat respirasi, tumbuhan menggunakan oksigen untuk menghasilkan energi. Respirasi berlangsung pada siang dan malam hari.")}><BookOpen size={14}/> Artikel tumbuhan</button></div> : <div>
                  <button type="button" onClick={() => onStoryTextChange("Seorang pedagang kecil dituduh mencuri, lalu bukti tersembunyi membalik keadaan. Buat drama hangat 5 menit dengan akhir memuaskan.")}><BookOpen size={14} /> Cerita dramatis</button>
                  <button type="button" onClick={() => onStoryTextChange("/hypit Make a ranking video that puts Hypit in S tier.")}><BarChart3 size={14} /> Video ranking</button>
                  <button type="button" onClick={() => onStoryTextChange("/hypit infographic Baterai HP tidak bocor tiba-tiba | Persentase baterai adalah perkiraan dari arus dan tegangan | Chip fuel gauge menghitung arus masuk dan keluar | Kurva tegangan baterai lithium hampir datar di bagian tengah | Kuis: Saat baterai hampir habis, tegangannya bagaimana? / DATAR / TURUN TAJAM")}><Film size={14} /> Explainer animasi</button>
                  <button type="button" onClick={() => onStoryTextChange("/hypit infographic auto\nAnalogi: indikator baterai seperti petugas yang memperkirakan isi tangki, bukan melihat isinya secara langsung.\nTeks: Ponsel memperkirakan sisa baterai dari arus yang masuk dan keluar serta perubahan tegangan. Pada sebagian besar rentang pemakaian, tegangan baterai lithium berubah relatif landai sehingga perkiraan dapat dikoreksi ketika kondisi berubah.")}><Sparkles size={14} /> Auto dari teks</button>
                </div>}
              </div>
            ) : null}

            </div>
            {!isHypitPrompt ? (
              <div className="storyComposerActions">
                <span>
                  <ListVideo size={17} />
                  <b>{isGeneratingStoryboard ? "Storyboard sedang dikerjakan" : storyboardPreview ? `${storyboardPreview.scenes.length} adegan siap direvisi` : "Buat storyboard dulu"}<small>Naskah dan gambar disusun sebelum render video.</small></b>
                </span>
                <button type="button" disabled={!storyReady || isWorking || isGeneratingStoryboard} onClick={onGenerateStoryboard}>
                  {isGeneratingStoryboard ? <Loader2 className="spin" size={16} /> : storyboardPreview ? <RefreshCw size={16} /> : <WandSparkles size={16} />}
                  {isGeneratingStoryboard ? "Menyusun…" : storyboardPreview ? "Susun ulang" : "Buat storyboard"}
                </button>
              </div>
            ) : (
              <div className="storyComposerActions isDirect">
                <span>
                  <Sparkles size={17} />
                  <b>{isPresenter ? "Artikel → presentasi animasi" : isHypitAuto ? "Explainer animasi siap dibuat" : "Video Hypit siap dibuat"}<small>{isPresenter ? "Alur, objek, gambar, narasi, dan animasi disusun otomatis dari artikel." : "Ilustrasi, suara, dan caption dirakit otomatis."}</small></b>
                </span>
                <button type="button" disabled={!canStart} onClick={onStart}>
                  {isWorking ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
                  Generate video
                </button>
              </div>
            )}

            {isGeneratingStoryboard ? (
              <div className="storyboardLiveProgress">
                <div role="status" aria-live="polite">
                  <strong>{storyboardProgress?.detail || "Menghubungkan ke generator storyboard…"}</strong>
                  <small>{storyboardProgress?.total
                    ? `${storyboardProgress.completed ?? 0} dari ${storyboardProgress.total} gambar selesai. Gambar muncul satu per satu di bawah.`
                    : "AI menyusun cerita terlebih dahulu, lalu membuat gambar setiap adegan."}</small>
                </div>
                <progress aria-label="Gambar storyboard selesai" max={storyboardProgress?.total || 1} value={storyboardProgress?.total ? storyboardProgress.completed ?? 0 : undefined} />
                <span><Clock3 size={13} /> {formatDuration(storyboardElapsed)} berjalan</span>
                <small>Gambar lokal dapat memerlukan beberapa menit per adegan. Biarkan halaman ini terbuka.</small>
              </div>
            ) : null}

            {storyboardError ? <div className="storyboardInlineError" role="alert">{storyboardError}</div> : null}

            {storyboardPreview && !isHypitPrompt ? (
              <section className="storyboardPreview" inert={isGeneratingStoryboard} aria-label={isGeneratingStoryboard ? "Storyboard sedang dibuat" : "Storyboard yang dapat direvisi"}>
                <header>
                  <span><Sparkles size={15} /> Storyboard produksi</span>
                  <b>{storyboardPreview.scenes.length} ADEGAN · {storyboardPreview.story_aspect_ratio || storyAspectRatio}</b>
                </header>
                <div className="storyboardSummary">
                  <label>
                    <span>Judul video</span>
                    <input value={storyboardPreview.title} maxLength={100} onChange={(event) => onStoryboardChange({ ...storyboardPreview, title: event.target.value })} />
                  </label>
                  <small>{storyboardPreview.hook || storyboardPreview.core_message}</small>
                </div>
                <div className={`imageProviderCheck ${storyboardPreview.image_provider.ready ? "isReady" : "isBlocked"}`}>
                  {storyboardPreview.image_provider.ready ? <CheckCircle2 size={16} /> : <AlertTriangle size={16} />}
                  <span><strong>{storyboardPreview.image_provider.ready ? "Visual provider siap" : "Visual provider perlu dicek"}</strong><small>{storyboardPreview.image_provider.message}</small></span>
                </div>

                <div className="storyboardSceneList">
                  {storyboardPreview.scenes.map((scene, position) => (
                    <article key={`${scene.index}-${position}`}>
                      <aside>
                        <GripVertical size={16} />
                        <b>{String(position + 1).padStart(2, "0")}</b>
                        <small>{scene.narrative_role.replaceAll("_", " ")}</small>
                      </aside>
                      <div className="storyboardSceneEditor">
                        <header>
                          <input aria-label={`Judul adegan ${position + 1}`} value={scene.title} maxLength={64} onChange={(event) => updateScene(position, { title: event.target.value })} />
                          <div>
                            <button title="Pindah ke atas" type="button" disabled={position === 0} onClick={() => moveScene(position, -1)}><ChevronUp size={15} /></button>
                            <button title="Pindah ke bawah" type="button" disabled={position === storyboardPreview.scenes.length - 1} onClick={() => moveScene(position, 1)}><ChevronDown size={15} /></button>
                            <button title="Duplikat adegan" type="button" disabled={storyboardPreview.scenes.length >= 36} onClick={() => duplicateScene(position)}><Copy size={14} /></button>
                            <button title="Hapus adegan" className="danger" type="button" disabled={storyboardPreview.scenes.length <= 3} onClick={() => removeScene(position)}><Trash2 size={14} /></button>
                          </div>
                        </header>
                        <div className="storyboardKeyframeGrid" style={landscapeStoryboard ? {gridTemplateColumns: "minmax(0, 1fr)"} : undefined}>
                          <figure className={`storyboardKeyframe is-${scene.image_status}`} style={landscapeStoryboard ? {aspectRatio: "16 / 9", minHeight: 0, alignSelf: "start"} : undefined}>
                            {scene.image_url ? <img src={`${API_BASE}${scene.image_url}`} alt={`Keyframe adegan ${position + 1}: ${scene.title}`} /> : <div><Film size={24} /><span>{scene.image_status === "error" ? "Keyframe gagal" : "Menunggu keyframe"}</span></div>}
                            <figcaption><b>KEYFRAME {String(position + 1).padStart(2, "0")}</b><span>{scene.image_status === "ready" ? "Dipakai langsung saat animasi" : scene.image_error || "Belum dibuat"}</span><button type="button" disabled={regeneratingKeyframe !== null} onClick={() => { void regenerateKeyframe(position); }}>{regeneratingKeyframe === position ? <Loader2 className="spin" size={12} /> : <RefreshCw size={12} />} Buat ulang</button></figcaption>
                          </figure>
                          <div className="storyboardSceneFields">
                            <label><span>Subtitle / urutan ucapan</span><textarea value={scene.narration} maxLength={5000} rows={4} readOnly /></label>
                            <label><span>Visual adegan</span><textarea value={scene.visual_prompt} maxLength={900} rows={4} onChange={(event) => updateScene(position, { visual_prompt: event.target.value, keyframe_file: "", image_url: "", image_status: "pending", image_error: "Visual berubah; susun ulang storyboard untuk membuat keyframe baru." })} /></label>
                          </div>
                        </div>
                        <section className="storyboardDialogueEditor" aria-label={`Dialog dan voice cast adegan ${position + 1}`}>
                          <header><span>Voice cast per karakter</span><button type="button" disabled={scene.dialogue_turns.length >= 24} onClick={() => addDialogueTurn(position)}>+ Tambah giliran</button></header>
                          <div>
                            {scene.dialogue_turns.map((turn, turnIndex) => (
                              <article key={`${turn.speaker}-${turnIndex}`}>
                                <input aria-label={`Pembicara ${turnIndex + 1}`} value={turn.speaker} maxLength={48} placeholder="Nama karakter" onChange={(event) => updateDialogueTurn(position, turnIndex, { speaker: event.target.value })} />
                                <select aria-label={`Gender suara ${turnIndex + 1}`} value={turn.gender} onChange={(event) => updateDialogueTurn(position, turnIndex, { gender: event.target.value as "male" | "female" | "neutral" })}><option value="neutral">Auto</option><option value="male">Pria</option><option value="female">Wanita</option></select>
                                <textarea aria-label={`Dialog ${turnIndex + 1}`} value={turn.text} maxLength={900} rows={2} placeholder="Kalimat yang diucapkan" onChange={(event) => updateDialogueTurn(position, turnIndex, { text: event.target.value })} />
                                <button className="danger" title="Hapus giliran" type="button" disabled={scene.dialogue_turns.length <= 1} onClick={() => removeDialogueTurn(position, turnIndex)}><Trash2 size={14} /></button>
                              </article>
                            ))}
                          </div>
                        </section>
                        <div className="storyboardSceneMeta">
                          <label><span>Gerak kamera</span><select value={scene.camera_motion} onChange={(event) => updateScene(position, { camera_motion: event.target.value })}><option value="push_in">Push in</option><option value="pull_out">Pull out</option><option value="pan_left">Pan kiri</option><option value="pan_right">Pan kanan</option><option value="drift_up">Drift naik</option><option value="static">Statis</option></select></label>
                          <label><span>Teks layar</span><input value={scene.on_screen_text} maxLength={64} placeholder="Opsional" onChange={(event) => updateScene(position, { on_screen_text: event.target.value })} /></label>
                          <span><b>{scene.shot_plan.length || scene.shots.length}</b> shot</span>
                        </div>
                        <details>
                          <summary>Arahan lanjutan sutradara & properti</summary>
                          <div className="storyboardDirectionGrid">
                            <label><span>Arahan sutradara</span><textarea value={scene.director_direction} maxLength={900} rows={3} onChange={(event) => updateScene(position, { director_direction: event.target.value })} /></label>
                            <label><span>Properti wajib</span><textarea value={scene.property_direction} maxLength={1100} rows={3} onChange={(event) => updateScene(position, { property_direction: event.target.value })} /></label>
                          </div>
                        </details>
                      </div>
                    </article>
                  ))}
                </div>

                <footer className="storyboardRenderBar">
                  <span><ShieldCheck size={16} /><b>Storyboard bergambar terkunci saat render<small>{allStoryboardKeyframesReady ? "Keyframe ini menjadi sumber animasi; dialog memakai voice cast per karakter." : "Semua keyframe harus siap. Susun ulang bila visual card diubah."}</small></b></span>
                  <button type="button" disabled={isWorking || !confirmSourceRights || storyboardPreview.scenes.length < 3 || !allStoryboardKeyframesReady} onClick={onRenderStoryboard}>
                    {isWorking ? <Loader2 className="spin" size={17} /> : <Play size={17} />}
                    Generate video
                  </button>
                </footer>
              </section>
            ) : null}

          </div>
        ) : <label className="sourceUrlField">
          <span>Link video sumber</span>
          <div className="sourceUrlInput">
            <Link2 size={20} />
            <input
              ref={inputRef}
              value={url}
              onChange={(event) => onUrlChange(event.target.value)}
              placeholder="Tempel link YouTube di sini…"
              inputMode="url"
              autoComplete="url"
            />
            <button type="button" onClick={() => { void pasteFromClipboard(); }}>
              <ClipboardPaste size={16} /><span>Tempel</span>
            </button>
          </div>
          <small className={pasteMessage.includes("berhasil") ? "isSuccess" : ""}>
            {isCheckingSourceHistory
              ? "Sedang memeriksa sumber…"
              : videoDuration
                ? `Terdeteksi · ${formatDuration(videoDuration)}`
                : pasteMessage || "YouTube watch, Shorts, Live, dan youtu.be"}
          </small>
        </label>}

        {!isStory && sourceReady && !sourceRightsBlocked ? (
          <div className="sourceDetected" role="status">
            <span className="sourceDetectedIcon"><Check size={18} /></span>
            <span>
              <small>Sumber siap dianalisis</small>
              <strong>{sourceProbe?.title || "Video terdeteksi"}</strong>
              {sourceProbe?.uploader ? <em>{sourceProbe.uploader}</em> : null}
            </span>
            {videoDuration ? <b><Clock3 size={13} /> {formatDuration(videoDuration)}</b> : null}
          </div>
        ) : null}

        {!isStory && sourceProbe ? (
          <div className={`sourceQuickCheck is-${quickRecommendation}`} role="status">
            <div className="sourceQuickScore">
              <BarChart3 size={15} />
              <b>{sourceProbe.momentum_score === null ? "—" : Math.round(sourceProbe.momentum_score)}</b>
              <small>/100</small>
            </div>
            <div className="sourceQuickCopy">
              <span>QUICK CHECK OTOMATIS · SINYAL SUMBER</span>
              <strong>{quickLabel}</strong>
              <small>{quickReason}</small>
            </div>
            <div className="sourceQuickMetrics">
              <span><b>{formatCompactNumber(sourceProbe.view_count)}</b> views</span>
              <span><b>{formatCompactNumber(sourceProbe.views_per_day)}</b> /hari</span>
              <span><b>{sourceProbe.source_age_days ?? "—"}</b> hari</span>
              {quickRecommendation === "skip" ? (
                <button type="button" onClick={() => onUrlChange("")}>Lewati sumber</button>
              ) : null}
            </div>
          </div>
        ) : null}

        {!isStory && sourceRightsBlocked ? (
          <div className="sourceNotice isDanger" role="alert">
            <AlertTriangle size={17} />
            <span>
              <strong>Sumber tidak aman untuk diproses ulang.</strong>
              <small>{sourceProbe?.source_rights_risk_reasons.slice(0, 2).join("; ")}. Gunakan rekaman sendiri atau materi berizin komersial.</small>
            </span>
          </div>
        ) : !isStory && invalidUrl ? (
          <div className="sourceNotice isDanger" role="alert">
            <AlertTriangle size={17} /><span><strong>Link belum dikenali.</strong><small>Periksa alamat video lalu coba lagi.</small></span>
          </div>
        ) : !isStory && sourceHistory?.found ? (
          <label className="sourceNotice isWarning">
            <AlertTriangle size={17} />
            <span>
              <strong>Sumber ini pernah diproses {sourceHistory.usage_count ? `${sourceHistory.usage_count}×` : "sebelumnya"}.</strong>
              <small>Aktifkan bila ingin membuat versi baru. <a href="/source-history"><Archive size={11} /> Buka Log Sumber</a></small>
            </span>
            <input
              type="checkbox"
              checked={allowReprocessSource}
              onChange={(event) => onAllowReprocessSourceChange(event.target.checked)}
            />
          </label>
        ) : !isStory && sourceHistory?.valid_youtube_url ? (
          <div className="sourceNotice isSuccess" role="status">
            <CheckCircle2 size={17} /><span><strong>Link valid.</strong><small>Belum ada duplikat di riwayat.</small></span>
          </div>
        ) : null}

        {!isHypitPrompt ? <label className={`sourceRights${confirmSourceRights ? " checked" : ""}`}>
          <input
            type="checkbox"
            checked={confirmSourceRights}
            onChange={(event) => onConfirmSourceRightsChange(event.target.checked)}
          />
          <span><ShieldCheck size={16} /><b>{isStory ? "Saya punya hak atas cerita ini dan telah meninjau izin komersial provider AI." : "Saya punya hak/izin untuk audio dan visual sumber ini."}</b></span>
        </label> : (
          <div className="sourceNotice isSuccess" role="status">
            <CheckCircle2 size={17} /><span><strong>{isPresenter ? "Presenter animasi siap." : "Render lokal siap."}</strong><small>{isPresenter ? "LLM yang dipilih menyusun objek dan penjelasan; ilustrasi serta animasi digambar lokal. Jika LLM tidak tersedia, perencana lokal memakai isi artikel." : "Visual dibuat dari kode; prompt ini tidak memakai footage, voice clone, atau ImageGen pihak ketiga."}</small></span>
          </div>
        )}

        {error ? <div className="sourceError" role="alert">{error}</div> : null}

        {!isStory ? <div className="sourceActionGrid isSingle">
          <button className="createShortButton" type="button" disabled={!canStart} onClick={onStart}>
            {isWorking ? <Loader2 className="spin" size={19} /> : <WandSparkles size={19} />}
            <span>
              {isWorking ? "Produksi video sedang berjalan…" : isLong ? "Scan & Susun Long Highlight" : "Scan & Buat Short Terbaik"}
              <small>{isWorking ? "AI menyusun materi lalu melanjutkan ke render" : isLong ? "Pilih chapter, susun alur, lalu render otomatis" : "Pilih momen terbaik, audit struktur dan konteks, lalu render"}</small>
            </span>
            {!isWorking ? <ArrowRight size={19} /> : null}
          </button>
        </div> : null}

        {!isHypitPrompt && !confirmSourceRights && (isStory ? Boolean(storyText.trim()) : hasUrl) ? <p className="sourceHint">Storyboard boleh dibuat dulu. Konfirmasi hak dan izin diperlukan saat produksi video.</p> : null}
      </div>
    </section>
  );
}
