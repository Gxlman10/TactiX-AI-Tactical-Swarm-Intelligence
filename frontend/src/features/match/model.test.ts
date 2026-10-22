import { describe, expect, it, beforeEach } from "vitest";
import {
  displayPoint,
  fixture,
  metricsAt,
  visibleEvents,
  timeOf,
} from "./model";
import { useStudio } from "../preferences/store";
describe("rehearsal evidence", () => {
  it("mirrors the visitor on both axes without mutating source points", () => {
    const point = { x: 82, y: 25 };
    expect(displayPoint(point, fixture.teams[1].id)).toEqual({ x: 18, y: 75 });
    expect(displayPoint(point, fixture.teams[0].id)).toEqual(point);
    expect(point).toEqual({ x: 82, y: 25 });
  });
  it("only exposes events at or before the cut and includes the goal at 62:00", () => {
    expect(
      visibleEvents(3719).some(
        (e) => e.id === fixture.context.climax!.event_ids.at(-1),
      ),
    ).toBe(false);
    expect(
      visibleEvents(3720).some(
        (e) => e.id === fixture.context.climax!.event_ids.at(-1),
      ),
    ).toBe(true);
    expect(visibleEvents(3720).every((e) => timeOf(e) <= 3720)).toBe(true);
    expect(metricsAt(3720)[1].goals).toBe(metricsAt(3719)[1].goals + 1);
  });
});
describe("studio state", () => {
  beforeEach(() => {
    useStudio.setState({
      second: fixture.initial,
      selectedId: visibleEvents(fixture.initial).at(-1)!.id,
      playing: false,
      mode: "analyst",
      language: "en",
      speed: 4,
    });
  });
  it("keeps temporal selection when changing language or mode", () => {
    const selected = useStudio.getState().selectedId;
    useStudio.getState().setLanguage("es");
    useStudio.getState().setMode("fan");
    expect(useStudio.getState().selectedId).toBe(selected);
    expect(useStudio.getState().second).toBe(3720);
  });
  it("clears future selection when seeking backwards and pauses", () => {
    useStudio.getState().togglePlay();
    useStudio.getState().seek(3719);
    const state = useStudio.getState();
    expect(state.playing).toBe(false);
    expect(
      visibleEvents(state.second).some((e) => e.id === state.selectedId),
    ).toBe(true);
    expect(state.selectedId).not.toBe(fixture.context.climax!.event_ids.at(-1));
  });
  it("ignores a future event selected programmatically", () => {
    useStudio.getState().seek(3719);
    const selected = useStudio.getState().selectedId;
    useStudio.getState().select(fixture.context.climax!.event_ids.at(-1)!);
    expect(useStudio.getState().selectedId).toBe(selected);
  });
  it("stops at the clip boundary and can replay without skipping kickoff observations", () => {
    useStudio.getState().seek(fixture.end - 1);
    useStudio.getState().togglePlay();
    useStudio.getState().advance();
    expect(useStudio.getState().second).toBe(fixture.end);
    expect(useStudio.getState().playing).toBe(false);
    useStudio.getState().togglePlay();
    expect(useStudio.getState().second).toBe(fixture.start);
  });
  it("rejects invalid clock input and clamps out-of-range seeks", () => {
    useStudio.getState().seek(Number.NaN);
    expect(useStudio.getState().second).toBe(fixture.initial);
    useStudio.getState().seek(-100);
    expect(useStudio.getState().second).toBe(fixture.start);
    expect(useStudio.getState().selectedId).toBeNull();
    useStudio.getState().seek(10000);
    expect(useStudio.getState().second).toBe(fixture.end);
  });
  it("validates persisted preferences without restoring actions or playback", async () => {
    localStorage.setItem(
      "tactix-preferences-v1",
      JSON.stringify({
        state: {
          language: "invalid",
          mode: "invalid",
          second: 999999,
          playing: true,
          seek: null,
        },
        version: 0,
      }),
    );
    await useStudio.persist.rehydrate();
    expect(useStudio.getState().language).toBe("en");
    expect(useStudio.getState().mode).toBe("analyst");
    expect(useStudio.getState().second).toBe(fixture.initial);
    expect(useStudio.getState().playing).toBe(false);
    expect(typeof useStudio.getState().seek).toBe("function");
  });
  it("persists preferences rather than stale clocks", () => {
    useStudio.getState().setLanguage("es");
    const saved = JSON.parse(localStorage.getItem("tactix-preferences-v1")!);
    expect(saved.state).toEqual({ language: "es", mode: "analyst" });
  });
});
