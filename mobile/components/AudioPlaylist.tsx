import React, { useRef, useEffect, useState } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet, Platform,
} from "react-native";
import { AudioResult } from "../api/client";
import { COLORS } from "../constants/theme";
import { useApp } from "../context/AppContext";

interface Props { audio: AudioResult[] }

/** Formatted mm:ss from seconds */
function fmtTime(secs: number): string {
  if (!isFinite(secs) || isNaN(secs)) return "0:00";
  const m = Math.floor(secs / 60);
  const s = Math.floor(secs % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function AudioRow({ item, isActive, onPlay }: {
  item: AudioResult;
  isActive: boolean;
  onPlay: (item: AudioResult, el: HTMLAudioElement) => void;
}) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [progress, setProgress] = useState(0);
  const [duration, setDuration] = useState(0);
  const [currentTime, setCurrentTime] = useState(0);

  useEffect(() => {
    const el = audioRef.current;
    if (!el) return;
    // Only pause when row becomes inactive — play() is called directly in the click handler
    if (!isActive) { el.pause(); }
    return () => { el.pause(); };
  }, [isActive]);

  const handleTimeUpdate = (e: React.SyntheticEvent<HTMLAudioElement>) => {
    const el = e.currentTarget;
    setCurrentTime(el.currentTime);
    setDuration(el.duration || 0);
    setProgress(el.duration ? (el.currentTime / el.duration) * 100 : 0);
  };

  const handleLoadedMetadata = (e: React.SyntheticEvent<HTMLAudioElement>) => {
    setDuration(e.currentTarget.duration || 0);
  };

  const handleClick = () => {
    if (audioRef.current) {
      onPlay(item, audioRef.current);
    }
  };

  if (Platform.OS !== "web") {
    // Native stub — audio only works on web
    return (
      <View style={styles.row}>
        <View style={styles.iconBox}><Text style={styles.icon}>🎵</Text></View>
        <View style={styles.info}>
          <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
          <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
        </View>
      </View>
    );
  }

  return (
    <View style={[styles.row, isActive && styles.rowActive]}>
      {/* Hidden HTML5 audio element */}
      {/* @ts-ignore */}
      <audio
        ref={audioRef}
        src={item.audio_url}
        preload="none"
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        style={{ display: "none" }}
      />

      <TouchableOpacity
        style={[styles.iconBox, isActive && styles.iconBoxActive]}
        onPress={handleClick}
        accessibilityLabel={isActive ? "Pause" : "Play"}
        accessibilityRole="button"
      >
        <Text style={styles.icon}>{isActive ? "⏸" : "▶"}</Text>
      </TouchableOpacity>

      <View style={styles.info}>
        <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
        <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
        {isActive && (
          <View style={styles.progressRow}>
            <View style={styles.progressBg}>
              <View style={[styles.progressFill, { width: `${progress}%` as any }]} />
            </View>
            <Text style={styles.timeText}>{fmtTime(currentTime)} / {fmtTime(duration)}</Text>
          </View>
        )}
      </View>
    </View>
  );
}

export function AudioPlaylist({ audio }: Props) {
  const { setCurrentAudio, playingAudioId, setPlayingAudioId, activeAudioElRef } = useApp();

  const play = (item: AudioResult, el: HTMLAudioElement) => {
    if (playingAudioId === item.identifier) {
      // Toggle play/pause on the same track
      if (el.paused) {
        el.play().catch(console.error);
        setCurrentAudio(item);
      } else {
        el.pause();
        setCurrentAudio(null);
      }
      return;
    }
    // Switch to new track — stop previous immediately
    if (activeAudioElRef.current && activeAudioElRef.current !== el) {
      activeAudioElRef.current.pause();
      activeAudioElRef.current.currentTime = 0;
    }
    activeAudioElRef.current = el;
    // Call play() here — must stay within the user-gesture call stack
    // (browser autoplay policy blocks play() called from useEffect/async context)
    el.play().catch(console.error);
    setPlayingAudioId(item.identifier);
    setCurrentAudio(item);
  };

  if (audio.length === 0) {
    return <Text style={styles.empty}>No audio found</Text>;
  }

  return (
    <FlatList
      data={audio}
      keyExtractor={(item) => item.identifier}
      scrollEnabled={false}
      renderItem={({ item }) => (
        <AudioRow
          item={item}
          isActive={playingAudioId === item.identifier}
          onPlay={play}
        />
      )}
    />
  );
}

const styles = StyleSheet.create({
  empty: { color: COLORS.textMuted, textAlign: "center", padding: 16 },
  row: {
    backgroundColor: COLORS.bgLight, borderRadius: 8,
    borderWidth: 1, borderColor: COLORS.border,
    flexDirection: "row", alignItems: "flex-start",
    padding: 10, marginBottom: 6, gap: 10,
  },
  rowActive: { borderColor: COLORS.gold + "88", backgroundColor: COLORS.bgLighter },
  iconBox: {
    width: 36, height: 28, borderRadius: 4,
    backgroundColor: COLORS.bgLighter,
    alignItems: "center", justifyContent: "center",
  },
  iconBoxActive: { backgroundColor: COLORS.gold },
  icon: { fontSize: 12 },
  info: { flex: 1 },
  title: { color: COLORS.text, fontSize: 12, fontWeight: "600" },
  sub: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
  progressRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: 6 },
  progressBg: {
    flex: 1, height: 3, backgroundColor: COLORS.border, borderRadius: 2,
    overflow: "hidden",
  },
  progressFill: { height: 3, backgroundColor: COLORS.gold, borderRadius: 2 },
  timeText: { color: COLORS.textMuted, fontSize: 9, minWidth: 70 },
});
