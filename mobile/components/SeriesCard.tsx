import React, { useState } from "react";
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet,
} from "react-native";
import { SeriesResult } from "../api/client";
import { COLORS } from "../constants/theme";

interface Props { series: SeriesResult }

export function SeriesCard({ series }: Props) {
  const [activeId, setActiveId] = useState<string | null>(null);

  const playingEpisode = series.episodes.find((e) => e.video_id === activeId);

  return (
    <View style={styles.card}>
      {/* Series header */}
      <View style={styles.header}>
        <View style={styles.headerText}>
          <Text style={styles.seriesTitle} numberOfLines={1}>{series.series_title}</Text>
          <Text style={styles.sub}>{series.speaker} • {series.episode_count} episodes</Text>
        </View>
        <View style={styles.badge}><Text style={styles.badgeText}>Series</Text></View>
      </View>

      {/* Inline player — shown when an episode is selected */}
      {activeId && (
        // @ts-ignore — iframe is not in RN types but works on web
        <iframe
          key={activeId}
          width="100%"
          height="200"
          src={`https://www.youtube.com/embed/${activeId}?autoplay=1`}
          allow="autoplay; encrypted-media"
          allowFullScreen
          style={{ border: "none", borderRadius: 0 } as React.CSSProperties}
        />
      )}

      {/* Episode strip */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.strip}
        contentContainerStyle={styles.stripContent}
      >
        {series.episodes.map((ep) => {
          const isActive = ep.video_id === activeId;
          return (
            <TouchableOpacity
              key={ep.video_id}
              style={[styles.chip, isActive && styles.chipActive]}
              onPress={() => setActiveId(isActive ? null : ep.video_id)}
            >
              <Text style={styles.chipPlay}>{isActive ? "⏸" : "▶"}</Text>
              <Text style={[styles.chipTitle, isActive && styles.chipTitleActive]} numberOfLines={2}>
                {ep.title}
              </Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>

      {/* Now playing label */}
      {playingEpisode && (
        <View style={styles.nowPlaying}>
          <Text style={styles.nowPlayingText} numberOfLines={1}>
            ▶ {playingEpisode.title}
          </Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: COLORS.bgLight, borderRadius: 8,
    borderWidth: 1, borderColor: COLORS.border,
    marginBottom: 6, overflow: "hidden",
  },
  header: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    padding: 10, gap: 8,
  },
  headerText: { flex: 1 },
  seriesTitle: { color: COLORS.text, fontSize: 12, fontWeight: "700" },
  sub: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
  badge: {
    backgroundColor: COLORS.goldDim, borderRadius: 4,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  badgeText: { color: COLORS.gold, fontSize: 9, fontWeight: "600" },
  strip: { borderTopWidth: 1, borderTopColor: COLORS.border },
  stripContent: { padding: 8, gap: 6, flexDirection: "row" },
  chip: {
    backgroundColor: COLORS.bgLighter, borderRadius: 6,
    borderWidth: 1, borderColor: COLORS.border,
    padding: 6, maxWidth: 120, alignItems: "center", gap: 4,
  },
  chipActive: { borderColor: COLORS.gold + "88", backgroundColor: COLORS.bgLighter },
  chipPlay: { color: COLORS.textMuted, fontSize: 10 },
  chipTitle: { color: COLORS.textMuted, fontSize: 9, textAlign: "center" },
  chipTitleActive: { color: COLORS.gold },
  nowPlaying: {
    backgroundColor: COLORS.goldDim, borderTopWidth: 1,
    borderTopColor: COLORS.gold + "33", padding: 6,
  },
  nowPlayingText: { color: COLORS.gold, fontSize: 9, fontWeight: "600" },
});
