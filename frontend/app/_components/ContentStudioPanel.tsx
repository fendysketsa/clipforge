"use client";

import {
  ArrowRight,
  Check,
  Clipboard,
  Image as ImageIcon,
  Lightbulb,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  TriangleAlert,
} from "lucide-react";
import { useMemo, useState } from "react";

type TrendStatus = "ready" | "adapt" | "review";

type TrendIdea = {
  id: string;
  query: string;
  pillar: string;
  fit: number;
  status: TrendStatus;
  statusLabel: string;
  angle: string;
  title: string;
  hook: string;
  thumbnail: string;
  rationale: string;
  guardrail: string;
  premise: string;
};

type Props = {
  onUseConcept: (premise: string) => void;
};

const TREND_IDEAS: TrendIdea[] = [
  {
    id: "life-story",
    query: "kisah kehidupan",
    pillar: "Hikmah nyata",
    fit: 96,
    status: "ready",
    statusLabel: "Langsung cocok",
    angle: "Keputusan kecil yang mengubah arah hidup seseorang, lalu tarik hikmah yang bisa dipraktikkan.",
    title: "Satu Keputusan yang Mengubah Hidupnya",
    hook: "Ia Hampir Menyerah",
    thumbnail: "HIDUPNYA BERUBAH",
    rationale: "Emosi manusia dan transformasi cocok dengan identitas channel tanpa memaksa isu sensasional.",
    guardrail: "Gunakan kisah orisinal atau sumber yang hak komersialnya jelas; jangan mengarang sebagai kisah nyata.",
    premise: "Buat Long Story Islami sinematik tentang seorang pemuda yang hampir menyerah setelah kehilangan arah hidup. Buka pada keputusan paling genting, lalu mundur ke tiga kejadian konkret yang membentuk konflik. Tunjukkan ikhtiar, pertolongan manusia, dan refleksi iman secara wajar—tanpa mukjizat palsu atau janji rezeki instan. Akhiri dengan satu keputusan kecil yang bisa dilakukan penonton hari ini. Visual Indonesia kontemporer, emosional namun hangat, setiap adegan harus memajukan cerita.",
  },
  {
    id: "smart-ngaji",
    query: "ngaji cerdas",
    pillar: "Dalil praktis",
    fit: 94,
    status: "ready",
    statusLabel: "Langsung cocok",
    angle: "Satu pertanyaan sehari-hari, jawaban ringkas, rujukan jelas, lalu contoh penerapan.",
    title: "Ibadah Benar, Tapi Kenapa Hati Tetap Gelisah?",
    hook: "Bukan Kurang Ibadah",
    thumbnail: "TERNYATA BUKAN ITU",
    rationale: "Menciptakan seri Q&A yang mudah dikenali sekaligus punya nilai edukasi nyata.",
    guardrail: "Setiap klaim agama wajib review manusia dan rujukan; bedakan dalil, pendapat ulama, dan refleksi kreator.",
    premise: "Buat video edukasi Islami bergaya Ngaji Cerdas tentang seseorang yang rajin beribadah tetapi tetap gelisah. Mulai dengan dilema konkret, jelaskan perbedaan ibadah ritual, kesehatan mental, tanggung jawab sosial, dan kebutuhan mencari bantuan. Jangan mendiagnosis atau menjanjikan kesembuhan. Sertakan ruang untuk verifikasi dalil oleh editor manusia. Tutup dengan tiga langkah praktis yang lembut dan realistis.",
  },
  {
    id: "horror-proof",
    query: "penampakan hantu terjelas dan seram",
    pillar: "Mitos vs dalil",
    fit: 91,
    status: "adapt",
    statusLabel: "Adaptasi aman",
    angle: "Mulai dari rasa takut, bongkar kemungkinan visual/psikologis, lalu jelaskan adab menyikapi hal gaib.",
    title: "Penampakan atau Tipuan Mata? Jangan Langsung Percaya",
    hook: "Benarkah Itu Hantu?",
    thumbnail: "JANGAN LANGSUNG PERCAYA",
    rationale: "Demand horor dipakai sebagai pintu masuk edukasi, bukan untuk menguatkan klaim yang belum terbukti.",
    guardrail: "Tanpa footage curian, jumpscare murahan, klaim penampakan asli, atau ayat yang dipakai sebagai sensasi.",
    premise: "Buat Long Story edukatif Islami berjudul Penampakan atau Tipuan Mata. Cold open memperlihatkan seseorang melihat bentuk samar di gang sebelum subuh, lalu cerita menguji tiga penjelasan: cahaya dan bayangan, pareidolia, serta rasa takut yang memperbesar persepsi. Setelah bukti visual dibahas, jelaskan dengan bahasa hati-hati bahwa iman pada hal gaib tidak berarti membenarkan setiap video viral. Tutup dengan adab saat takut, langkah keselamatan nyata, dan ajakan tabayyun. Jangan tampilkan makhluk gaib, jangan menyatakan rekaman sebagai bukti, jangan membuat klaim agama tanpa review.",
  },
  {
    id: "j-horror-format",
    query: "japanese horror podcast",
    pillar: "Storytelling misteri",
    fit: 82,
    status: "adapt",
    statusLabel: "Ambil formatnya",
    angle: "Ambil ritme audio-story: cold open, petunjuk, salah arah, reveal rasional, dan hikmah.",
    title: "Suara dari Masjid Kosong Itu Ternyata…",
    hook: "Ada Suara Setelah Isya",
    thumbnail: "MASJID ITU KOSONG",
    rationale: "Struktur podcast misteri kuat untuk retention, sementara isi tetap orisinal dan relevan dengan channel.",
    guardrail: "Jangan meniru cerita, audio, karakter, atau visual podcast lain; format boleh diinspirasi, karya harus baru.",
    premise: "Tulis cerita misteri Islami orisinal bergaya audio-story tentang suara berulang dari sebuah masjid setelah Isya. Gunakan cold open, tiga petunjuk, satu dugaan yang ternyata keliru, dan reveal realistis yang manusiawi. Suasana tegang tetapi tidak mengeksploitasi jin, kematian, atau tempat ibadah. Payoff harus mengubah rasa takut menjadi kepedulian sosial dan kebiasaan memeriksa fakta.",
  },
  {
    id: "interfaith",
    query: "kesaksian kristen · roh allah yang hidup penuhiku",
    pillar: "Literasi lintas iman",
    fit: 58,
    status: "review",
    statusLabel: "Review ketat",
    angle: "Bahas cara umat beragama menceritakan pengalaman spiritual—tanpa debat menang-kalah.",
    title: "Mengapa Kesaksian Spiritual Terasa Sangat Nyata?",
    hook: "Pengalaman atau Kebenaran?",
    thumbnail: "KENAPA TERASA NYATA?",
    rationale: "Relevan hanya bila channel siap menjadi ruang literasi, bukan kanal polemik atau serangan kelompok.",
    guardrail: "Wajib review teologis dan konteks; hindari merendahkan keyakinan, potongan khotbah, atau klaim konversi palsu.",
    premise: "Buat video literasi lintas iman yang netral tentang mengapa pengalaman spiritual dapat terasa sangat nyata bagi penganut agama yang berbeda. Bedakan pengalaman personal, interpretasi teologis, dan bukti publik. Gunakan narator yang rendah hati, tanpa menyimpulkan agama lain palsu, tanpa ajakan debat, dan tandai seluruh kutipan atau klaim agama untuk review manusia sebelum publikasi.",
  },
  {
    id: "kdrama-structure",
    query: "sinopsis drama korea",
    pillar: "Drama bermakna",
    fit: 74,
    status: "adapt",
    statusLabel: "Ambil strukturnya",
    angle: "Pakai struktur konflik–pilihan–konsekuensi ala drama, tetapi dengan tokoh dan dunia yang sepenuhnya orisinal.",
    title: "Ia Memilih Jujur Saat Semua Orang Menyuruh Diam",
    hook: "Satu Pilihan, Semua Berubah",
    thumbnail: "DIA TETAP JUJUR",
    rationale: "Drama meningkatkan watch time bila konflik spesifik dan payoff-nya pantas, tanpa memakai potongan serial.",
    guardrail: "Tidak memakai footage, poster, musik, nama karakter, atau ringkasan episode berhak cipta.",
    premise: "Buat drama pendek orisinal berlatar Indonesia tentang seorang pegawai muda yang menemukan kecurangan kecil di tempat kerja. Semua orang menyuruhnya diam. Susun konflik, hubungan, konsekuensi, dan payoff seperti drama serial yang rapat, tetapi jangan meniru karya tertentu. Nilai utama adalah kejujuran, amanah, dan keberanian yang tidak naif. Akhiri dengan konsekuensi realistis, bukan kemenangan instan.",
  },
];

const THUMBNAIL_VARIANTS = [
  { id: "emotion", label: "A · Emosi", badge: "CERITA BARU" },
  { id: "proof", label: "B · Bukti", badge: "CEK FAKTA" },
  { id: "curiosity", label: "C · Curiosity", badge: "WAJIB TAHU" },
] as const;

const statusIcon = (status: TrendStatus) => status === "review" ? TriangleAlert : status === "ready" ? Check : Sparkles;

export function ContentStudioPanel({ onUseConcept }: Props) {
  const [selectedId, setSelectedId] = useState("horror-proof");
  const [variantId, setVariantId] = useState<(typeof THUMBNAIL_VARIANTS)[number]["id"]>("emotion");
  const [copied, setCopied] = useState(false);
  const selected = useMemo(
    () => TREND_IDEAS.find((idea) => idea.id === selectedId) ?? TREND_IDEAS[0],
    [selectedId],
  );
  const selectedVariant = THUMBNAIL_VARIANTS.find((variant) => variant.id === variantId) ?? THUMBNAIL_VARIANTS[0];
  const previewHeadline = variantId === "proof"
    ? selected.hook.toUpperCase()
    : variantId === "curiosity"
      ? selected.title.split(/[?!]/)[0].split(" ").slice(0, 5).join(" ").toUpperCase()
      : selected.thumbnail;

  const copyPackage = async () => {
    const packageText = [
      `TREND: ${selected.query}`,
      `PILAR: ${selected.pillar}`,
      `JUDUL: ${selected.title}`,
      `HOOK: ${selected.hook}`,
      `THUMBNAIL ${selectedVariant.label}: ${previewHeadline}`,
      `ANGLE: ${selected.angle}`,
      `GUARDRAIL: ${selected.guardrail}`,
      "",
      `PREMIS PRODUKSI:\n${selected.premise}`,
    ].join("\n");
    await navigator.clipboard.writeText(packageText);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1800);
  };

  return (
    <section className="contentStudio" id="content-studio" aria-labelledby="content-studio-title">
      <header className="contentStudioHeader">
        <div>
          <span className="contentStudioKicker"><TrendingUp size={14} /> TREND → ORIGINAL CONTENT</span>
          <h2 id="content-studio-title">Content Studio</h2>
          <p>Ubah sinyal pencarian menjadi angle Islami, paket judul, thumbnail, dan premis produksi yang tetap autentik.</p>
        </div>
        <div className="studioPositioning">
          <Sparkles size={16} />
          <span><b>Bukan sekadar clipper</b><small>Riset · ide · produksi · packaging · evaluasi</small></span>
        </div>
      </header>

      <div className="contentStudioGrid">
        <div className="trendSignalColumn">
          <div className="studioSectionTitle">
            <span>01</span>
            <div><strong>Trend fit radar</strong><small>Snapshot dari pencarian yang Anda kirim</small></div>
          </div>
          <div className="trendIdeaList">
            {TREND_IDEAS.map((idea) => {
              const Icon = statusIcon(idea.status);
              return (
                <button
                  className={`trendIdeaCard ${selected.id === idea.id ? "active" : ""} status-${idea.status}`}
                  key={idea.id}
                  type="button"
                  onClick={() => setSelectedId(idea.id)}
                >
                  <span className="trendIdeaTop"><b>{idea.query}</b><em>{idea.fit}% fit</em></span>
                  <span className="trendIdeaMeta"><i><Icon size={12} /> {idea.statusLabel}</i><small>{idea.pillar}</small></span>
                </button>
              );
            })}
          </div>
          <p className="trendRejectNote"><ShieldCheck size={14} /> “Diana and Roma” serta nama figur publik tidak dipakai otomatis karena risiko niche, hak, dan relevansi.</p>
        </div>

        <div className="trendPackageColumn">
          <div className="studioSectionTitle">
            <span>02</span>
            <div><strong>Originality package</strong><small>Janji konten harus sama dari thumbnail sampai payoff</small></div>
          </div>

          <div className="trendPackageCopy">
            <span className={`trendSafetyBadge status-${selected.status}`}><ShieldCheck size={13} /> {selected.statusLabel}</span>
            <h3>{selected.title}</h3>
            <p>{selected.angle}</p>
            <dl>
              <div><dt>Kenapa cocok</dt><dd>{selected.rationale}</dd></div>
              <div><dt>Guardrail</dt><dd>{selected.guardrail}</dd></div>
            </dl>
          </div>

          <div className={`thumbnailLab variant-${variantId}`}>
            <div className="thumbnailCanvas" role="img" aria-label={`Preview thumbnail: ${previewHeadline}`}>
              <img src="/trend-studio-cover-v1.png" alt="Preview visual sinematik untuk konsep thumbnail" />
              <div className="thumbnailShade" />
              <div className="thumbnailCopy">
                <span>{selectedVariant.badge}</span>
                <strong>{previewHeadline}</strong>
                <small>{selected.pillar.toUpperCase()}</small>
              </div>
            </div>
            <div className="thumbnailLabFooter">
              <span><ImageIcon size={14} /> Preview thumbnail 16:9</span>
              <div role="group" aria-label="Pilih variasi thumbnail">
                {THUMBNAIL_VARIANTS.map((variant) => (
                  <button className={variant.id === variantId ? "active" : ""} key={variant.id} type="button" onClick={() => setVariantId(variant.id)}>
                    {variant.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          <div className="contentStudioActions">
            <button type="button" className="studioCopyButton" onClick={() => { void copyPackage(); }}>
              {copied ? <Check size={16} /> : <Clipboard size={16} />}
              {copied ? "Paket tersalin" : "Salin paket"}
            </button>
            <button type="button" className="studioProduceButton" onClick={() => onUseConcept(selected.premise)}>
              <Lightbulb size={16} /> Produksi ide ini <ArrowRight size={16} />
            </button>
          </div>
        </div>
      </div>

      <footer className="monetizationLane">
        <span><Target size={15} /> Jalur monetisasi sehat</span>
        <ol>
          <li><b>1</b> Angle orisinal</li>
          <li><b>2</b> Visual berhak pakai</li>
          <li><b>3</b> Perspektif kreator</li>
          <li><b>4</b> Upload Private + review</li>
          <li><b>5</b> Uji A/B/C thumbnail</li>
        </ol>
        <small>Tidak ada fitur yang dapat menjamin viral atau monetisasi; studio mengurangi risiko dan mempercepat eksperimen.</small>
      </footer>
    </section>
  );
}
