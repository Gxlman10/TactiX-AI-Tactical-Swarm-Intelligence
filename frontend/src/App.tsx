import {
  AnalystPanel,
  type AnalysisData,
} from "./features/analyst/AnalystPanel";
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  ArrowUpRight,
  ChartLineUp,
  Crosshair,
  Globe,
  Pause,
  Play,
  SoccerBall,
  SquaresFour,
  Stack,
  Target,
} from "@phosphor-icons/react";
import { Pitch } from "./features/match/Pitch";
import {
  clock,
  fixture,
  metricsAt,
  timeOf,
  visibleEvents,
  type MatchEvent,
  type Team,
  type Context,
} from "./features/match/model";
import { useStudio, type Language } from "./features/preferences/store";
import { FocusPlayerPanel } from "./features/preferences/FocusPlayerPanel";
import { ProvenanceParagraph } from "./features/analyst/ProvenanceParagraph";
import type { MatchReportRun } from "./features/live/api";
import i18n from "./i18n";

export interface StudioView {
  analysis?: AnalysisData;
  report?: MatchReportRun | null;
  teams: Team[];
  season: string;
  events: MatchEvent[];
  metrics: Record<string, number>[];
  context: Context | null;
  second: number;
  start: number;
  end: number;
  score: number[];
  playing: boolean;
  speed: number;
  selectedId: string | null;
  busy: boolean;
  seek: (second: number) => void;
  select: (id: string) => void;
  togglePlay: () => void;
  setSpeed: (speed: number) => void;
}
export default function App({
  view,
  sessionPanel,
}: {
  view?: StudioView;
  sessionPanel?: React.ReactNode;
}) {
  const { t } = useTranslation();
  const [timelineLimit, setTimelineLimit] = useState(50);
  const local = useStudio();
  const state = { ...local, ...view };
  const teams = view?.teams ?? fixture.teams;
  const context = view ? view.context : fixture.context;
  const score = view?.score ?? metricsAt(local.second).map((row) => row.goals);
  const start = view?.start ?? fixture.start;
  const end = view?.end ?? fixture.end;
  const player = (id: string | null) =>
    teams.flatMap((team) => team.players).find((player) => player.id === id);
  const teamOf = (id: string) => teams.find((team) => team.id === id);
  const visible = view?.events ?? visibleEvents(state.second);
  const selected = visible.find((e) => e.id === state.selectedId);
  const metrics = view?.metrics ?? metricsAt(state.second);
  const hasContext = Boolean(
    context?.climax && state.second >= context.climax.goal_second,
  );
  useEffect(() => {
    void i18n.changeLanguage(state.language);
    document.documentElement.lang = state.language;
  }, [state.language]);
  useEffect(() => {
    if (view || !local.playing) return;
    const timer = window.setInterval(local.advance, 1000 / local.speed);
    return () => window.clearInterval(timer);
  }, [view, local.playing, local.speed, local.advance]);
  if (window.location.pathname !== "/")
    return (
      <main className="not-found">
        <span className="brand">
          TactiX<span>✳</span>
        </span>
        <h1>{t("notFound")}</h1>
        <a href="/">
          {t("return")} <ArrowRight />
        </a>
      </main>
    );
  return (
    <>
      <a className="skip" href="#main">
        {t("skip")}
      </a>
      <div className="app-layout">
        <aside className="sidebar">
          <a href="/" className="brand" aria-label="TactiX home">
            TactiX<span>✳</span>
          </a>
          <p className="workspace">{t("workspace")}</p>
          <span className="nav-label">{t("navigation")}</span>
          <nav aria-label={t("studio")}>
            <a href="#main" className="active" aria-current="page">
              <SquaresFour size={20} />
              {t("studio")}
              <span className="tiny-dot" />
            </a>
            <a href="#analysis">
              <ChartLineUp size={20} />
              {t("lab.title")}
            </a>
            <a href="#evidence">
              <Crosshair size={20} />
              {t("evidence")}
            </a>
            <a href="#session">
              <Stack size={20} />
              {t("session")}
            </a>
          </nav>
          <div className="sidebar-bottom">
            <div className="scenario-glyph">
              <SoccerBall size={24} />
            </div>
            <strong>{t("demo")}</strong>
            <p>{t("synthetic")}</p>
            <span className="version">
              ashford-demo-v1 <ArrowUpRight size={14} />
            </span>
          </div>
        </aside>
        <div className="main-shell">
          <header className="topbar">
            <div className="breadcrumb">
              {t("match")}
              <span>/</span>
              <strong>{t("studio")}</strong>
            </div>
            <div className="top-actions">
              <span className="rehearsal">
                <span className="tiny-dot" />
                {t(view ? "serverReplay" : "rehearsal")}
              </span>
              <label className="language">
                <Globe size={18} />
                <span className="sr-only">{t("language")}</span>
                <select
                  aria-label={t("language")}
                  value={state.language}
                  onChange={(e) =>
                    state.setLanguage(e.target.value as Language)
                  }
                >
                  <option value="en">EN</option>
                  <option value="es">ES</option>
                </select>
              </label>
              <label className="preference-select">
                <span>{t("favoriteClub")}</span>
                <select
                  aria-label={t("favoriteClub")}
                  value={state.favoriteTeamId ?? ""}
                  onChange={(event) =>
                    state.setFavoriteTeam(event.target.value || null)
                  }
                >
                  <option value="">{t("noFavoriteClub")}</option>
                  {teams.map((team) => (
                    <option key={team.id} value={team.id}>
                      {team.name}
                    </option>
                  ))}
                </select>
              </label>
              <label className="preference-select">
                <span>{t("focusPlayer")}</span>
                <select
                  aria-label={t("focusPlayer")}
                  value={state.focusPlayerId ?? ""}
                  onChange={(event) =>
                    state.setFocusPlayer(event.target.value || null)
                  }
                >
                  <option value="">{t("noFocusPlayer")}</option>
                  {teams.flatMap((team) =>
                    team.players.map((player) => (
                      <option key={player.id} value={player.id}>
                        {player.name} · {team.name}
                      </option>
                    )),
                  )}
                </select>
              </label>
            </div>
          </header>
          <main id="main">
            {sessionPanel}
            <section className="intro">
              <div>
                <p className="eyebrow">TACTICAL SWARM INTELLIGENCE</p>
                <h1>{t("heading")}</h1>
                <p className="intro-copy">{t("subtitle")}</p>
              </div>
              <div className="mode-switch" aria-label={t("viewMode")}>
                {(["analyst", "fan"] as const).map((mode) => (
                  <button
                    key={mode}
                    aria-pressed={state.mode === mode}
                    className={state.mode === mode ? "selected" : ""}
                    onClick={() => state.setMode(mode)}
                  >
                    {mode === "analyst" ? (
                      <ChartLineUp size={18} />
                    ) : (
                      <SoccerBall size={18} />
                    )}{" "}
                    {t(mode)}
                  </button>
                ))}
              </div>
            </section>
            <FocusPlayerPanel
              playerId={state.focusPlayerId}
              teams={teams}
              events={visible}
              second={state.second}
            />
            {state.report?.report.narration && (
              <ProvenanceParagraph
                moments={[
                  ...state.report.report.narration.play_by_play,
                  ...state.report.report.narration.key_moments,
                ]}
                findings={[
                  ...state.report.context.analyst_findings,
                  ...state.report.context.historian_findings,
                ]}
              />
            )}
            <section className="scoreboard" aria-label={t("match")}>
              <div className="competition">
                <span className="competition-mark">
                  <SoccerBall size={22} />
                </span>
                <div>
                  <strong>TactiX League</strong>
                  <small>
                    {t("season")} {view?.season ?? fixture.season} ·{" "}
                    {t("matchday")}
                  </small>
                </div>
              </div>
              <div className="score-match">
                <div className="club home">
                  <span className="club-monogram">
                    {teams[0].name[0]}
                    <span>FC</span>
                  </span>
                  <div>
                    <strong>{teams[0].name}</strong>
                    <small>
                      {teams[0].formation} · {t("home")}
                    </small>
                  </div>
                </div>
                <div className="score">
                  <strong>
                    {score[0]} <span>:</span> {score[1]}
                  </strong>
                  <span className="match-clock">{clock(state.second)}</span>
                </div>
                <div className="club away">
                  <div>
                    <strong>{teams[1].name}</strong>
                    <small>
                      {teams[1].formation} · {t("away")}
                    </small>
                  </div>
                  <span className="club-monogram">
                    {teams[1].name[0]}
                    <span>FC</span>
                  </span>
                </div>
              </div>
              <span className="play-status">
                <span
                  className={`tiny-dot ${state.playing ? "glowing" : ""}`}
                />
                {t(state.playing ? "live" : "paused")}
              </span>
            </section>
            {state.mode === "analyst" && (
              <section className="metrics-strip" aria-label={t("matchMetrics")}>
                {(["possession", "passing", "shots", "xg"] as const).map(
                  (label, index) => {
                    const key = (
                      [
                        "possession_pct",
                        "pass_accuracy_pct",
                        "shots",
                        "xg_like",
                      ] as const
                    )[index];
                    const format = (n: number | undefined) =>
                      !Number.isFinite(n)
                        ? "—"
                        : index < 2
                          ? `${n!.toFixed(1)}%`
                          : index === 3
                            ? n!.toFixed(2)
                            : n;
                    return (
                      <div className="metric" key={label}>
                        <span>
                          {t(label)} {label === "xg" && <small>ⓘ</small>}
                        </span>
                        <div>
                          <strong className="home-text">
                            {format(metrics[0][key])}
                          </strong>
                          <span className="metric-divider" />
                          <strong className="away-text">
                            {format(metrics[1][key])}
                          </strong>
                        </div>
                        {label === "xg" && (
                          <small>{t("syntheticMetric")}</small>
                        )}
                      </div>
                    );
                  },
                )}
              </section>
            )}
            <div className="studio-grid">
              <section className="pitch-panel panel">
                <div className="panel-heading">
                  <div>
                    <h2>
                      <Crosshair size={18} />
                      {t("pitch")}
                    </h2>
                    <p>{t("pitchSub")}</p>
                  </div>
                  <span className="subtle-tag">
                    {selected ? clock(timeOf(selected)) : "—"}
                  </span>
                </div>
                <Pitch selected={selected} visible={visible} teams={teams} />
                <div className="pitch-footer">
                  <span>
                    <i className="legend home-legend" />
                    {teams[0].name}
                  </span>
                  <span>
                    <i className="legend away-legend" />
                    {teams[1].name}
                  </span>
                  <small>{t("chain")}</small>
                </div>
                <div className="playback" aria-label={t("controls")}>
                  <div className="playback-top">
                    <button
                      className="play-button"
                      aria-label={t(state.playing ? "pause" : "play")}
                      disabled={view?.busy}
                      onClick={state.togglePlay}
                    >
                      {state.playing ? (
                        <Pause weight="fill" size={18} />
                      ) : (
                        <Play weight="fill" size={18} />
                      )}
                    </button>
                    <strong>{clock(state.second)}</strong>
                    <span className="duration">/ {clock(end)}</span>
                    <label className="speed">
                      <span className="sr-only">{t("speed")}</span>
                      <select
                        aria-label={t("speed")}
                        disabled={view?.busy}
                        value={state.speed}
                        onChange={(e) => state.setSpeed(Number(e.target.value))}
                      >
                        {(view ? [1, 4, 12, 60] : [1, 4, 12]).map((speed) => (
                          <option key={speed} value={speed}>
                            {speed}×
                          </option>
                        ))}
                      </select>
                    </label>
                    <button
                      disabled={view?.busy}
                      className="key-moment"
                      onClick={() => state.seek(3720)}
                    >
                      <Target size={16} />
                      {t("goal")}
                    </button>
                  </div>
                  <input
                    disabled={view?.busy}
                    className="scrubber"
                    type="range"
                    min={start}
                    max={end}
                    value={state.second}
                    aria-label={t("scrub")}
                    onChange={(e) => state.seek(Number(e.target.value))}
                  />
                  <div className="range-labels">
                    <span>{clock(start)}</span>
                    <span>{clock(end)}</span>
                  </div>
                </div>
              </section>
              <aside className="context-panel panel">
                <div className="panel-heading">
                  <h2>
                    <Stack size={18} />
                    {t("context")}
                  </h2>
                  <ArrowUpRight className="muted" size={18} />
                </div>
                <div className="context-content">
                  <span className="section-tag">{t("contextTag")}</span>
                  <div className="context-symbol">
                    <Target size={32} />
                  </div>
                  <h3>{t(hasContext ? "contextHeading" : "pending")}</h3>
                  <p>{t(hasContext ? "contextBody" : "pendingBody")}</p>
                  {hasContext && (
                    <>
                      <div className="context-numbers">
                        <div>
                          <strong>
                            {context!.verified_consecutive_matches}
                            <span>↗</span>
                          </strong>
                          <small>{t("pattern")}</small>
                        </div>
                        <div>
                          <strong>
                            {context!.climax!.elapsed_seconds}
                            <span>s</span>
                          </strong>
                          <small>{t("elapsed")}</small>
                        </div>
                      </div>
                      <p className="historical-note">{t("historical")}</p>
                      <details>
                        <summary>
                          {t("sources")} <ArrowRight size={14} />
                        </summary>
                        {Object.keys(context!.historical_patterns).map((id) => (
                          <code key={id}>{id}</code>
                        ))}
                      </details>
                    </>
                  )}
                  <span className="authored-note">
                    <span className="tiny-dot" />
                    {t("authored")}
                  </span>
                </div>
              </aside>
            </div>
            {state.mode === "analyst" && (
              <AnalystPanel
                key={
                  view?.analysis
                    ? `${view.analysis.sessionId}:${view.analysis.revision}`
                    : "offline"
                }
                data={view?.analysis}
                events={visible}
                teams={teams}
                second={state.second}
                onSelect={state.select}
              />
            )}
            <div className="evidence-grid">
              <section className="panel timeline">
                <div className="panel-heading">
                  <div>
                    <h2>
                      <ChartLineUp size={18} />
                      {t("eventFeed")}
                    </h2>
                    <p>{t(view ? "liveFeedSub" : "feedSub")}</p>
                  </div>
                  <span className="subtle-tag">
                    {visible.length} {t("total")}
                  </span>
                </div>
                <div className="event-list">
                  {visible.length ? (
                    [...visible]
                      .reverse()
                      .slice(0, timelineLimit)
                      .map((event) => (
                        <button
                          key={event.id}
                          className={`event-row ${event.id === state.selectedId ? "chosen" : ""}`}
                          onClick={() => state.select(event.id)}
                          aria-pressed={event.id === state.selectedId}
                        >
                          <span className="event-time">
                            {clock(timeOf(event))}
                          </span>
                          <span
                            className={`event-icon ${event.team_id === teams[0].id ? "home-text" : "away-text"}`}
                          >
                            {["shot", "goal"].includes(event.type) ? (
                              <Target size={18} />
                            ) : (
                              <ArrowUpRight size={18} />
                            )}
                          </span>
                          <span className="event-copy">
                            <strong>
                              {t(
                                event.type === "goal"
                                  ? "goalEvent"
                                  : event.type,
                              )}{" "}
                              <span>· {player(event.player_id)?.name}</span>
                            </strong>
                            <small>{teamOf(event.team_id)?.name}</small>
                          </span>
                          <ArrowRight className="event-arrow" size={16} />
                        </button>
                      ))
                  ) : (
                    <p className="empty">{t("noEvents")}</p>
                  )}
                </div>
                {visible.length > timelineLimit && (
                  <button
                    className="history-more"
                    onClick={() => setTimelineLimit((limit) => limit + 50)}
                  >
                    {t("olderEvents")} ({visible.length - timelineLimit})
                  </button>
                )}
                <p className="timeline-note">{t("future")}</p>
              </section>
              <section className="panel event-detail" id="evidence">
                <div className="panel-heading">
                  <h2>
                    <Crosshair size={18} />
                    {t("evidenceTitle")}
                  </h2>
                  <span className="section-tag">{t("selected")}</span>
                </div>
                {selected ? (
                  <div className="detail-content">
                    <div className="detail-title">
                      <span className="detail-type">
                        {t(
                          selected.type === "goal"
                            ? "goalEvent"
                            : selected.type,
                        )}
                      </span>
                      <strong>{player(selected.player_id)?.name}</strong>
                    </div>
                    <dl>
                      <div>
                        <dt>{t("outcome")}</dt>
                        <dd>
                          {t(
                            selected.outcome === "success" ? "success" : "fail",
                          )}
                        </dd>
                      </div>
                      <div>
                        <dt>{t("start")}</dt>
                        <dd>
                          {selected.start.x.toFixed(1)},{" "}
                          {selected.start.y.toFixed(1)}
                        </dd>
                      </div>
                      <div>
                        <dt>{t("end")}</dt>
                        <dd>
                          {selected.end
                            ? `${selected.end.x.toFixed(1)}, ${selected.end.y.toFixed(1)}`
                            : "—"}
                        </dd>
                      </div>
                    </dl>
                    <label>
                      {t("eventId")}
                      <code>{selected.id}</code>
                    </label>
                    <label>
                      {t("possessionId")}
                      <code>{selected.possession_id}</code>
                    </label>
                  </div>
                ) : (
                  <p className="empty">{t("evidenceHint")}</p>
                )}
              </section>
            </div>
            <footer id="session">
              <span className="footer-mark">
                T<span>✳</span>
              </span>
              <div>
                <strong>{t("notes")}</strong>
                <p>{t(view ? "serverNotes" : "notesBody")}</p>
              </div>
              <span className="footer-version">
                {view ? "replay-v1" : "rehearsal-v1"}
              </span>
            </footer>
          </main>
        </div>
      </div>
    </>
  );
}
