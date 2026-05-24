import React from "react";
import { View, Text, TouchableOpacity, StyleSheet, Platform } from "react-native";
import { useApp } from "../context/AppContext";
import { COLORS } from "../constants/theme";

export function StickyAudioBar() {
  const { currentAudio, audioQueue, setCurrentAudio } = useApp();

  if (!currentAudio || Platform.OS !== "web") return null;

  const currentIndex = audioQueue.findIndex((a) => a.identifier === currentAudio.identifier);
  const nextTrack = currentIndex >= 0 && currentIndex < audioQueue.length - 1
    ? audioQueue[currentIndex + 1]
    : null;

  const handleNext = () => {
    if (!nextTrack) return;
    if (typeof document !== "undefined") {
      const currentEl = document.querySelector(`audio[src="${currentAudio.audio_url}"]`) as HTMLAudioElement | null;
      if (currentEl) {
        currentEl.pause();
        currentEl.currentTime = 0;
      }
      const nextEl = document.querySelector(`audio[src="${nextTrack.audio_url}"]`) as HTMLAudioElement | null;
      if (nextEl) nextEl.play().catch(() => {});
    }
    setCurrentAudio(nextTrack);
  };

  return (
    <View style={styles.bar}>
      <View style={styles.info}>
        <Text style={styles.label}>▶ NOW PLAYING</Text>
        <Text style={styles.title} numberOfLines={1}>{currentAudio.title}</Text>
        <Text style={styles.sub}>{currentAudio.speaker}</Text>
      </View>
      {nextTrack && (
        <TouchableOpacity style={styles.nextBtn} onPress={handleNext}>
          <Text style={styles.nextText}>⏭ Next</Text>
        </TouchableOpacity>
      )}
      <TouchableOpacity style={styles.closeBtn} onPress={() => {
        if (typeof document !== "undefined") {
          const el = document.querySelector(`audio[src="${currentAudio.audio_url}"]`) as HTMLAudioElement | null;
          if (el) { el.pause(); el.currentTime = 0; }
        }
        setCurrentAudio(null);
      }}>
        <Text style={styles.closeText}>✕</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: {
    position: "absolute" as any,
    bottom: 0,
    left: 0,
    right: 0,
    backgroundColor: COLORS.bgLighter,
    borderTopWidth: 1,
    borderTopColor: COLORS.gold + "44",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 16,
    paddingVertical: 8,
    gap: 12,
  },
  info: { flex: 1 },
  label: { color: COLORS.gold, fontSize: 8, letterSpacing: 1, fontWeight: "700", opacity: 0.8 },
  title: { color: COLORS.text, fontSize: 12, fontWeight: "600", marginTop: 2 },
  sub: { color: COLORS.textMuted, fontSize: 10 },
  nextBtn: {
    backgroundColor: COLORS.bgLight, borderRadius: 4,
    borderWidth: 1, borderColor: COLORS.border,
    paddingHorizontal: 8, paddingVertical: 4,
  },
  nextText: { color: COLORS.textMuted, fontSize: 11 },
  closeBtn: { padding: 4 },
  closeText: { color: COLORS.textMuted, fontSize: 14 },
});
