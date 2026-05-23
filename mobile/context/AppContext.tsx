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
  loading: boolean;
  budgetWarning: boolean;
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
  const [loading, setLoading] = useState(false);
  const [budgetWarning, setBudgetWarning] = useState(false);
  const [currentPlayer, setCurrentPlayer] = useState<PlayerItem | null>(null);

  const search = useCallback(async (q: string) => {
    if (!q.trim()) return;
    setLoading(true);
    try {
      const [videoRes, audioRes, vyakhanamRes] = await Promise.all([
        api.searchVideos(q, language),
        api.searchAudio(q, language),
        api.getVyakhanams(q, language),
      ]);
      setVideos(videoRes.results);
      setAudio(audioRes.results);
      setVyakhanams(vyakhanamRes.results);
      setBudgetWarning(videoRes.budget_warning || audioRes.budget_warning);
    } catch (e) {
      console.error("Search failed:", e);
    } finally {
      setLoading(false);
    }
  }, [language]);

  return (
    <AppContext.Provider value={{
      query, language, videos, audio, vyakhanams,
      loading, budgetWarning, currentPlayer,
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
