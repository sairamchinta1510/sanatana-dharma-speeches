import { Stack } from "expo-router";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { AppProvider } from "../context/AppContext";
import { StickyPlayer } from "../components/StickyPlayer";
import { StatusBar } from "expo-status-bar";

export default function RootLayout() {
  return (
    <SafeAreaProvider>
      <AppProvider>
        <StatusBar style="light" />
        <Stack
          screenOptions={{
            headerStyle: { backgroundColor: "#0d1117" },
            headerTintColor: "#e2a84b",
            headerTitleStyle: { fontWeight: "700" },
            contentStyle: { backgroundColor: "#0d1117" },
          }}
        >
          <Stack.Screen
            name="index"
            options={{ title: "🕉 Sanatana Dharma Speeches" }}
          />
          <Stack.Screen
            name="vyakhanam/[id]"
            options={{ title: "Vyakhanam", presentation: "modal" }}
          />
        </Stack>
        <StickyPlayer />
      </AppProvider>
    </SafeAreaProvider>
  );
}
