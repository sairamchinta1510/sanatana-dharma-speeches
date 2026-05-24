import React, { useState } from "react";
import { View, Text, TouchableOpacity, StyleSheet, ScrollView } from "react-native";
import { COLORS } from "../constants/theme";

interface Props {
  explanation: string | null;
  relatedTopics: string[];
  onTopicPress: (topic: string) => void;
}

export function ExplanationPanel({ explanation, relatedTopics, onTopicPress }: Props) {
  const [collapsed, setCollapsed] = useState(false);

  if (!explanation) return null;

  return (
    <View style={styles.container}>
      <TouchableOpacity style={styles.header} onPress={() => setCollapsed((c) => !c)}>
        <Text style={styles.title}>✨ Topic Insight</Text>
        <Text style={styles.toggle}>{collapsed ? "▼ Show" : "▲ Hide"}</Text>
      </TouchableOpacity>

      {!collapsed && (
        <View style={styles.body}>
          <Text style={styles.explanation}>{explanation}</Text>
          {relatedTopics.length > 0 && (
            <View style={styles.relatedRow}>
              <Text style={styles.relatedLabel}>Explore:</Text>
              <ScrollView horizontal showsHorizontalScrollIndicator={false}>
                {relatedTopics.map((topic) => (
                  <TouchableOpacity
                    key={topic}
                    style={styles.chip}
                    onPress={() => onTopicPress(topic)}
                  >
                    <Text style={styles.chipText}>{topic}</Text>
                  </TouchableOpacity>
                ))}
              </ScrollView>
            </View>
          )}
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginHorizontal: 16, marginBottom: 12,
    backgroundColor: COLORS.bgLight,
    borderRadius: 10, borderWidth: 1.5, borderColor: COLORS.gold + "55",
    overflow: "hidden",
  },
  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    paddingHorizontal: 14, paddingVertical: 8,
    backgroundColor: COLORS.goldDim,
  },
  title: { color: COLORS.gold, fontSize: 12, fontWeight: "700" },
  toggle: { color: COLORS.textMuted, fontSize: 11 },
  body: { padding: 14 },
  explanation: { color: COLORS.text, fontSize: 13, lineHeight: 22 },
  relatedRow: { marginTop: 10, flexDirection: "row", alignItems: "center", gap: 8 },
  relatedLabel: { color: COLORS.textMuted, fontSize: 11 },
  chip: {
    backgroundColor: COLORS.bg, borderWidth: 1, borderColor: COLORS.gold + "44",
    borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4, marginRight: 6,
  },
  chipText: { color: COLORS.gold, fontSize: 11 },
});
