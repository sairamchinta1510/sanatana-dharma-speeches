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

  return (
    <View style={styles.container}>
      <View style={styles.inputRow}>
        <Text style={styles.icon}>🔍</Text>
        <TextInput
          style={styles.input}
          value={text}
          onChangeText={setText}
          placeholder='Ask anything — "Siva Tatvam", "Bhagavad Gita Chapter 2 Sloka 5"...'
          placeholderTextColor={COLORS.textDim}
          onSubmitEditing={submit}
          returnKeyType="search"
          autoCorrect={false}
        />
        <TouchableOpacity style={styles.button} onPress={submit} disabled={loading}>
          <Text style={styles.buttonText}>{loading ? "..." : "Search"}</Text>
        </TouchableOpacity>
      </View>
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
  inputRow: {
    flexDirection: "row", alignItems: "center",
    backgroundColor: COLORS.bgLight,
    borderRadius: 28, borderWidth: 1.5, borderColor: COLORS.gold,
    paddingHorizontal: 16, paddingVertical: Platform.OS === "ios" ? 12 : 8,
    shadowColor: COLORS.gold, shadowOpacity: 0.15, shadowRadius: 12,
    elevation: 4,
  },
  icon: { fontSize: 16, marginRight: 8 },
  input: { flex: 1, color: COLORS.text, fontSize: 14 },
  button: {
    backgroundColor: COLORS.gold, borderRadius: 16,
    paddingHorizontal: 14, paddingVertical: 6, marginLeft: 8,
  },
  buttonText: { color: "#000", fontWeight: "700", fontSize: 12 },
  chips: { marginTop: 10 },
  chip: {
    backgroundColor: COLORS.goldDim, borderWidth: 1,
    borderColor: "#e2a84b33", borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 4, marginRight: 8,
  },
  chipText: { color: COLORS.gold, fontSize: 11 },
});
