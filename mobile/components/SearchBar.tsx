import React, { useState } from "react";
import {
  View, TextInput, TouchableOpacity, Text,
  ScrollView, StyleSheet, Platform,
} from "react-native";
import { COLORS } from "../constants/theme";

const TOPIC_CHIPS = [
  "Bhagavad Gita", "Siva Tatvam", "Upanishads", "Ramayanam", "Karma Yoga",
];

interface Props {
  onSearch: (query: string) => void;
  loading: boolean;
}

export function SearchBar({ onSearch, loading }: Props) {
  const [text, setText] = useState("");

  const submit = () => { if (text.trim()) onSearch(text.trim()); };

  const glassStyle = Platform.OS === "web"
    ? { backdropFilter: "blur(16px)", WebkitBackdropFilter: "blur(16px)" } as any
    : {};

  return (
    <View style={styles.container}>
      <View style={[styles.inputBox, glassStyle]}>
        <Text style={styles.icon}>🔍</Text>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder={"Ask anything about Sanatan Dharma...\n\"Explain Bhagavad Gita Chapter 2 Sloka 47\"\n\"What is Siva Tatvam according to Chaganti?\""}
          placeholderTextColor={COLORS.textDim}
          multiline
          numberOfLines={4}
          textAlignVertical="top"
          autoCorrect={false}
        />
      </View>
      <TouchableOpacity
        style={[styles.searchBtn, glassStyle, loading && styles.searchBtnDisabled]}
        onPress={submit}
        disabled={loading}
      >
        <Text style={styles.searchBtnText}>{loading ? "Searching..." : "🔍 Search"}</Text>
      </TouchableOpacity>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chips}>
        {TOPIC_CHIPS.map((chip) => (
          <TouchableOpacity
            key={chip}
            style={[styles.chip, glassStyle]}
            onPress={() => { setText(chip); onSearch(chip); }}
          >
            <Text style={styles.chipText}>{chip}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { paddingHorizontal: 16, paddingVertical: 12 },
  inputBox: {
    flexDirection: "row",
    backgroundColor: "rgba(255, 255, 255, 0.06)",
    borderRadius: 16,
    paddingHorizontal: 14, paddingVertical: 12,
    shadowColor: "#000", shadowOpacity: 0.5, shadowRadius: 24,
    shadowOffset: { width: 0, height: 4 },
    elevation: 6, minHeight: 100,
  },
  icon: { fontSize: 16, marginRight: 8, marginTop: 2, opacity: 0.6 },
  input: {
    flex: 1, color: COLORS.text, fontSize: 14,
    lineHeight: 22, minHeight: 80,
  },
  searchBtn: {
    backgroundColor: "rgba(226, 168, 75, 0.85)",
    borderRadius: 12,
    borderWidth: 1,
    borderColor: "rgba(255, 255, 255, 0.15)",
    paddingVertical: 12, marginTop: 8,
    alignItems: "center", justifyContent: "center",
    shadowColor: "#000", shadowOpacity: 0.3, shadowRadius: 10,
    shadowOffset: { width: 0, height: 2 },
  },
  searchBtnDisabled: { opacity: 0.4 },
  searchBtnText: { color: "#0d1117", fontWeight: "700", fontSize: 14 },
  chips: { marginTop: 10 },
  chip: {
    backgroundColor: "rgba(255, 255, 255, 0.07)",
    borderRadius: 20,
    paddingHorizontal: 12, paddingVertical: 5, marginRight: 8,
  },
  chipText: { color: COLORS.textMuted, fontSize: 11 },
});
