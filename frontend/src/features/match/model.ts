import raw from "./fixture.json";
export type Point = { x: number; y: number };
export interface MatchEvent {
  id: string;
  match_id: string;
  minute: number;
  second: number;
  team_id: string;
  player_id: string;
  type: string;
  start: Point;
  end: Point | null;
  outcome: string;
  possession_id: string | null;
}
export type Team = (typeof raw.teams)[number];
export interface Context {
  climax: { goal_second: number; elapsed_seconds: number } | null;
  verified_consecutive_matches: number;
  historical_patterns: Record<string, unknown>;
}
export const fixture = raw;
export const timeOf = (event: MatchEvent) => event.minute * 60 + event.second;
export const clock = (second: number) =>
  `${Math.floor(second / 60)}:${String(second % 60).padStart(2, "0")}`;
export const visibleEvents = (second: number) =>
  fixture.events.filter((event) => timeOf(event) <= second);
export const player = (id: string | null) =>
  fixture.teams
    .flatMap((team) => team.players)
    .find((person) => person.id === id);
export const teamOf = (id: string) =>
  fixture.teams.find((team) => team.id === id);
export const displayPoint = (
  point: Point,
  teamId: string,
  homeId = fixture.teams[0].id,
): Point =>
  teamId === homeId ? point : { x: 100 - point.x, y: 100 - point.y };
export const metricsAt = (second: number) =>
  fixture.snapshots[String(second) as keyof typeof fixture.snapshots];
