import React from "react";
import { View, Text, TouchableOpacity, ScrollView, StyleSheet } from "react-native";
import { Language } from "../context/AppContext";
import { COLORS } from "../constants/theme";

const LANGUAGES: Language[] = ["Telugu", "English", "Sanskrit", "Hindi"];

interface Props {
  selected: Language;
  onSelect: (lang: Language) => void;
}

export function LanguageFilter({ selected, onSelect }: Props) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false}
      style={styles.scroll} contentContainerStyle={styles.row}>
      {LANGUAGES.map((lang) => {
        const active = lang === selected;
        return (
          <TouchableOpacity
            key={lang}
            style={[styles.pill, active && styles.pillActive]}
            onPress={() => onSelect(lang)}
          >
            <Text style={[styles.label, active && styles.labelActive]}>
              {lang === "Telugu" ? "🌐 " : ""}{lang}
            </Text>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll: { marginBottom: 8 },
  row: { paddingHorizontal: 16, gap: 8, flexDirection: "row" },
  pill: {
    borderRadius: 12, borderWidth: 1, borderColor: COLORS.border,
    backgroundColor: COLORS.bgLight, paddingHorizontal: 14, paddingVertical: 5,
  },
  pillActive: { backgroundColor: COLORS.gold, borderColor: COLORS.gold },
  label: { color: COLORS.textMuted, fontSize: 12 },
  labelActive: { color: "#000", fontWeight: "700" },
});
