import type { MatchEvent, Point } from "../match/model";

export interface Evidence {
  event_ids: string[];
  description: string;
}
export interface Metric {
  key: string;
  value: number;
  label?: string;
  unit?: string | null;
  evidence?: Evidence;
}
export interface NetworkNode {
  player_id: string;
  touches: number;
  degree_centrality: number;
  betweenness_centrality: number;
  avg_location: Point | null;
}
export interface NetworkEdge {
  from_player_id: string;
  to_player_id: string;
  passes: number;
}
export interface PassNetwork {
  team_id: string;
  nodes: NetworkNode[];
  edges: NetworkEdge[];
}
export interface Shot {
  event_id: string;
  player_id: string;
  location: Point;
  xg: number;
  outcome: string;
}
export interface TeamAnalysis {
  team_id: string;
  values: Metric[];
  pass_network?: PassNetwork | null;
  shot_map?: Shot[];
}
export interface Pattern {
  match_id: string;
  event_ids: string[];
  possession_ids: string[];
  loss_second: number;
  goal_second: number;
  elapsed_seconds: number;
  conceding_club_id: string;
  scoring_club_id: string;
  scorer_id: string;
  shot_channel: string;
}
export interface HistoricalMatch {
  match_id: string;
  home_club_id: string;
  away_club_id: string;
  events: MatchEvent[];
}
export interface HistoricalArtifact {
  match_id: string;
  home_club_id: string;
  away_club_id: string;
  frames: { events: MatchEvent[] }[];
}
export interface FixtureSummary {
  id: string;
  matchday: number;
  home_club_id: string;
  away_club_id: string;
  home_goals: number;
  away_goals: number;
}
