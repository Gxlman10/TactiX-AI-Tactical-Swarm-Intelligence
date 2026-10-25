import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, expect, it } from "vitest";
import { Home } from "./Home";
import { useStudio } from "./features/preferences/store";

beforeEach(() => useStudio.setState({ language: "en" }));

it("connects the editorial introduction to real session controls without claiming live inference", () => {
  render(<Home sessionPanel={<button>Create demo session</button>} />);
  expect(
    screen.getByRole("link", { name: "Enter the studio" }),
  ).toHaveAttribute("href", "#demo");
  expect(
    screen.getByRole("button", { name: "Create demo session" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Live agent narration requires a configured model/),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("img", { name: "Premier League" })).toHaveLength(
    2,
  );
  fireEvent.click(screen.getByRole("button", { name: "02 Historian" }));
  expect(
    screen.getByText("Connects the moment to season history."),
  ).toBeInTheDocument();
});

it("translates essential copy and keeps the selected specialist", () => {
  render(<Home sessionPanel={<div>Session controls</div>} />);
  fireEvent.click(screen.getByRole("button", { name: "03 Narrator" }));
  fireEvent.click(screen.getByRole("button", { name: "Cambiar a español" }));
  expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
    "Más allá del marcador.",
  );
  expect(screen.getByRole("button", { name: "03 Narrador" })).toHaveAttribute(
    "aria-pressed",
    "true",
  );
  expect(
    screen.getByRole("link", { name: "Entrar al estudio" }),
  ).toHaveAttribute("href", "#demo");
});

it("opens and closes mobile navigation on section selection", () => {
  render(<Home sessionPanel={<div>Session controls</div>} />);
  const menu = screen.getByRole("button", { name: "Open navigation" });
  fireEvent.click(menu);
  expect(
    screen.getByRole("button", { name: "Close navigation" }),
  ).toHaveAttribute("aria-expanded", "true");
  fireEvent.click(screen.getByRole("link", { name: "Explore" }));
  expect(
    screen.getByRole("button", { name: "Open navigation" }),
  ).toHaveAttribute("aria-expanded", "false");
});
