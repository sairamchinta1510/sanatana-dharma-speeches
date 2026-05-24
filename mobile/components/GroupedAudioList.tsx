import React from "react";
import { View } from "react-native";
import { AudioResult } from "../api/client";
import { SpeakerRow } from "./SpeakerRow";
import { AudioPlaylist } from "./AudioPlaylist";

function groupBySpeaker(items: AudioResult[]): [string, AudioResult[]][] {
  const map = new Map<string, AudioResult[]>();
  for (const item of items) {
    const key = item.speaker || "Unknown";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(item);
  }
  return Array.from(map.entries()).sort((a, b) => b[1].length - a[1].length);
}

interface Props {
  audio: AudioResult[];
}

export function GroupedAudioList({ audio }: Props) {
  if (audio.length === 0) return <AudioPlaylist audio={audio} />;
  const groups = groupBySpeaker(audio);
  if (groups.length <= 1) return <AudioPlaylist audio={audio} />;

  return (
    <View>
      {groups.map(([speaker, items]) => (
        <SpeakerRow key={speaker} type="audio" speaker={speaker} items={items} />
      ))}
    </View>
  );
}
