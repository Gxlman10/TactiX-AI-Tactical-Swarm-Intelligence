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
