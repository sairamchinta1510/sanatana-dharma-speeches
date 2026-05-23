import React, { useState } from "react";
import {
  View, TextInput, TouchableOpacity, Text,
  ScrollView, StyleSheet,
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

  return (
    <View style={styles.container}>
      <View style={styles.inputBox}>
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
        style={[styles.searchBtn, loading && styles.searchBtnDisabled]}
        onPress={submit}
        disabled={loading}
      >
        <Text style={styles.searchBtnText}>{loading ? "Searching..." : "🔍 Search"}</Text>
      </TouchableOpacity>
      <ScrollView horizontal showsHorizontalScrollIndicator={false} style={styles.chips}>
        {TOPIC_CHIPS.map((chip) => (
          <TouchableOpacity
            key={chip}
            style={styles.chip}
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
    backgroundColor: COLORS.bgLight,
    borderRadius: 12, borderWidth: 1.5, borderColor: COLORS.gold,
    paddingHorizontal: 14, paddingVertical: 10,
    shadowColor: COLORS.gold, shadowOpacity: 0.15, shadowRadius: 12,
    elevation: 4, minHeight: 100,
  },
  icon: { fontSize: 16, marginRight: 8, marginTop: 2 },
  input: {
    flex: 1, color: COLORS.text, fontSize: 14,
    lineHeight: 22, minHeight: 80,
  },
  searchBtn: {
    backgroundColor: COLORS.gold, borderRadius: 10,
    paddingVertical: 12, marginTop: 8,
    alignItems: "center", justifyContent: "center",
  },
  searchBtnDisabled: { opacity: 0.5 },
  searchBtnText: { color: "#000", fontWeight: "700", fontSize: 14 },
  chips: { marginTop: 10 },
  chip: {
    backgroundColor: COLORS.goldDim, borderWidth: 1,
    borderColor: "#e2a84b33", borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 4, marginRight: 8,
  },
  chipText: { color: COLORS.gold, fontSize: 11 },
});
