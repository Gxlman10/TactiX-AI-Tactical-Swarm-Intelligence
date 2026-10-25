import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { SessionPanel } from "./SessionPanel";
import { LiveSession } from "./session";
import i18n from "../../i18n";

afterEach(() => vi.useRealTimers());

it("announces retained data and countdown, supports manual recovery and cleans up timers", async () => {
  await i18n.changeLanguage("en");
  vi.useFakeTimers();
  const controller = new LiveSession();
  const retry = vi.spyOn(controller, "retryConnection");
  const data = {
    ...controller.getSnapshot(),
    connection: "reconnecting" as const,
    retryAt: Date.now() + 5000,
    retryAttempt: 2,
    teams: [{ id: "home" }],
    info: { session_id: "test" },
  } as ReturnType<LiveSession["getSnapshot"]>;
  const { unmount } = render(
    <SessionPanel data={data} controller={controller} />,
  );
  expect(screen.getByText(/Keeping the last confirmed view/)).toHaveTextContent(
    "Retry 2 in 5s",
  );
  act(() => vi.advanceTimersByTime(2000));
  expect(screen.getByText(/Keeping the last confirmed view/)).toHaveTextContent(
    "in 3s",
  );
  fireEvent.click(screen.getByRole("button", { name: "Reconnect" }));
  expect(retry).toHaveBeenCalledOnce();
  unmount();
  expect(vi.getTimerCount()).toBe(0);
});

it("explains closed sessions in Spanish and offers a new demo instead of retrying it", async () => {
  await i18n.changeLanguage("es");
  const controller = new LiveSession();
  const data = { ...controller.getSnapshot(), connection: "closed" as const };
  render(<SessionPanel data={data} controller={controller} />);
  expect(
    screen.getByText(/Esta sesión temporal ya no está disponible/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Crear sesión demo" }),
  ).toBeEnabled();
  expect(
    screen.queryByRole("button", { name: "Reconectar" }),
  ).not.toBeInTheDocument();
});
