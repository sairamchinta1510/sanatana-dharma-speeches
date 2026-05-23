import React, { createContext, useContext, useState, useCallback } from "react";
import { api, VideoResult, AudioResult, VyakhanamResult } from "../api/client";

export type Language = "Telugu" | "English" | "Sanskrit" | "Hindi";
export type PlayerItem =
  | { type: "video"; item: VideoResult }
  | { type: "audio"; item: AudioResult };

interface AppState {
  query: string;
  language: Language;
  videos: VideoResult[];
  audio: AudioResult[];
  vyakhanams: VyakhanamResult[];
  explanation: string | null;
  relatedTopics: string[];
  loading: boolean;
  budgetWarning: boolean;
  searchError: string | null;
  currentPlayer: PlayerItem | null;
  setQuery: (q: string) => void;
  setLanguage: (l: Language) => void;
  search: (q: string) => Promise<void>;
  setCurrentPlayer: (item: PlayerItem | null) => void;
}

const AppContext = createContext<AppState | null>(null);

export function AppProvider({ children }: { children: React.ReactNode }) {
  const [query, setQuery] = useState("");
  const [language, setLanguage] = useState<Language>("Telugu");
  const [videos, setVideos] = useState<VideoResult[]>([]);
  const [audio, setAudio] = useState<AudioResult[]>([]);
  const [vyakhanams, setVyakhanams] = useState<VyakhanamResult[]>([]);
  const [explanation, setExplanation] = useState<string | null>(null);
  const [relatedTopics, setRelatedTopics] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [budgetWarning, setBudgetWarning] = useState(false);
  const [currentPlayer, setCurrentPlayer] = useState<PlayerItem | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    setSearchError(null);
    try {
      const [videoRes, audioRes, vyakhanamRes] = await Promise.all([
        api.searchVideos(q, language),
        api.searchAudio(q, language),
        api.getVyakhanams(q, "Telugu"),  // always Telugu
      ]);
      setVideos(videoRes.results);
      setAudio(audioRes.results);
      setVyakhanams(vyakhanamRes.results);
      setExplanation(videoRes.explanation ?? null);
      setRelatedTopics(videoRes.related_topics ?? []);
      setBudgetWarning(videoRes.budget_warning || audioRes.budget_warning);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error("Search failed:", msg);
      setSearchError(msg);
    } finally {
      setLoading(false);
    }
  }, [language]);

  return (
    <AppContext.Provider value={{
      query, language, videos, audio, vyakhanams,
      explanation, relatedTopics,
      loading, budgetWarning, searchError, currentPlayer,
      setQuery, setLanguage, search, setCurrentPlayer,
    }}>
      {children}
    </AppContext.Provider>
  );
}

export function useApp(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used within AppProvider");
  return ctx;
}
