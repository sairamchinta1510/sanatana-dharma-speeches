import React, { useState, useEffect, useMemo } from "react";
import { View, Text, FlatList, TouchableOpacity, StyleSheet } from "react-native";
import { VideoResult, SeriesResult } from "../api/client";
import { SeriesCard } from "./SeriesCard";
import { COLORS } from "../constants/theme";

interface Props { videos: VideoResult[] }

/** Group videos by speaker. Groups of 3+ → SeriesResult. Fewer → flat VideoResult rows. */
function groupVideos(videos: VideoResult[]): (VideoResult | SeriesResult)[] {
  const byChannel = new Map<string, VideoResult[]>();
  for (const v of videos) {
    const group = byChannel.get(v.speaker) ?? [];
    group.push(v);
    byChannel.set(v.speaker, group);
  }

  const items: (VideoResult | SeriesResult)[] = [];
  for (const [speaker, group] of byChannel) {
    if (group.length >= 3) {
      // Infer series title from first 4 words of first video title
      const firstWords = group[0].title.split(" ").slice(0, 4).join(" ");
      const seriesTitle = firstWords || group[0].title;

      const episodes = group.slice(0, 20).map((v) => ({
        video_id: v.video_id,
        title: v.title,
        thumbnail: v.thumbnail,
      }));

      items.push({
        type: "series",
        speaker,
        series_title: seriesTitle,
        episode_count: episodes.length,
        episodes,
        lang: group[0].lang,
      });
    } else {
      items.push(...group);
    }
  }
  return items;
}

export function VideoPlaylist({ videos }: Props) {
  const [playingId, setPlayingId] = useState<string | null>(null);

  useEffect(() => {
    setPlayingId(null);
  }, [videos]);

  if (videos.length === 0) {
    return <Text style={styles.empty}>No videos found</Text>;
  }

  const items = useMemo(() => groupVideos(videos), [videos]);

  return (
    <FlatList
      data={items}
      keyExtractor={(item) =>
        "type" in item ? `series-${item.speaker}` : item.video_id
      }
      scrollEnabled={false}
      renderItem={({ item }) => {
        if ("type" in item) {
          return <SeriesCard series={item} />;
        }
        // Flat single-video row
        const active = playingId === item.video_id;
        return (
          <View style={[styles.row, active && styles.rowActive]}>
            {active && (
              // @ts-expect-error — iframe not in RN types but works on web
              <iframe
                title="YouTube video player"
                width="100%"
                height="200"
                src={`https://www.youtube.com/embed/${item.video_id}?autoplay=1`}
                allow="autoplay; encrypted-media"
                allowFullScreen
                style={{ border: "none", borderRadius: 0 } as React.CSSProperties}
              />
            )}
            <TouchableOpacity style={styles.meta} onPress={() => setPlayingId(active ? null : item.video_id)}>
              <View style={styles.playBtn}>
                <Text style={styles.playIcon}>{active ? "⏸" : "▶"}</Text>
              </View>
              <View style={styles.info}>
                <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
                <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
              </View>
              {active && (
                <View style={styles.badge}><Text style={styles.badgeText}>Playing</Text></View>
              )}
            </TouchableOpacity>
          </View>
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
    marginBottom: 6, overflow: "hidden",
  },
  rowActive: { borderColor: COLORS.gold + "88" },
  meta: { flexDirection: "row", alignItems: "center", padding: 10, gap: 10 },
  playBtn: {
    width: 36, height: 28, backgroundColor: COLORS.bgLighter,
    borderRadius: 4, alignItems: "center", justifyContent: "center",
  },
  playIcon: { color: COLORS.textMuted, fontSize: 12 },
  info: { flex: 1 },
  title: { color: COLORS.text, fontSize: 12, fontWeight: "600" },
  sub: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
  badge: {
    backgroundColor: COLORS.goldDim, borderWidth: 1,
    borderColor: COLORS.gold + "44", borderRadius: 4,
    paddingHorizontal: 6, paddingVertical: 2,
  },
  badgeText: { color: COLORS.gold, fontSize: 8 },
});
