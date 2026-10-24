import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import App from "./App";
import { useStudio } from "./features/preferences/store";
import { fixture, visibleEvents } from "./features/match/model";
import "./i18n";
beforeEach(() =>
  useStudio.setState({
    second: 3720,
    selectedId: visibleEvents(3720).at(-1)!.id,
    playing: false,
    language: "en",
    mode: "analyst",
  }),
);
it("renders the authored evidence without pretending to run agents", () => {
  render(<App />);
  expect(screen.getByText("Local rehearsal")).toBeInTheDocument();
  expect(
    screen.getByRole("img", { name: /The match, in space/ }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "This is a scripted preview, not generated agent commentary.",
    ),
  ).toBeInTheDocument();
});
it("translates navigation and preserves the current event", async () => {
  render(<App />);
  const before = useStudio.getState().selectedId;
  fireEvent.change(screen.getByRole("combobox", { name: "Language" }), {
    target: { value: "es" },
  });
  await waitFor(() =>
    expect(
      screen.getByRole("heading", { name: "Cada acción tiene una historia." }),
    ).toBeInTheDocument(),
  );
  expect(useStudio.getState().selectedId).toBe(before);
  expect(document.documentElement.lang).toBe("es");
});
it("updates the favourite club and focus player preferences", () => {
  render(<App />);
  const club = fixture.teams[0];
  const focus = club.players[0];
  fireEvent.change(screen.getByRole("combobox", { name: "Favourite club" }), {
    target: { value: club.id },
  });
  fireEvent.change(screen.getByRole("combobox", { name: "Focus player" }), {
    target: { value: focus.id },
  });
  expect(useStudio.getState().favoriteTeamId).toBe(club.id);
  expect(useStudio.getState().focusPlayerId).toBe(focus.id);
  expect(
    JSON.parse(localStorage.getItem("tactix-preferences-v1")!).state,
  ).toMatchObject({ favoriteTeamId: club.id, focusPlayerId: focus.id });
  expect(screen.getByRole("heading", { name: focus.name })).toBeInTheDocument();
  expect(screen.getByText("The rating is a transparent event-based proxy until live Personalizer output is connected.")).toBeInTheDocument();
});
it("switches Analyst and Fan on the same live moment", () => {
  render(<App />);
  const before = useStudio.getState();
  fireEvent.click(screen.getByRole("button", { name: "Fan" }));
  expect(useStudio.getState().second).toBe(before.second);
  expect(useStudio.getState().selectedId).toBe(before.selectedId);
  expect(screen.queryByRole("region", { name: "Match metrics" })).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Analyst" }));
  expect(useStudio.getState().second).toBe(before.second);
  expect(useStudio.getState().selectedId).toBe(before.selectedId);
  expect(screen.getByRole("region", { name: "Match metrics" })).toBeInTheDocument();
});
it("removes future climax context when scrubbing backwards", () => {
  render(<App />);
  fireEvent.change(screen.getByRole("slider", { name: "Match clock" }), {
    target: { value: "3719" },
  });
  expect(
    screen.queryByText("A familiar weakness, exposed again."),
  ).not.toBeInTheDocument();
  expect(
    screen.getByText("The next moment is still to come."),
  ).toBeInTheDocument();
  expect(
    screen.queryByText(fixture.context.climax!.event_ids.at(-1)!),
  ).not.toBeInTheDocument();
});
