import React, { useState } from "react";
import {
  View, Text, ScrollView, TouchableOpacity,
  Modal, StyleSheet, SafeAreaView,
} from "react-native";
import { VyakhanamResult } from "../api/client";
import { COLORS, SCHOLAR_COLORS } from "../constants/theme";

interface Props { vyakhanams: VyakhanamResult[] }

export function VyakhanamsPanel({ vyakhanams }: Props) {
  const [expanded, setExpanded] = useState(false);

  if (vyakhanams.length === 0) return null;

  const content = (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.scrollContent}>
      {vyakhanams.map((v, i) => (
        <View key={v.scholar} style={[styles.entry,
          { borderLeftColor: SCHOLAR_COLORS[i % SCHOLAR_COLORS.length] }]}>
          <View style={styles.header}>
            <Text style={[styles.scholar,
              { color: SCHOLAR_COLORS[i % SCHOLAR_COLORS.length] }]}>
              {v.scholar}
            </Text>
            <View style={[styles.badge,
              { backgroundColor: SCHOLAR_COLORS[i % SCHOLAR_COLORS.length] + "22" }]}>
              <Text style={[styles.badgeText,
                { color: SCHOLAR_COLORS[i % SCHOLAR_COLORS.length] }]}>
                {v.lang} • {v.affiliation}
              </Text>
            </View>
          </View>
          <Text style={styles.text}>{v.highlight ?? v.text}</Text>
        </View>
      ))}
    </ScrollView>
  );

  return (
    <View style={styles.container}>
      <View style={styles.sectionHeader}>
        <View style={styles.titleRow}>
          <Text style={styles.sectionTitle}>📖 వ్యాఖ్యానాలు — Vyakhanams</Text>
          <View style={styles.countBadge}>
            <Text style={styles.countText}>{vyakhanams.length} scholars</Text>
          </View>
        </View>
        <TouchableOpacity onPress={() => setExpanded(true)}>
          <Text style={styles.expandText}>⤢ Expand</Text>
        </TouchableOpacity>
      </View>
      <View style={styles.panel}>{content}</View>

      <Modal visible={expanded} animationType="slide" onRequestClose={() => setExpanded(false)}>
        <SafeAreaView style={styles.modal}>
          <View style={styles.modalHeader}>
            <Text style={styles.modalTitle}>📖 Vyakhanams</Text>
            <TouchableOpacity onPress={() => setExpanded(false)}>
              <Text style={styles.closeText}>✕ Close</Text>
            </TouchableOpacity>
          </View>
          {content}
        </SafeAreaView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginHorizontal: 16, marginBottom: 100 },
  sectionHeader: {
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    marginBottom: 8,
  },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  sectionTitle: { color: COLORS.text, fontSize: 13, fontWeight: "700" },
  countBadge: {
    backgroundColor: COLORS.goldDim, borderRadius: 8,
    paddingHorizontal: 8, paddingVertical: 2,
  },
  countText: { color: COLORS.gold, fontSize: 9 },
  expandText: { color: COLORS.textMuted, fontSize: 11 },
  panel: {
    backgroundColor: COLORS.bgLight, borderRadius: 8,
    borderWidth: 1, borderTopWidth: 2,
    borderColor: COLORS.border, borderTopColor: COLORS.gold + "66",
    maxHeight: 280, overflow: "hidden",
  },
  scroll: {},
  scrollContent: { padding: 12, gap: 12 },
  entry: { borderLeftWidth: 3, paddingLeft: 10 },
  header: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 4 },
  scholar: { fontSize: 11, fontWeight: "700" },
  badge: { borderRadius: 8, paddingHorizontal: 6, paddingVertical: 1 },
  badgeText: { fontSize: 8 },
  text: { color: COLORS.textMuted, fontSize: 11, lineHeight: 18 },
  modal: { flex: 1, backgroundColor: COLORS.bg },
  modalHeader: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    padding: 16, borderBottomWidth: 1, borderBottomColor: COLORS.border,
  },
  modalTitle: { color: COLORS.text, fontSize: 16, fontWeight: "700" },
  closeText: { color: COLORS.gold, fontSize: 13 },
});
