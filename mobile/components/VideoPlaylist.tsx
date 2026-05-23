import React, { useState } from "react";
import {
  View, Text, FlatList, TouchableOpacity,
  StyleSheet, Platform, Dimensions,
} from "react-native";
import YoutubePlayer from "react-native-youtube-iframe";
import { VideoResult } from "../api/client";
import { COLORS } from "../constants/theme";
import { useApp } from "../context/AppContext";

const { width } = Dimensions.get("window");

interface Props { videos: VideoResult[] }

export function VideoPlaylist({ videos }: Props) {
  const { setCurrentPlayer } = useApp();
  const [playingId, setPlayingId] = useState<string | null>(null);

  const play = (item: VideoResult) => {
    setPlayingId(item.video_id);
    setCurrentPlayer({ type: "video", item });
  };

  if (videos.length === 0) {
    return <Text style={styles.empty}>No videos found</Text>;
  }

  return (
    <FlatList
      data={videos}
      keyExtractor={(item) => item.video_id}
      scrollEnabled={false}
      renderItem={({ item }) => (
        <View style={[styles.row, playingId === item.video_id && styles.rowActive]}>
          {playingId === item.video_id && Platform.OS !== "web" ? (
            <YoutubePlayer
              height={200}
              width={width - 32}
              play
              videoId={item.video_id}
              onChangeState={(state) => {
                if (state === "ended") setPlayingId(null);
              }}
            />
          ) : null}
          {playingId === item.video_id && Platform.OS === "web" ? (
            <iframe
              width="100%"
              height="200"
              src={`https://www.youtube.com/embed/${item.video_id}?autoplay=1`}
              allow="autoplay; encrypted-media"
              allowFullScreen
              style={{ border: "none", borderRadius: 6 } as React.CSSProperties}
            />
          ) : null}
          <TouchableOpacity style={styles.meta} onPress={() => play(item)}>
            <View style={styles.playBtn}>
              <Text style={styles.playIcon}>▶</Text>
            </View>
            <View style={styles.info}>
              <Text style={styles.title} numberOfLines={2}>{item.title}</Text>
              <Text style={styles.sub}>{item.speaker} • {item.lang}</Text>
            </View>
            {playingId === item.video_id && (
              <View style={styles.badge}><Text style={styles.badgeText}>Playing</Text></View>
            )}
          </TouchableOpacity>
        </View>
      )}
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
