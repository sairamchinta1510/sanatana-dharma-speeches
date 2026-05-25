const BASE_URL =
  process.env.EXPO_PUBLIC_API_URL ??
  (typeof window !== "undefined" && window.location?.hostname !== "localhost"
    ? "https://api.find.sanatanadharmas.com"
    : "http://localhost:8000");

export interface VideoResult {
  video_id: string;
  title: string;
  speaker: string;
  description: string;
  thumbnail: string;
  url: string;
  lang: string;
}

export interface SeriesEpisode {
  video_id: string;
  title: string;
  thumbnail: string;
}

export interface SeriesResult {
  type: "series";
  speaker: string;
  series_title: string;
  episode_count: number;
  episodes: SeriesEpisode[];
  lang: string;
}

export interface AudioResult {
  identifier: string;
  title: string;
  speaker: string;
  description: string;
  audio_url: string;
  page_url: string;
  lang: string;
}

export interface VyakhanamResult {
  scholar: string;
  affiliation: string;
  text: string;
  highlight: string | null;
  lang: string;
  source_url: string;
}

export interface LocalResult {
  title: string;
  category: string;
  page_number: number;
  excerpt: string;
  pdf_url: string;
  pdf_key: string;
}

export interface SearchResponse<T> {
  results: T[];
  local_results: LocalResult[];
  explanation: string | null;
  related_topics: string[];
  budget_warning: boolean;
  from_cache: boolean;
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

export const api = {
  searchVideos: (q: string, lang: string) =>
    apiFetch<SearchResponse<VideoResult>>(
      `/api/search?q=${encodeURIComponent(q)}&lang=${encodeURIComponent(lang)}&type=video`
    ),
  searchAudio: (q: string, lang: string) =>
    apiFetch<SearchResponse<AudioResult>>(
      `/api/search?q=${encodeURIComponent(q)}&lang=${encodeURIComponent(lang)}&type=audio`
    ),
  getVyakhanams: (q: string, lang: string) =>
    apiFetch<{ results: VyakhanamResult[]; from_cache: boolean }>(
      `/api/vyakhanams?q=${encodeURIComponent(q)}&lang=${encodeURIComponent(lang)}`
    ),
};
