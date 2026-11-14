import { ArrowUpRight, CheckCircle2, ChevronDown, Loader2, RefreshCw, Settings2, Youtube } from "lucide-react";

type Props = {
  youtubeEnabled: boolean; tiktokEnabled: boolean;
  youtubeMessage: string; tiktokMessage: string; tiktokHandle: string;
  youtubeBusy: boolean; tiktokBusy: boolean;
  onYouTubeLogin: () => void; onTikTokLogin: () => void; onTikTokCheck: () => void;
  onCapture: () => void; onImport: () => void; onNoCdp: () => void;
};

export function ConnectionsPanel(props: Props) {
  return <div className="connectionGrid">
    <section className="connectionCard">
      <header><span className="connectionLogo isYoutube"><Youtube size={25} /></span><div><h2>YouTube</h2><p>Upload, jadwal, dan pemeriksaan video.</p></div></header>
      <span className={`connectionState ${props.youtubeEnabled ? "isReady" : ""}`}><CheckCircle2 size={14} />{props.youtubeEnabled ? "Integrasi tersedia" : "Perlu dihubungkan"}</span>
      <p>Hubungkan akun yang digunakan untuk mengelola channel. Hasil upload tetap melewati pemeriksaan dan aturan publikasi.</p>
      <div className="connectionActions"><button className="uiButton uiButton--primary" type="button" disabled={props.youtubeBusy} onClick={props.onYouTubeLogin}>
        {props.youtubeBusy ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}{props.youtubeBusy ? "Menunggu login…" : props.youtubeEnabled ? "Hubungkan ulang" : "Hubungkan YouTube"}
      </button><a className="uiButton" href="https://studio.youtube.com" target="_blank" rel="noreferrer">Buka Studio <ArrowUpRight size={15} /></a></div>
      <details className="connectionAdvanced"><summary><Settings2 size={14} /> Diagnostik koneksi <ChevronDown size={14} /></summary>
        <p>{props.youtubeMessage || "Belum ada informasi koneksi."}</p>
        <div className="connectionActions"><button type="button" onClick={props.onCapture}>Sinkronkan sesi browser</button><button type="button" onClick={props.onImport}>Impor sesi</button><button type="button" onClick={props.onNoCdp}>Gunakan sesi tersimpan</button></div>
      </details>
    </section>
    <section className="connectionCard">
      <header><span className="connectionLogo">♪</span><div><h2>TikTok</h2><p>{props.tiktokHandle ? `@${props.tiktokHandle}` : "Distribusi video pendek."}</p></div></header>
      <span className={`connectionState ${props.tiktokEnabled ? "isReady" : ""}`}><CheckCircle2 size={14} />{props.tiktokEnabled ? "Integrasi tersedia" : "Perlu dihubungkan"}</span>
      <p>Periksa sesi akun sebelum mengirim video. Post yang belum terkonfirmasi tetap ditahan untuk menghindari duplikat.</p>
      <div className="connectionActions"><button className="uiButton uiButton--primary" type="button" disabled={props.tiktokBusy} onClick={props.onTikTokLogin}>
        {props.tiktokBusy ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}{props.tiktokBusy ? "Menunggu login…" : props.tiktokEnabled ? "Hubungkan ulang" : "Hubungkan TikTok"}
      </button><button className="uiButton" type="button" onClick={props.onTikTokCheck} disabled={props.tiktokBusy}>Periksa sesi</button></div>
      <details className="connectionAdvanced"><summary><Settings2 size={14} /> Diagnostik koneksi <ChevronDown size={14} /></summary><p>{props.tiktokMessage || "Belum ada informasi koneksi."}</p></details>
    </section>
  </div>;
}
