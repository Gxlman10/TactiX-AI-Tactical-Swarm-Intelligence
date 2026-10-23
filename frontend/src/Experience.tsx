import { useEffect, useState, useSyncExternalStore } from "react";
import Studio from "./App";
import {
  LiveSession,
  metricRows,
  visibleLiveEvents,
} from "./features/live/session";
import { SessionPanel } from "./features/live/SessionPanel";
import { useStudio } from "./features/preferences/store";
import i18n from "./i18n";

export default function Experience() {
  const [local, setLocal] = useState(
    new URLSearchParams(window.location.search).get("source") === "local",
  );
  const language = useStudio((state) => state.language);
  useEffect(() => {
    void i18n.changeLanguage(language);
    document.documentElement.lang = language;
  }, [language]);
  if (window.location.pathname !== "/") return <Studio />;
  return local ? (
    <Studio
      sessionPanel={<SessionPanel local onConnect={() => setLocal(false)} />}
    />
  ) : (
    <LiveStudio onLocal={() => setLocal(true)} />
  );
}
function LiveStudio({ onLocal }: { onLocal: () => void }) {
  const [controller] = useState(() => new LiveSession());
  const data = useSyncExternalStore(
    controller.subscribe,
    controller.getSnapshot,
  );
  useEffect(() => {
    window.addEventListener("pagehide", controller.leave);
    return () => {
      window.removeEventListener("pagehide", controller.leave);
      controller.dispose();
    };
  }, [controller]);
  const panel = (
    <SessionPanel data={data} controller={controller} onLocal={onLocal} />
  );
  if (!data.info || data.teams.length !== 2)
    return (
      <main className="session-launcher">
        <a className="brand" href="/">
          TactiX<span>✳</span>
        </a>
        {panel}
      </main>
    );
  const state = data.info.state;
  return (
    <Studio
      sessionPanel={panel}
      view={{
        teams: data.teams,
        season: data.season,
        events: visibleLiveEvents(data),
        metrics: metricRows(data.metrics, data.teams),
        context: data.context,
        second: Math.floor(state.position_seconds),
        start: 0,
        end: state.duration_seconds,
        score: state.score,
        playing: state.status === "playing",
        speed: state.speed,
        selectedId: data.selectedId,
        busy: data.busy || data.rebuilding || data.connection !== "connected",
        select: controller.select,
        seek: (second) => {
          void controller.control({ action: "seek", second });
        },
        setSpeed: (speed) => {
          void controller.control({ action: "speed", speed });
        },
        togglePlay: () => {
          void (async () => {
            if (state.status === "finished")
              await controller.control({ action: "seek", second: 0 });
            await controller.control({
              action: state.status === "playing" ? "pause" : "play",
            });
          })();
        },
      }}
    />
  );
}
