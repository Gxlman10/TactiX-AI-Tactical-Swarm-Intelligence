import { describe, expect, it } from "vitest";
import { displayPoint } from "../match/model";
import {
  edgeIds,
  edgePath,
  metricText,
  nodeIds,
  occurrences,
  resolveEvidence,
  validCut,
} from "./evidence";
import {
  analysis,
  events,
  matchId,
  receiver,
  sender,
  teams,
} from "./test-data";

describe("analysis source boundaries", () => {
  it("resolves unique evidence in the requested match and cut, preserving source order", () => {
    const source = [
      ...events,
      { ...events[0], id: "future", minute: 9 },
      { ...events[0], id: "foreign", match_id: "another-match" },
    ];
    const result = resolveEvidence(
      ["p2", "p1", "p2", "future", "foreign", "missing"],
      source,
      matchId,
      300,
    );
    expect(result.events.map((event) => event.id)).toEqual(["p2", "p1"]);
    expect(result.missing).toEqual(["future", "foreign", "missing"]);
  });
  it("separates the directed edge from its reciprocal link using backend evidence", () => {
    const metric = analysis().response!.snapshot.teams[0].values[0];
    expect(
      edgeIds(
        { from_player_id: sender.id, to_player_id: receiver.id, passes: 2 },
        metric,
        events,
        teams[0].id,
        matchId,
        300,
      ),
    ).toEqual(["p1", "p2"]);
    expect(
      nodeIds(sender.id, metric, events, teams[0].id, matchId, 300),
    ).toEqual(["p1", "p2", "p3"]);
    expect(
      edgeIds(
        { from_player_id: sender.id, to_player_id: receiver.id, passes: 2 },
        {
          ...metric,
          evidence: {
            event_ids: ["p1"],
            description: "Only one loaded source",
          },
        },
        events,
        teams[0].id,
        matchId,
        300,
      ),
    ).toEqual(["p1"]);
  });
  it("rejects mismatched revisions and future metric cuts", () => {
    const response = analysis().response!;
    expect(validCut(response, matchId, 2, 300)).toBe(true);
    expect(validCut(response, matchId, 3, 300)).toBe(false);
    expect(validCut(response, matchId, 2, 299)).toBe(false);
    expect(validCut(response, "another-match", 2, 300)).toBe(false);
  });
  it("does not confuse unavailable ratios with measured zero", () => {
    expect(metricText(undefined, "en")).toBe("—");
    expect(metricText({ key: "ppda", value: 0 }, "en")).toBe("0");
    expect(metricText({ key: "ratio", value: 37.5, unit: "%" }, "es")).toBe(
      "37,5%",
    );
  });
  it("keeps completed historical occurrences but withholds a future live climax", () => {
    const data = analysis();
    expect(
      occurrences(data.context, data.fixtures, matchId, 139).map(
        (row) => row.current,
      ),
    ).toEqual([false]);
    expect(
      occurrences(data.context, data.fixtures, matchId, 140).map(
        (row) => row.current,
      ),
    ).toEqual([false, true]);
    expect(
      occurrences(
        { ...data.context!, historical_patterns: { bad: [{}] } },
        data.fixtures,
        matchId,
        139,
      ),
    ).toEqual([]);
  });
  it("uses opposite arcs for reciprocal edges and mirrors away coordinates on both axes", () => {
    expect(edgePath({ x: 0, y: 0 }, { x: 100, y: 0 })).toContain("Q50,28");
    expect(edgePath({ x: 100, y: 0 }, { x: 0, y: 0 })).toContain("Q50,-28");
    expect(edgePath({ x: 0, y: 0 }, { x: 0, y: 0 })).toBe("");
    expect(displayPoint({ x: 82, y: 25 }, teams[1].id, teams[0].id)).toEqual({
      x: 18,
      y: 75,
    });
  });
});
