import React, { useState, useRef } from "react";
import {
  View, Text, FlatList, TouchableOpacity, StyleSheet,
} from "react-native";
import { Audio } from "expo-av";
import { AudioResult } from "../api/client";
import { COLORS } from "../constants/theme";
import { useApp } from "../context/AppContext";

interface Props { audio: AudioResult[] }

export function AudioPlaylist({ audio }: Props) {
  const { setCurrentPlayer } = useApp();
  const [playingId, setPlayingId] = useState<string | null>(null);
  const soundRef = useRef<Audio.Sound | null>(null);

  const play = async (item: AudioResult) => {
    try {
      if (soundRef.current) {
        await soundRef.current.unloadAsync();
        soundRef.current = null;
      }
      await Audio.setAudioModeAsync({ playsInSilentModeIOS: true });
      const { sound } = await Audio.Sound.createAsync(
        { uri: item.audio_url },
        { shouldPlay: true }
      );
      soundRef.current = sound;
      setPlayingId(item.identifier);
      setCurrentPlayer({ type: "audio", item });
      sound.setOnPlaybackStatusUpdate((status) => {
        if (status.isLoaded && status.didJustFinish) {
          setPlayingId(null);
          setCurrentPlayer(null);
        }
      });
    } catch (e) {
      console.error("Audio play failed:", e);
    }
  };

  const stop = async () => {
    if (soundRef.current) {
      await soundRef.current.stopAsync();
      await soundRef.current.unloadAsync();
      soundRef.current = null;
    }
    setPlayingId(null);
    setCurrentPlayer(null);
  };

  if (audio.length === 0) {
    return <Text style={styles.empty}>No audio found</Text>;
  }

  return (
    <FlatList
      data={audio}
      keyExtractor={(item) => item.identifier}
      scrollEnabled={false}
      renderItem={({ item }) => {
        const active = playingId === item.identifier;
        return (
          <TouchableOpacity
            style={[styles.row, active && styles.rowActive]}
            onPress={() => active ? stop() : play(item)}
          >
            <View style={[styles.iconBox, active && styles.iconBoxActive]}>
              <Text style={styles.icon}>{active ? "⏸" : "🎵"}</Text>
            </View>
            <View style={styles.info}>
              <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
              <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
            </View>
          </TouchableOpacity>
        );
      }}
    />
  );
}

const styles = StyleSheet.create({
  empty: { color: COLORS.textMuted, textAlign: "center", padding: 16 },
  row: {
    backgroundColor: COLORS.bgLight, borderRadius: 8,
    borderWidth: 1, borderColor: COLORS.border,
    flexDirection: "row", alignItems: "center",
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
});
