import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AnalystPanel } from "./AnalystPanel";
import {
  analysis,
  artifact,
  events,
  receiver,
  sender,
  teams,
} from "./test-data";
import type { HistoricalMatch } from "./contracts";
import i18n from "../../i18n";

beforeEach(async () => {
  await i18n.changeLanguage("en");
});
it("opens a directed connection with keyboard, resolves source actions and fixes its cut", () => {
  const data = analysis(),
    select = vi.fn();
  const { rerender } = render(
    <AnalystPanel
      data={data}
      events={events}
      teams={teams}
      second={300}
      onSelect={select}
    />,
  );
  const link = screen.getByRole("button", {
    name: `${sender.name} → ${receiver.name} · 2 passes`,
  });
  fireEvent.keyDown(link, { key: "Enter" });
  const inspector = screen.getByRole("complementary", {
    name: "Evidence trail",
  });
  expect(within(inspector).getByText("2 passes")).toBeInTheDocument();
  expect(within(inspector).getByRole("status")).toHaveTextContent(
    "2 source actions resolved",
  );
  fireEvent.click(
    within(inspector).getByRole("button", {
      name: new RegExp(`1:10 Pass ${sender.name}`),
    }),
  );
  expect(select).toHaveBeenCalledWith("p1");
  fireEvent.click(within(inspector).getByText("Source references"));
  expect(within(inspector).getByText("test-session")).toBeInTheDocument();
  expect(
    within(inspector).getByText("p1", { selector: "code" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Pinned cut 5:00")).toBeInTheDocument();
  const newer = { ...data, response: { ...data.response!, at_second: 301 } };
  rerender(
    <AnalystPanel
      data={newer}
      events={events}
      teams={teams}
      second={301}
      onSelect={select}
    />,
  );
  expect(screen.getByText("Pinned cut 5:00")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Return to latest cut" }));
  expect(screen.getByText("Latest cut 5:01")).toBeInTheDocument();
  expect(
    screen.getByText("Make the number explain itself."),
  ).toBeInTheDocument();
});
it("renders one shot instead of counting the GOAL marker as an extra shot", () => {
  const select = vi.fn();
  render(
    <AnalystPanel
      data={analysis()}
      events={events}
      teams={teams}
      second={300}
      onSelect={select}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Shot map" }));
  fireEvent.click(
    screen.getByRole("button", {
      name: `${receiver.name} · Goal · Synthetic xG 0.20`,
    }),
  );
  expect(select).toHaveBeenCalledWith("s1");
  const inspector = screen.getByRole("complementary", {
    name: "Evidence trail",
  });
  expect(within(inspector).getByRole("status")).toHaveTextContent(
    "1 source actions resolved",
  );
  expect(
    within(inspector).queryByRole("button", { name: /Goal/ }),
  ).not.toBeInTheDocument();
});
it("shows measured zero and missing PPDA distinctly and discloses incomplete sources", () => {
  const data = analysis();
  data.response!.snapshot.teams[0].values[1].evidence!.event_ids.push(
    "missing",
  );
  render(
    <AnalystPanel
      data={data}
      events={events}
      teams={teams}
      second={300}
      onSelect={vi.fn()}
    />,
  );
  expect(screen.getByRole("button", { name: /PPDA —/ })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: /High recoveries 0/ }));
  expect(
    screen.getByText("This value has no supporting events at this cut."),
  ).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: /Pass accuracy 100%/ }));
  expect(screen.getByText(/Source set incomplete/)).toBeInTheDocument();
  expect(
    screen.getByRole("complementary", { name: "Evidence trail" }),
  ).toHaveTextContent("100%");
});
it("opens historical event artifacts and never selects them on the live match clock", async () => {
  const data = analysis(),
    select = vi.fn();
  const loader = vi.fn(async () => artifact);
  data.history = loader;
  render(
    <AnalystPanel
      data={data}
      events={events}
      teams={teams}
      second={300}
      onSelect={select}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Pattern ledger" }));
  await act(async () => {
    fireEvent.click(screen.getByRole("button", { name: /Matchday 6/ }));
  });
  expect(loader).toHaveBeenCalledWith("fixture-past", expect.any(AbortSignal));
  const inspector = screen.getByRole("complementary", {
    name: "Evidence trail",
  });
  expect(within(inspector).getByText("Historical fixture")).toBeInTheDocument();
  fireEvent.click(within(inspector).getByRole("button", { name: /1:10 Pass/ }));
  expect(select).not.toHaveBeenCalled();
  fireEvent.click(within(inspector).getByText("Source references"));
  expect(
    within(inspector).getByText("historical-match", { selector: "code" }),
  ).toBeInTheDocument();
});
it("cancels a historical load when switching views and ignores its late response", async () => {
  const data = analysis();
  let release!: (artifact: HistoricalMatch) => void;
  let signal!: AbortSignal;
  data.history = async (_, s) => {
    signal = s;
    return new Promise((resolve) => {
      release = resolve;
    });
  };
  render(
    <AnalystPanel
      data={data}
      events={events}
      teams={teams}
      second={300}
      onSelect={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Pattern ledger" }));
  fireEvent.click(screen.getByRole("button", { name: /Matchday 6/ }));
  expect(screen.getByRole("status")).toHaveTextContent(
    "Loading the historical event artifact",
  );
  fireEvent.click(screen.getByRole("button", { name: "Pass network" }));
  await act(async () => release(artifact));
  expect(signal.aborted).toBe(true);
  expect(screen.queryByText("Historical fixture")).not.toBeInTheDocument();
  expect(
    screen.getByText("Make the number explain itself."),
  ).toBeInTheDocument();
});
it("drops a fixed analysis when a new revision is mounted and withholds future source geometry", () => {
  const data = analysis();
  const { rerender } = render(
    <AnalystPanel
      key="2"
      data={data}
      events={events}
      teams={teams}
      second={300}
      onSelect={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: /Pass accuracy 100%/ }));
  rerender(
    <AnalystPanel
      key="3"
      data={{ ...data, revision: 3, response: null, context: null }}
      events={[]}
      teams={teams}
      second={0}
      onSelect={vi.fn()}
    />,
  );
  expect(screen.queryByText(/Pinned cut/)).not.toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent(
    "Waiting for a complete metric cut",
  );
});
it("provides a translated offline state without fabricating analysis", async () => {
  await i18n.changeLanguage("es");
  render(
    <AnalystPanel
      events={events}
      teams={teams}
      second={300}
      onSelect={vi.fn()}
    />,
  );
  expect(
    screen.getByRole("heading", { name: "Laboratorio de evidencia" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/El ensayo local solo contiene un clip corto/),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /PPDA/ }),
  ).not.toBeInTheDocument();
});
it("does not plot future shot sources or expose a later context count at an earlier metric cut", () => {
  const data = analysis();
  data.response!.at_second = 100;
  render(
    <AnalystPanel
      data={data}
      events={events}
      teams={teams}
      second={300}
      onSelect={vi.fn()}
    />,
  );
  fireEvent.click(screen.getByRole("button", { name: "Shot map" }));
  expect(
    screen.getByText("No source shots are available at this cut."),
  ).toBeInTheDocument();
  expect(
    screen.queryByRole("button", { name: /Synthetic xG 0.20/ }),
  ).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Pattern ledger" }));
  expect(
    screen.queryByRole("button", { name: /This match/ }),
  ).not.toBeInTheDocument();
  expect(screen.getByText("— Verified appearances")).toBeInTheDocument();
});

it("separates graph topology from observed pitch locations", () => {
  render(<AnalystPanel data={analysis()} events={events} teams={teams} second={300} onSelect={vi.fn()} />);
  const node = screen.getByRole("button", { name: `${sender.name} · 3 pass observations` });
  expect(node.querySelector("circle")?.getAttribute("cx")).not.toBe("472.5");
  fireEvent.click(screen.getByRole("button", { name: "Observed positions" }));
  expect(node.querySelector("circle")?.getAttribute("cx")).toBe("472.5");
  fireEvent.keyDown(node, { key: " " });
  expect(screen.getByRole("complementary", { name: "Evidence trail" })).toHaveTextContent("3 source actions resolved");
});
