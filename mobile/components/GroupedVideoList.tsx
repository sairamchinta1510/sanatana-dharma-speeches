import React from "react";
import { View } from "react-native";
import { VideoResult } from "../api/client";
import { SpeakerRow } from "./SpeakerRow";
import { VideoPlaylist } from "./VideoPlaylist";

function groupBySpeaker(items: VideoResult[]): [string, VideoResult[]][] {
  const map = new Map<string, VideoResult[]>();
  for (const item of items) {
    const key = item.speaker || "Unknown";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  // Sort: most results first
  return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
}

interface Props {
  videos: VideoResult[];
}

export function GroupedVideoList({ videos }: Props) {
  if (videos.length === 0) return <VideoPlaylist videos={videos} />;
  const groups = groupBySpeaker(videos);
  // If every result is from the same speaker, no grouping needed
  if (groups.length <= 1) return <VideoPlaylist videos={videos} />;

  return (
    <View>
      {groups.map(([speaker, items]) => (
        <SpeakerRow key={speaker} type="video" speaker={speaker} items={items} />
      ))}
    </View>
  );
}
