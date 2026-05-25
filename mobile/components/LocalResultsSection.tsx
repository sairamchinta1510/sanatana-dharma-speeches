import React, { useState } from "react";
import {
  View,
  Text,
  TouchableOpacity,
  Linking,
  StyleSheet,
  ScrollView,
} from "react-native";
import { LocalResult } from "../api/client";
import { COLORS } from "../constants/theme";

interface Props {
  results: LocalResult[];
}

const CATEGORY_COLORS: Record<string, string> = {
  Veda: "#FF9933",
  Puran: "#4CAF50",
  Upanishad: "#2196F3",
  Bonus: "#9C27B0",
};

function ResultCard({ item }: { item: LocalResult }) {
  const [expanded, setExpanded] = useState(false);
  const badgeColor = CATEGORY_COLORS[item.category] ?? COLORS.gold;
  const shortExcerpt = item.excerpt.length > 150
    ? `${item.excerpt.slice(0, 150)}…`
    : item.excerpt;

  return (
    <View style={styles.card}>
      <View style={styles.cardHeader}>
        <View style={[styles.badge, { backgroundColor: `${badgeColor}33`, borderColor: badgeColor }]}>
          <Text style={[styles.badgeText, { color: badgeColor }]}>{item.category}</Text>
        </View>
        <Text style={styles.cardTitle} numberOfLines={1}>
          {item.title} — Page {item.page_number}
        </Text>
      </View>

      <TouchableOpacity onPress={() => setExpanded((e) => !e)}>
        <Text style={styles.excerpt}>
          {expanded ? item.excerpt : shortExcerpt}
        </Text>
        {item.excerpt.length > 150 && (
          <Text style={styles.expandToggle}>{expanded ? "చూపించకు ▲" : "మరింత చదవండి ▼"}</Text>
        )}
      </TouchableOpacity>

      {item.pdf_url ? (
        <TouchableOpacity
          style={styles.pdfButton}
          onPress={() => Linking.openURL(item.pdf_url)}
        >
          <Text style={styles.pdfButtonText}>📄 PDF తెరవండి</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

export function LocalResultsSection({ results }: Props) {
  if (results.length === 0) return null;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.title}>📚 స్థానిక గ్రంథాలు</Text>
        <Text style={styles.subtitle}>Local Scriptures</Text>
      </View>
      <ScrollView horizontal={false} showsVerticalScrollIndicator={false}>
        {results.map((item, idx) => (
          <ResultCard key={`${item.pdf_key}-${item.page_number}-${idx}`} item={item} />
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    marginHorizontal: 16,
    marginBottom: 12,
    backgroundColor: COLORS.bgLight,
    borderRadius: 10,
    borderWidth: 1.5,
    borderColor: `${COLORS.gold}33`,
    overflow: "hidden",
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 14,
    paddingVertical: 8,
    backgroundColor: COLORS.bgLight,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  title: {
    color: COLORS.gold,
    fontSize: 12,
    fontWeight: "700",
  },
  subtitle: {
    color: COLORS.textMuted,
    fontSize: 10,
    opacity: 0.7,
  },
  card: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderBottomWidth: 1,
    borderBottomColor: COLORS.border,
  },
  cardHeader: {
    flexDirection: "row",
    alignItems: "center",
    marginBottom: 6,
    gap: 8,
  },
  badge: {
    borderWidth: 1,
    borderRadius: 8,
    paddingHorizontal: 7,
    paddingVertical: 2,
  },
  badgeText: {
    fontSize: 9,
    fontWeight: "700",
    letterSpacing: 0.5,
  },
  cardTitle: {
    color: COLORS.text,
    fontSize: 12,
    fontWeight: "600",
    flex: 1,
  },
  excerpt: {
    color: COLORS.text,
    fontSize: 13,
    lineHeight: 20,
    marginBottom: 4,
  },
  expandToggle: {
    color: COLORS.gold,
    fontSize: 11,
    marginBottom: 6,
  },
  pdfButton: {
    alignSelf: "flex-start",
    marginTop: 6,
    paddingHorizontal: 12,
    paddingVertical: 5,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: `${COLORS.gold}66`,
    backgroundColor: COLORS.bg,
  },
  pdfButtonText: {
    color: COLORS.gold,
    fontSize: 11,
    fontWeight: "600",
  },
});
