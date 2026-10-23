// Small contract fixtures for isolation tests; never imported by product code.
import { fixture, type MatchEvent } from "../match/model";
import type { AnalysisData } from "./AnalystPanel";
import type { HistoricalMatch, Pattern } from "./contracts";

export const teams = fixture.teams;
export const sender = teams[0].players[1],
  receiver = teams[0].players[2];
const base = fixture.events.find((event) => event.type === "pass")!;
export const matchId = fixture.match_id;
export const events: MatchEvent[] = [
  {
    ...base,
    id: "p1",
    match_id: matchId,
    minute: 1,
    second: 10,
    team_id: teams[0].id,
    player_id: sender.id,
    related_player_id: receiver.id,
    start: { x: 45, y: 50 },
    end: { x: 82, y: 25 },
    outcome: "success",
  },
  {
    ...base,
    id: "p2",
    match_id: matchId,
    minute: 1,
    second: 20,
    team_id: teams[0].id,
    player_id: sender.id,
    related_player_id: receiver.id,
    start: { x: 45, y: 50 },
    end: { x: 82, y: 25 },
    outcome: "success",
  },
  {
    ...base,
    id: "p3",
    match_id: matchId,
    minute: 1,
    second: 30,
    team_id: teams[0].id,
    player_id: receiver.id,
    related_player_id: sender.id,
    start: { x: 82, y: 25 },
    end: { x: 45, y: 50 },
    outcome: "success",
  },
  {
    ...base,
    id: "s1",
    match_id: matchId,
    minute: 2,
    second: 20,
    team_id: teams[0].id,
    player_id: receiver.id,
    type: "shot",
    start: { x: 82, y: 25 },
    end: null,
    outcome: "success",
  },
  {
    ...base,
    id: "g1",
    match_id: matchId,
    minute: 2,
    second: 20,
    team_id: teams[0].id,
    player_id: receiver.id,
    type: "goal",
    start: { x: 82, y: 25 },
    end: null,
    outcome: "success",
  },
];
export const past: Pattern = {
  match_id: "historical-match",
  event_ids: ["p1", "p2", "s1", "g1"],
  possession_ids: ["loss", "attack"],
  loss_second: 120,
  goal_second: 140,
  elapsed_seconds: 20,
  conceding_club_id: teams[1].id,
  scoring_club_id: teams[0].id,
  scorer_id: receiver.id,
  shot_channel: "left",
};
export const artifact: HistoricalMatch = {
  match_id: past.match_id,
  home_club_id: teams[0].id,
  away_club_id: teams[1].id,
  events: events.map((event) => ({ ...event, match_id: past.match_id })),
};
export function analysis(): AnalysisData {
  return {
    sessionId: "test-session",
    matchId,
    revision: 2,
    clubs: teams,
    fixtures: [
      {
        id: "fixture-past",
        matchday: 6,
        home_club_id: teams[0].id,
        away_club_id: teams[1].id,
        home_goals: 1,
        away_goals: 0,
      },
    ],
    response: {
      revision: 2,
      at_second: 300,
      snapshot: {
        match_id: matchId,
        teams: [
          {
            team_id: teams[0].id,
            values: [
              {
                key: "pass_network_passes",
                value: 3,
                unit: "count",
                evidence: {
                  event_ids: ["p1", "p2", "p3"],
                  description: "Completed PASS observations",
                },
              },
              {
                key: "pass_accuracy_pct",
                value: 100,
                unit: "%",
                evidence: {
                  event_ids: ["p1", "p2", "p3"],
                  description: "Completed passes / attempted passes",
                },
              },
              {
                key: "xg_like",
                value: 0.2,
                unit: "xG-like",
                evidence: { event_ids: ["s1"], description: "One SHOT source" },
              },
              {
                key: "high_recoveries",
                value: 0,
                unit: "count",
                evidence: { event_ids: [], description: "No recoveries" },
              },
            ],
            pass_network: {
              team_id: teams[0].id,
              nodes: [
                {
                  player_id: sender.id,
                  touches: 3,
                  degree_centrality: 1,
                  betweenness_centrality: 0,
                  avg_location: { x: 45, y: 50 },
                },
                {
                  player_id: receiver.id,
                  touches: 3,
                  degree_centrality: 1,
                  betweenness_centrality: 0,
                  avg_location: { x: 82, y: 25 },
                },
              ],
              edges: [
                {
                  from_player_id: sender.id,
                  to_player_id: receiver.id,
                  passes: 2,
                },
                {
                  from_player_id: receiver.id,
                  to_player_id: sender.id,
                  passes: 1,
                },
              ],
            },
            shot_map: [
              {
                event_id: "s1",
                player_id: receiver.id,
                location: { x: 82, y: 25 },
                xg: 0.2,
                outcome: "goal",
              },
            ],
          },
          {
            team_id: teams[1].id,
            values: [],
            pass_network: { team_id: teams[1].id, nodes: [], edges: [] },
            shot_map: [],
          },
        ],
      },
    },
    context: {
      revision: 2,
      at_second: 300,
      historical_patterns: { "fixture-past": [past] },
      climax: { ...past, match_id: matchId },
      verified_consecutive_matches: 4,
    },
    history: async () => artifact,
  };
}
