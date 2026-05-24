import React, { useState } from "react";
import {
  View, TextInput, TouchableOpacity, Text,
  ScrollView, StyleSheet, Platform,
} from "react-native";
import { COLORS } from "../constants/theme";

const TOPIC_CHIPS = [
  "✦ Bhagavad Gita",
  "✦ Siva Tatvam",
  "✦ Upanishads",
  "✦ Ramayanam",
  "✦ Karma Yoga",
  "✦ Chaganti Pravachanam",
];

interface Props {
  onSearch: (query: string) => void;
  loading: boolean;
}

export function SearchBar({ onSearch, loading }: Props) {
  const [text, setText] = useState("");

  const submit = () => {
    if (text.trim() && !loading) onSearch(text.trim());
  };

  const handleKeyPress = (e: any) => {
    if (Platform.OS === "web" && e.nativeEvent.key === "Enter" && !e.nativeEvent.shiftKey) {
      e.preventDefault?.();
      submit();
    }
  };

  const glassStyle = Platform.OS === "web"
    ? { backdropFilter: "blur(20px)", WebkitBackdropFilter: "blur(20px)" } as any
    : {};

  return (
    <View style={styles.container}>
      {/* Card */}
      <View style={[styles.card, glassStyle]}>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          onKeyPress={handleKeyPress}
          placeholder={"చాగంటి గారి భగవద్గీత గురించి చెప్పండి...\n\"What is Nishkama Karma?\"\n\"Explain Siva Tatvam in Telugu\""}
          placeholderTextColor={COLORS.textDim}
          multiline
          numberOfLines={3}
          textAlignVertical="top"
          autoCorrect={false}
        />
        {/* Card footer */}
        <View style={styles.cardFooter}>
          <Text style={styles.hint}>
            {text.length > 0 ? `${text.length} chars` : "AI-powered · Telugu · English"}
          </Text>
          <TouchableOpacity
            style={[styles.submitBtn, (loading || !text.trim()) && styles.submitBtnDisabled]}
            onPress={submit}
            disabled={loading || !text.trim()}
          >
            <Text style={styles.submitIcon}>{loading ? "…" : "↑"}</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Topic chips */}
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        style={styles.chips}
        contentContainerStyle={styles.chipsContent}
      >
        {TOPIC_CHIPS.map((chip) => {
          const label = chip.replace("✦ ", "");
          return (
            <TouchableOpacity
              key={chip}
              style={[styles.chip, glassStyle]}
              onPress={() => { setText(label); onSearch(label); }}
            >
              <Text style={styles.chipText}>{chip}</Text>
            </TouchableOpacity>
          );
        })}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingHorizontal: 16, paddingVertical: 12 },
  card: {
    backgroundColor: "rgba(22, 27, 34, 0.95)",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "rgba(226, 168, 75, 0.30)",
    paddingHorizontal: 16,
    paddingTop: 14,
    paddingBottom: 10,
    shadowColor: "#000",
    shadowOpacity: 0.5,
    shadowRadius: 24,
    shadowOffset: { width: 0, height: 6 },
    elevation: 8,
  },
  input: {
    color: COLORS.text,
    fontSize: 14,
    lineHeight: 22,
    minHeight: 72,
    outlineWidth: 0,
  } as any,
  cardFooter: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: 8,
    borderTopWidth: 1,
    borderTopColor: COLORS.border,
    paddingTop: 8,
  },
  hint: { color: COLORS.textDim, fontSize: 10 },
  submitBtn: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: COLORS.gold,
    alignItems: "center",
    justifyContent: "center",
  },
  submitBtnDisabled: { opacity: 0.35 },
  submitIcon: { color: "#0d1117", fontSize: 16, fontWeight: "800", lineHeight: 18 },
  chips: { marginTop: 10 },
  chipsContent: { paddingRight: 16 },
  chip: {
    backgroundColor: "rgba(226, 168, 75, 0.08)",
    borderRadius: 20,
    borderWidth: 1,
    borderColor: "rgba(226, 168, 75, 0.20)",
    paddingHorizontal: 12,
    paddingVertical: 5,
    marginRight: 8,
  },
  chipText: { color: COLORS.gold, fontSize: 11, opacity: 0.85 },
});
