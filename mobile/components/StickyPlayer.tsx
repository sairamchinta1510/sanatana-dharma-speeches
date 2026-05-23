import React from "react";
import { View, Text, TouchableOpacity, StyleSheet } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useApp } from "../context/AppContext";
import { COLORS } from "../constants/theme";

export function StickyPlayer() {
  const { currentPlayer, setCurrentPlayer } = useApp();
  const insets = useSafeAreaInsets();

  if (!currentPlayer) return null;

  const title = currentPlayer.type === "video"
    ? currentPlayer.item.title
    : currentPlayer.item.title;
  const speaker = currentPlayer.type === "video"
    ? currentPlayer.item.speaker
    : currentPlayer.item.speaker;

  return (
    <View style={[styles.container, { paddingBottom: insets.bottom + 8 }]}>
      <View style={styles.thumb}>
        <Text style={styles.thumbIcon}>
          {currentPlayer.type === "video" ? "▶" : "🎵"}
        </Text>
      </View>
      <View style={styles.info}>
        <Text style={styles.title} numberOfLines={1}>{title}</Text>
        <Text style={styles.speaker} numberOfLines={1}>{speaker}</Text>
        <View style={styles.progressBar}>
          <View style={styles.progressFill} />
        </View>
      </View>
      <TouchableOpacity onPress={() => setCurrentPlayer(null)} style={styles.closeBtn}>
        <Text style={styles.closeText}>✕</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: "absolute", bottom: 0, left: 0, right: 0,
    backgroundColor: COLORS.bgLight,
    borderTopWidth: 1, borderTopColor: COLORS.border,
    flexDirection: "row", alignItems: "center",
    paddingHorizontal: 16, paddingTop: 8,
    elevation: 10, zIndex: 100,
  },
  thumb: {
    width: 44, height: 36, backgroundColor: COLORS.bg,
    borderRadius: 4, alignItems: "center", justifyContent: "center", marginRight: 10,
  },
  thumbIcon: { color: COLORS.gold, fontSize: 16 },
  info: { flex: 1 },
  title: { color: COLORS.text, fontSize: 11, fontWeight: "600" },
  speaker: { color: COLORS.textMuted, fontSize: 10 },
  progressBar: {
    height: 3, backgroundColor: COLORS.border, borderRadius: 2, marginTop: 4,
  },
  progressFill: {
    width: "30%", height: "100%",
    backgroundColor: COLORS.gold, borderRadius: 2,
  },
  closeBtn: { padding: 8 },
  closeText: { color: COLORS.textMuted, fontSize: 14 },
});
