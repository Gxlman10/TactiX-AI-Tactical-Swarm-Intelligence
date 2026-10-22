import raw from "./fixture.json";
export type Point = { x: number; y: number };
export type MatchEvent = (typeof raw.events)[number];
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
export const displayPoint = (point: Point, teamId: string): Point =>
  teamId === fixture.teams[0].id
    ? point
    : { x: 100 - point.x, y: 100 - point.y };
export const metricsAt = (second: number) =>
  fixture.snapshots[String(second) as keyof typeof fixture.snapshots];
