export type StoryInputFormat = "article" | "article_story" | "story";
const HYPIT = /^\s*\/hypit(?:\s+|$)/i;
const PRESENTER = /^\s*\/hypit\s+(?:presenter|presentasi|artikel)\b\s*[:\n]?/i;
const INFOGRAPHIC = /\b(?:infographic|infografis|explainer|motion\s*graphic|video\s*edukasi)\b/i;
const AUTO = /\b(?:auto|otomatis|kembangkan|jelaskan\s+sendiri)\b/i;
const ARTICLE_FILM = /^\s*\/film-artikel\b\s*/i;

export const isArticlePresenterPrompt = (value: string) => PRESENTER.test(value);
export const isArticleFilmPrompt = (value: string) => ARTICLE_FILM.test(value);
export const articleFilmText = (value: string) => value.replace(ARTICLE_FILM, "").trim();
export const hypitStoryBody = (value: string) => value.replace(HYPIT, "").trim();
export const articleText = (value: string) => value.replace(PRESENTER, "").trim();
export const promptDurationSeconds = (value: string, fallback: number) => {
  const minutes = value.match(/\b(\d{1,4}(?:[.,]\d+)?)(?:\s*[-–—]\s*(\d{1,4}(?:[.,]\d+)?))?\s*(?:menit|minutes?|mins?)\b/i);
  const seconds = value.match(/\b(\d{1,4}(?:[.,]\d+)?)(?:\s*[-–—]\s*(\d{1,4}(?:[.,]\d+)?))?\s*(?:detik|seconds?|secs?|s)\b/i);
  const match = minutes || seconds
    || value.match(/\b(?:durasi|duration|sepanjang|selama)\s*[:=]?\s*(\d{1,4}(?:[.,]\d+)?)\b(?!\s*(?:menit|minutes?|jam|hours?))/i);
  if (!match) return fallback;
  // A range requests a maximum running time; use its upper bound in both UI and backend.
  const parsed = Number.parseFloat((match[2] || match[1]).replace(",", ".")) * (minutes ? 60 : 1);
  return Number.isFinite(parsed) ? Math.max(5, Math.min(600, parsed)) : fallback;
};
export const prepareStoryInput = (value: string, format: StoryInputFormat) => {
  if (HYPIT.test(value) || ARTICLE_FILM.test(value) || /^###\s*ADEGAN\b/im.test(value)) return value.trim();
  if (format === "article") return `/hypit presenter\n${value.trim()}`;
  if (format === "article_story") return `/film-artikel\n${value.trim()}`;
  return value.trim();
};

export const isHypitAutoPrompt = (value: string) => {
  if (PRESENTER.test(value)) return true;
  const body = hypitStoryBody(value);
  return HYPIT.test(value) && INFOGRAPHIC.test(body) && AUTO.test(body);
};

export const isHypitQuickPrompt = (value: string) => {
  if (PRESENTER.test(value)) return true;
  if (!HYPIT.test(value)) return false;
  const body = hypitStoryBody(value);
  const words = body.split(/\s+/).filter(Boolean).length;
  return (words <= 80 && /\b(?:ranking|rank|tier(?:\s+list)?|peringkat)\b/i.test(body))
    || (words <= (AUTO.test(body) ? 2500 : 600) && INFOGRAPHIC.test(body));
};
