import React, { useState } from "react";
import {
  View, ScrollView, Text, TouchableOpacity, StyleSheet,
} from "react-native";
import { useApp } from "../context/AppContext";
import { SearchBar } from "../components/SearchBar";
import { LanguageFilter } from "../components/LanguageFilter";
import { GroupedVideoList } from "../components/GroupedVideoList";
import { GroupedAudioList } from "../components/GroupedAudioList";
import { VyakhanamsPanel } from "../components/VyakhanamsPanel";
import { StickyAudioBar } from "../components/StickyAudioBar";
import { COLORS } from "../constants/theme";
import { ExplanationPanel } from "../components/ExplanationPanel";

type ResultTab = "video" | "audio";

export default function HomeScreen() {
  const { videos, audio, vyakhanams, loading, budgetWarning, searchError,
          explanation, relatedTopics, language, setLanguage, search } =
    useApp();
  const [tab, setTab] = useState<ResultTab>("video");
  const hasResults = videos.length > 0 || audio.length > 0;

  return (
    <View style={styles.wrapper}>
      <ScrollView style={styles.screen} contentContainerStyle={styles.content}>
        <View style={styles.hero}>
          <Text style={styles.subtitle}>EXPLORE DHARMIC KNOWLEDGE</Text>
          <SearchBar onSearch={search} loading={loading} />
          <LanguageFilter selected={language} onSelect={setLanguage} />
        </View>

        {searchError && (
          <View style={styles.errorBanner}>
            <Text style={styles.errorText}>⚠️ Search error: {searchError}</Text>
          </View>
        )}

        {budgetWarning && (
          <View style={styles.warningBanner}>
            <Text style={styles.warningText}>
              ⚠️ Enhanced search paused — results shown as-is
            </Text>
          </View>
        )}

        <ExplanationPanel
          explanation={explanation}
          relatedTopics={relatedTopics}
          onTopicPress={search}
        />

        {hasResults && (
          <>
            <View style={styles.sectionBox}>
              <View style={styles.sectionHeader}>
                <Text style={styles.sectionLabel}>🎬 Videos &amp; Audio</Text>
                <View style={styles.tabs}>
                  <TouchableOpacity
                    style={[styles.tab, tab === "video" && styles.tabActive]}
                    onPress={() => setTab("video")}
                  >
                    <Text style={[styles.tabText, tab === "video" && styles.tabTextActive]}>
                      ▶ Videos ({videos.length})
                    </Text>
                  </TouchableOpacity>
                  <TouchableOpacity
                    style={[styles.tab, tab === "audio" && styles.tabActive]}
                    onPress={() => setTab("audio")}
                  >
                    <Text style={[styles.tabText, tab === "audio" && styles.tabTextActive]}>
                      🎵 Audio ({audio.length})
                    </Text>
                  </TouchableOpacity>
                </View>
              </View>
              <View style={styles.playlistArea}>
                {tab === "video" ? (
                  <GroupedVideoList videos={videos} />
                ) : (
                  <GroupedAudioList audio={audio} />
                )}
              </View>
            </View>

            <View style={styles.divider}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerSymbol}>✦ ✦ ✦</Text>
              <View style={styles.dividerLine} />
            </View>

            <VyakhanamsPanel vyakhanams={vyakhanams} />
          </>
        )}
      </ScrollView>
      <StickyAudioBar />
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: { flex: 1, backgroundColor: COLORS.bg },
  screen: { flex: 1 },
  content: { paddingBottom: 120 },
  hero: { paddingTop: 16 },
  subtitle: {
    textAlign: "center", color: COLORS.gold, fontSize: 10,
    letterSpacing: 2, opacity: 0.7, marginBottom: 8,
  },
  errorBanner: {
    marginHorizontal: 16, marginBottom: 8,
    backgroundColor: "#4a000022",
    borderWidth: 1, borderColor: "#cc4444",
    borderRadius: 8, padding: 8,
  },
  errorText: { color: "#ff6666", fontSize: 11, textAlign: "center" },
  warningBanner: {
    marginHorizontal: 16, marginBottom: 8,
    backgroundColor: "#7d4e0022",
    borderWidth: 1, borderColor: "#7d4e00",
    borderRadius: 8, padding: 8,
  },
  warningText: { color: "#f0a050", fontSize: 11, textAlign: "center" },
  sectionBox: {
    marginHorizontal: 16, backgroundColor: COLORS.bgLight,
    borderRadius: 8, borderWidth: 1, borderColor: COLORS.border,
    overflow: "hidden", marginBottom: 4,
  },
  sectionHeader: {
    backgroundColor: COLORS.bgLighter, paddingHorizontal: 14, paddingVertical: 6,
    borderBottomWidth: 1, borderBottomColor: COLORS.border,
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
  },
  sectionLabel: { color: COLORS.text, fontSize: 12, fontWeight: "700" },
  tabs: { flexDirection: "row" },
  tab: { paddingHorizontal: 10, paddingVertical: 4 },
  tabActive: { borderBottomWidth: 2, borderBottomColor: COLORS.gold },
  tabText: { color: COLORS.textMuted, fontSize: 11 },
  tabTextActive: { color: COLORS.gold, fontWeight: "600" },
  playlistArea: { padding: 10 },
  divider: {
    flexDirection: "row", alignItems: "center",
    marginHorizontal: 16, marginVertical: 12,
  },
  dividerLine: { flex: 1, height: 1, backgroundColor: COLORS.gold + "22" },
  dividerSymbol: { color: COLORS.gold + "55", fontSize: 12, marginHorizontal: 10 },
});
