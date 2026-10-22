import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import { fixture, timeOf, visibleEvents } from "../match/model";
export type Language = "en" | "es";
export type Mode = "analyst" | "fan";
type StudioState = {
  language: Language;
  mode: Mode;
  second: number;
  selectedId: string | null;
  playing: boolean;
  speed: number;
  setLanguage: (language: Language) => void;
  setMode: (mode: Mode) => void;
  seek: (second: number) => void;
  select: (id: string) => void;
  togglePlay: () => void;
  advance: () => void;
  setSpeed: (speed: number) => void;
};
const lastAt = (second: number) => visibleEvents(second).at(-1)?.id ?? null;
export const useStudio = create<StudioState>()(
  persist(
    (set, get) => ({
      language: "en",
      mode: "analyst",
      second: fixture.initial,
      selectedId: lastAt(fixture.initial),
      playing: false,
      speed: 4,
      setLanguage: (language) => set({ language }),
      setMode: (mode) => set({ mode }),
      seek: (value) => {
        if (!Number.isFinite(value)) return;
        const second = Math.max(
          fixture.start,
          Math.min(fixture.end, Math.round(value)),
        );
        set({ second, selectedId: lastAt(second), playing: false });
      },
      select: (id) => {
        const event = fixture.events.find((item) => item.id === id);
        if (event && timeOf(event) <= get().second)
          set({ selectedId: id, playing: false });
      },
      togglePlay: () =>
        set((state) =>
          state.second === fixture.end
            ? {
                playing: true,
                second: fixture.start,
                selectedId: lastAt(fixture.start),
              }
            : { playing: !state.playing },
        ),
      advance: () => {
        if (!get().playing) return;
        const second = Math.min(fixture.end, get().second + 1);
        set({
          second,
          selectedId: lastAt(second),
          playing: second < fixture.end,
        });
      },
      setSpeed: (speed) => {
        if ([1, 4, 12].includes(speed)) set({ speed });
      },
    }),
    {
      name: "tactix-preferences-v1",
      storage: createJSONStorage(() => localStorage),
      partialize: ({ language, mode }) => ({ language, mode }),
      merge: (saved, current) => {
        const data =
          saved && typeof saved === "object"
            ? (saved as Record<string, unknown>)
            : {};
        return {
          ...current,
          language: data.language === "es" ? "es" : "en",
          mode: data.mode === "fan" ? "fan" : "analyst",
        };
      },
    },
  ),
);
