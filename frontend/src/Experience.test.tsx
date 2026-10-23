import { render, screen, fireEvent } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import Experience from "./Experience";
import Studio, { type StudioView } from "./App";
import { fixture } from "./features/match/model";
import { useStudio } from "./features/preferences/store";
beforeEach(() => {
  useStudio.setState({ language: "en", mode: "analyst", playing: false });
  window.history.replaceState({}, "", "/");
});
it("starts with a real connection choice and never silently falls back to exported metrics", () => {
  render(<Experience />);
  expect(
    screen.getByRole("button", { name: "Create demo session" }),
  ).toBeInTheDocument();
  expect(screen.queryByText("63.7%")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Open local rehearsal" }));
  expect(
    screen.getByText("Local rehearsal", { selector: "strong" }),
  ).toBeInTheDocument();
});
it("renders a server view using server score and missing values without fixture fallback", () => {
  const noop = vi.fn();
  const view: StudioView = {
    teams: fixture.teams,
    season: fixture.season,
    events: [],
    metrics: [{}, {}],
    context: null,
    second: 3600,
    start: 0,
    end: 5400,
    score: [3, 2],
    playing: false,
    speed: 4,
    selectedId: null,
    busy: true,
    seek: noop,
    select: noop,
    togglePlay: noop,
    setSpeed: noop,
  };
  render(<Studio view={view} />);
  expect(screen.getByText("Server replay")).toBeInTheDocument();
  expect(screen.queryByText("63.7%")).not.toBeInTheDocument();
  expect(
    screen.queryByText("A familiar weakness, exposed again."),
  ).not.toBeInTheDocument();
  expect(screen.getByRole("slider", { name: "Match clock" })).toBeDisabled();
  expect(screen.getByRole("button", { name: "Play clip" })).toBeDisabled();
});
it("makes retained earlier events available without rendering the entire match on every tick", () => {
  const noop = vi.fn();
  const events = Array.from({ length: 120 }, (_, index) => ({
    ...fixture.events[0],
    id: `event-${index}`,
  }));
  const view: StudioView = {
    teams: fixture.teams,
    season: fixture.season,
    events,
    metrics: [{}, {}],
    context: null,
    second: 3720,
    start: 0,
    end: 5400,
    score: [1, 1],
    playing: false,
    speed: 60,
    selectedId: null,
    busy: false,
    seek: noop,
    select: noop,
    togglePlay: noop,
    setSpeed: noop,
  };
  const { container } = render(<Studio view={view} />);
  expect(container.querySelectorAll(".event-row")).toHaveLength(50);
  fireEvent.click(
    screen.getByRole("button", { name: "Show earlier actions (70)" }),
  );
  expect(container.querySelectorAll(".event-row")).toHaveLength(100);
  fireEvent.click(
    screen.getByRole("button", { name: "Show earlier actions (20)" }),
  );
  expect(container.querySelectorAll(".event-row")).toHaveLength(120);
  expect(
    screen.queryByRole("button", { name: /Show earlier actions/ }),
  ).not.toBeInTheDocument();
});
