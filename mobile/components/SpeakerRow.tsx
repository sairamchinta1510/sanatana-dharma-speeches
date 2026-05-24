import React, { useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity,
  Image, StyleSheet,
} from "react-native";
import { VideoResult, AudioResult } from "../api/client";
import { COLORS } from "../constants/theme";
import { VideoPlaylist } from "./VideoPlaylist";
import { AudioPlaylist } from "./AudioPlaylist";

const PREVIEW_COUNT = 4;

type SpeakerRowProps =
  | { type: "video"; speaker: string; items: VideoResult[] }
  | { type: "audio"; speaker: string; items: AudioResult[] };

function VideoPreviewCard({ item, onExpand }: { item: VideoResult; onExpand: () => void }) {
  return (
    <TouchableOpacity style={styles.videoCard} onPress={onExpand} activeOpacity={0.75}>
      {item.thumbnail ? (
        <Image source={{ uri: item.thumbnail }} style={styles.thumbnail} resizeMode="cover" />
      ) : (
        <View style={[styles.thumbnail, styles.thumbPlaceholder]}>
          <Text style={styles.thumbIcon}>▶</Text>
        </View>
      )}
      <View style={styles.cardInfo}>
        <Text style={styles.cardTitle} numberOfLines={2}>{item.title}</Text>
        <Text style={styles.cardSub} numberOfLines={1}>{item.speaker}</Text>
      </View>
    </TouchableOpacity>
  );
}

function AudioPreviewCard({ item, onExpand }: { item: AudioResult; onExpand: () => void }) {
  return (
    <TouchableOpacity style={styles.audioCard} onPress={onExpand} activeOpacity={0.75}>
      <Text style={styles.audioIcon}>🎵</Text>
      <Text style={styles.cardTitle} numberOfLines={3}>{item.title}</Text>
      <Text style={styles.cardSub} numberOfLines={1}>{item.lang}</Text>
    </TouchableOpacity>
  );
}

export function SpeakerRow(props: SpeakerRowProps) {
  const { type, speaker, items } = props;
  const [expanded, setExpanded] = useState(false);
  const overflow = items.length - PREVIEW_COUNT;
  const previewItems = items.slice(0, PREVIEW_COUNT);

  return (
    <View style={styles.section}>
      {/* Header */}
      <View style={styles.header}>
        <Text style={styles.speakerName} numberOfLines={1}>{speaker}</Text>
        <Text style={styles.count}>{items.length}</Text>
        <TouchableOpacity onPress={() => setExpanded((e) => !e)} style={styles.toggleBtn}>
          <Text style={styles.toggleText}>{expanded ? "▲ Less" : "See all →"}</Text>
        </TouchableOpacity>
      </View>

      {expanded ? (
        <View style={styles.expandedList}>
          {type === "video"
            ? <VideoPlaylist videos={items as VideoResult[]} />
            : <AudioPlaylist audio={items as AudioResult[]} />}
        </View>
      ) : (
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={styles.scroll}
          contentContainerStyle={styles.scrollContent}
        >
          {type === "video"
            ? (previewItems as VideoResult[]).map((item) => (
                <VideoPreviewCard
                  key={item.video_id}
                  item={item}
                  onExpand={() => setExpanded(true)}
                />
              ))
            : (previewItems as AudioResult[]).map((item) => (
                <AudioPreviewCard
                  key={item.identifier}
                  item={item}
                  onExpand={() => setExpanded(true)}
                />
              ))}
          {overflow > 0 && (
            <TouchableOpacity style={styles.moreCard} onPress={() => setExpanded(true)}>
              <Text style={styles.moreCount}>+{overflow}</Text>
              <Text style={styles.moreLabel}>more</Text>
            </TouchableOpacity>
          )}
        </ScrollView>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  section: {
    marginBottom: 16,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 8,
    paddingHorizontal: 2,
  },
  speakerName: {
    flex: 1,
    color: COLORS.text,
    fontSize: 12,
    fontWeight: "700",
  },
  count: {
    color: COLORS.textMuted,
    fontSize: 10,
    marginRight: 8,
  },
  toggleBtn: { paddingVertical: 2, paddingHorizontal: 4 },
  toggleText: { color: COLORS.gold, fontSize: 11 },
  scroll: {},
  scrollContent: { paddingRight: 8 },
  expandedList: { marginTop: 4 },
  // Video preview card
  videoCard: {
    width: 160,
    backgroundColor: COLORS.bgLight,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    marginRight: 8,
    overflow: "hidden",
  },
  thumbnail: {
    width: 160,
    height: 90,
    backgroundColor: COLORS.bgLighter,
  },
  thumbPlaceholder: {
    alignItems: "center",
    justifyContent: "center",
  },
  thumbIcon: { color: COLORS.textMuted, fontSize: 20 },
  cardInfo: { padding: 6 },
  cardTitle: { color: COLORS.text, fontSize: 11, fontWeight: "600", lineHeight: 15 },
  cardSub: { color: COLORS.textMuted, fontSize: 9, marginTop: 2 },
  // Audio preview card
  audioCard: {
    width: 150,
    backgroundColor: COLORS.bgLight,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: COLORS.border,
    marginRight: 8,
    padding: 10,
    justifyContent: "flex-start",
  },
  audioIcon: { fontSize: 20, marginBottom: 6 },
  // "+N more" card
  moreCard: {
    width: 70,
    backgroundColor: "rgba(226,168,75,0.08)",
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "rgba(226,168,75,0.25)",
    alignItems: "center",
    justifyContent: "center",
    paddingVertical: 12,
  },
  moreCount: { color: COLORS.gold, fontSize: 18, fontWeight: "700" },
  moreLabel: { color: COLORS.textMuted, fontSize: 10, marginTop: 2 },
});
