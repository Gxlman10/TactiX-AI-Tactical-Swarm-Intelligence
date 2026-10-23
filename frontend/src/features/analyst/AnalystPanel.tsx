import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ArrowRight,
  Crosshair,
  PushPin,
  ShareNetwork,
} from "@phosphor-icons/react";
import { clock, type MatchEvent, type Team } from "../match/model";
import type { ApiContext, MetricsResponse } from "../live/api";
import type {
  FixtureSummary,
  HistoricalMatch,
  Metric,
  NetworkEdge,
  NetworkNode,
  Shot,
} from "./contracts";
import { NetworkChart, ShotChart } from "./Charts";
import { Inspector, type Selection } from "./Inspector";
import {
  edgeIds,
  metricKeys,
  metricText,
  nodeIds,
  occurrences,
  resolveEvidence,
  validCut,
} from "./evidence";

export interface AnalysisData {
  sessionId: string;
  matchId: string;
  revision: number;
  response: MetricsResponse | null;
  clubs: Team[];
  fixtures: FixtureSummary[];
  context: ApiContext | null;
  history: (fixtureId: string, signal: AbortSignal) => Promise<HistoricalMatch>;
}
type Tab = "network" | "shots" | "patterns" | "metrics";
type Pin = { response: MetricsResponse; context: ApiContext | null };
export function AnalystPanel({
  data,
  events,
  teams,
  second,
  onSelect,
}: {
  data?: AnalysisData;
  events: MatchEvent[];
  teams: Team[];
  second: number;
  onSelect: (id: string) => void;
}) {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>("network");
  const [teamId, setTeamId] = useState(teams[0].id);
  const [pin, setPin] = useState<Pin | null>(null);
  const [selection, setSelection] = useState<Selection | null>(null);
  const [historical, setHistorical] = useState<HistoricalMatch | null>(null);
  const [edge, setEdge] = useState<NetworkEdge | undefined>();
  const [node, setNode] = useState<string | undefined>();
  const [shotId, setShotId] = useState<string | undefined>();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const request = useRef(0);
  const pending = useRef<AbortController | null>(null);
  useEffect(() => () => pending.current?.abort(), []);
  const response = pin?.response ?? data?.response;
  const context = pin ? pin.context : data?.context;
  const ready = data && validCut(response, data.matchId, data.revision, second);
  const team = teams.find((team) => team.id === teamId) ?? teams[0];
  const result = response?.snapshot.teams.find(
    (row) => row.team_id === team.id,
  );
  const cut = response?.at_second ?? second;
  const networkMetric = result?.values.find(
    (metric) => metric.key === "pass_network_passes",
  );
  const player = (id: string) =>
    (data?.clubs ?? teams)
      .flatMap((team) => team.players)
      .find((player) => player.id === id)?.name ?? id;
  const metricLabel = (metric: Metric) =>
    t(`lab.metric_${metric.key}`, { defaultValue: metric.label ?? metric.key });
  const cancel = () => {
    request.current++;
    pending.current?.abort();
    pending.current = null;
    setLoading(false);
    setError("");
  };
  const clear = () => {
    cancel();
    setSelection(null);
    setHistorical(null);
    setEdge(undefined);
    setNode(undefined);
    setShotId(undefined);
  };
  const freeze = () => {
    if (!pin && response && data) setPin({ response, context: data.context });
  };
  const choose = (
    value: Omit<Selection, "key" | "matchId" | "cutoff" | "revision">,
  ) => {
    cancel();
    freeze();
    setHistorical(null);
    setEdge(undefined);
    setNode(undefined);
    setShotId(undefined);
    setSelection({
      ...value,
      key: String(request.current),
      matchId: data!.matchId,
      cutoff: cut,
      revision: data!.revision,
    });
  };
  const chooseMetric = (metric: Metric) =>
    choose({
      title: metricLabel(metric),
      value: metricText(metric, i18n.language),
      definition: metric.evidence?.description ?? t("lab.sourceUnavailable"),
      eventIds: metric.evidence?.event_ids ?? [],
    });
  const chooseEdge = (value: NetworkEdge) => {
    choose({
      title: `${player(value.from_player_id)} → ${player(value.to_player_id)}`,
      value: `${value.passes} ${t("lab.passes")}`,
      definition: t("lab.edgeDefinition"),
      eventIds: edgeIds(
        value,
        networkMetric,
        events,
        team.id,
        data!.matchId,
        cut,
      ),
      expectedCount: value.passes,
    });
    setEdge(value);
  };
  const chooseNode = (value: NetworkNode) => {
    choose({
      title: player(value.player_id),
      value: `${value.touches} ${t("lab.observations")}`,
      definition: t("lab.nodeDefinition"),
      eventIds: nodeIds(
        value.player_id,
        networkMetric,
        events,
        team.id,
        data!.matchId,
        cut,
      ),
      expectedCount: value.touches,
    });
    setNode(value.player_id);
  };
  const chooseShot = (value: Shot) => {
    choose({
      title: player(value.player_id),
      value: `${t("xg")} ${value.xg.toFixed(2)}`,
      definition: `${t("lab.shotDefinition")} · ${t(`lab.outcome_${value.outcome}`, { defaultValue: value.outcome })}`,
      eventIds: [value.event_id],
      expectedCount: 1,
    });
    setShotId(value.event_id);
    onSelect(value.event_id);
  };
  const rows = occurrences(
    context ?? null,
    data?.fixtures ?? [],
    data?.matchId ?? "",
    cut,
  );
  const choosePattern = async (row: (typeof rows)[number]) => {
    cancel();
    freeze();
    setHistorical(null);
    setEdge(undefined);
    setNode(undefined);
    setShotId(undefined);
    const token = request.current;
    const controller = new AbortController();
    pending.current = controller;
    const value: Selection = {
      key: String(token),
      title: t("lab.turnoverPattern"),
      value: `${row.pattern.elapsed_seconds} ${t("seconds")}`,
      definition: t("lab.patternDefinition"),
      eventIds: row.pattern.event_ids,
      matchId: row.pattern.match_id,
      cutoff: row.pattern.goal_second,
      revision: data!.revision,
      historical: row.fixtureId,
      chronological: true,
      expectedCount: row.pattern.event_ids.length,
    };
    setSelection(value);
    if (!row.fixtureId) return;
    setLoading(true);
    try {
      const artifact = await data!.history(row.fixtureId, controller.signal);
      if (controller.signal.aborted || token !== request.current) return;
      if (
        artifact.match_id !== row.pattern.match_id ||
        ![artifact.home_club_id, artifact.away_club_id].every((id) =>
          data!.clubs.some((club) => club.id === id),
        )
      )
        throw new Error("Historical source does not match its evidence");
      setHistorical(artifact);
    } catch (error) {
      if (!controller.signal.aborted && token === request.current)
        setError(
          `${t("lab.historyFailed")} ${error instanceof Error ? error.message : ""}`,
        );
    } finally {
      if (!controller.signal.aborted && token === request.current)
        setLoading(false);
    }
  };
  const shotSources = (result?.shot_map ?? []).filter(
    (shot) =>
      Number.isFinite(shot.xg) &&
      resolveEvidence(
        [shot.event_id],
        events,
        data?.matchId ?? "",
        cut,
      ).events.some(
        (event) => event.type === "shot" && event.team_id === team.id,
      ),
  );
  const sourceTeams = historical
    ? [historical.home_club_id, historical.away_club_id].flatMap((id) =>
        data!.clubs.filter((club) => club.id === id),
      )
    : teams;
  return (
    <section
      className="evidence-lab panel"
      id="analysis"
      aria-label={t("lab.title")}
    >
      <header className="lab-header">
        <div>
          <span className="eyebrow">
            <Crosshair size={16} />
            {t("lab.eyebrow")}
          </span>
          <h2>{t("lab.title")}</h2>
          <p>{t("lab.subtitle")}</p>
        </div>
        {ready && (
          <div className="lab-cut-controls">
            <span className="lab-cut">
              <PushPin size={14} />
              {t(pin ? "lab.pinned" : "lab.latest")} {clock(cut)}
            </span>
            {pin && (
              <button
                onClick={() => {
                  clear();
                  setPin(null);
                }}
              >
                {t("lab.resume")}
              </button>
            )}
          </div>
        )}
      </header>
      {!data ? (
        <p className="lab-empty">{t("lab.offline")}</p>
      ) : !ready ? (
        <div className="lab-empty" role="status">
          {t("lab.waiting")}
        </div>
      ) : (
        <>
          <div className="lab-metric-grid">
            {metricKeys.map((key) => {
              const metric = result?.values.find(
                (metric) => metric.key === key,
              );
              return (
                <button
                  key={key}
                  aria-label={`${t(`lab.metric_${key}`)} ${metricText(metric, i18n.language)} ${t("lab.inspect")}`}
                  onClick={() => metric && chooseMetric(metric)}
                  disabled={!metric}
                  aria-pressed={
                    selection?.title === (metric ? metricLabel(metric) : "")
                  }
                >
                  <span>{t(`lab.metric_${key}`)}</span>
                  <strong>{metricText(metric, i18n.language)}</strong>
                  <small>
                    {key === "xg_like"
                      ? t("syntheticMetric")
                      : t("lab.inspect")}
                  </small>
                </button>
              );
            })}
          </div>
          <div className="lab-toolbar">
            <div className="lab-tabs" role="group" aria-label={t("lab.view")}>
              {(["network", "shots", "patterns", "metrics"] as const).map(
                (value) => (
                  <button
                    key={value}
                    aria-pressed={tab === value}
                    onClick={() => {
                      clear();
                      setTab(value);
                    }}
                  >
                    {value === "network" && <ShareNetwork size={16} />}{" "}
                    {t(`lab.${value}`)}
                  </button>
                ),
              )}
            </div>
            <div className="lab-clubs" role="group" aria-label={t("lab.club")}>
              {teams.map((club) => (
                <button
                  key={club.id}
                  aria-pressed={team.id === club.id}
                  onClick={() => {
                    clear();
                    setTeamId(club.id);
                  }}
                >
                  <i
                    className={
                      club.id === teams[0].id
                        ? "home-legend legend"
                        : "away-legend legend"
                    }
                  />
                  {club.name}
                </button>
              ))}
            </div>
          </div>
          <div className="lab-workspace">
            <div className="lab-visual">
              {tab === "network" && (
                <NetworkChart
                  network={result?.pass_network}
                  teams={teams}
                  team={team}
                  selectedEdge={edge}
                  selectedNode={node}
                  onEdge={chooseEdge}
                  onNode={chooseNode}
                />
              )}
              {tab === "shots" && (
                <>
                  <ShotChart
                    shots={shotSources}
                    teams={teams}
                    team={team}
                    selectedId={shotId}
                    onShot={chooseShot}
                  />
                  {shotSources.length !== (result?.shot_map ?? []).length && (
                    <p className="lab-warning">{t("lab.incompleteSources")}</p>
                  )}
                </>
              )}
              {tab === "patterns" && (
                <div className="pattern-ledger">
                  <h3>{t("lab.turnoverPattern")}</h3>
                  <p>{t("lab.patternDefinition")}</p>
                  <span className="lab-pattern-count">
                    {context &&
                    context.at_second <= cut &&
                    context.revision === data.revision
                      ? context.verified_consecutive_matches
                      : "—"}{" "}
                    {t("pattern")}
                  </span>
                  <p className="chart-legend">{t("lab.patternNote")}</p>
                  {rows.map((row, index) => (
                    <button
                      key={`${row.fixtureId ?? "live"}:${index}`}
                      aria-pressed={Boolean(
                        selection?.chronological &&
                        selection.matchId === row.pattern.match_id,
                      )}
                      onClick={() => {
                        void choosePattern(row);
                      }}
                    >
                      <span className="pattern-fixture">
                        <strong>
                          {row.current
                            ? t("lab.currentMatch")
                            : `${t("lab.matchday")} ${row.fixture!.matchday}`}
                        </strong>
                        <small>
                          {row.current
                            ? teams.map((team) => team.name).join(" · ")
                            : [
                                row.fixture!.home_club_id,
                                row.fixture!.away_club_id,
                              ]
                                .map(
                                  (id) =>
                                    data.clubs.find((club) => club.id === id)
                                      ?.name ?? id,
                                )
                                .join(" · ")}
                        </small>
                      </span>
                      <span className="pattern-window">
                        {clock(row.pattern.loss_second)}{" "}
                        <ArrowRight size={16} />{" "}
                        {clock(row.pattern.goal_second)}
                      </span>
                      <strong>{row.pattern.elapsed_seconds}s</strong>
                    </button>
                  ))}
                  {!rows.length && (
                    <p className="lab-empty">{t("lab.noPattern")}</p>
                  )}
                </div>
              )}
              {tab === "metrics" && (
                <div className="lab-metric-table">
                  <p>{t("lab.definitions")}</p>
                  <table>
                    <thead>
                      <tr>
                        <th>{t("lab.metric")}</th>
                        <th>{t("lab.value")}</th>
                        <th>{t("lab.sources")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(result?.values ?? []).map((metric) => (
                        <tr key={metric.key}>
                          <td>
                            <button onClick={() => chooseMetric(metric)}>
                              {metricLabel(metric)}
                            </button>
                            <code>{metric.key}</code>
                          </td>
                          <td>
                            {metricText(metric, i18n.language)}
                            {metric.unit &&
                              !["count", "%"].includes(metric.unit) && (
                                <small>{metric.unit}</small>
                              )}
                          </td>
                          <td>{metric.evidence?.event_ids.length ?? "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
            {loading ? (
              <aside className="lab-inspector" role="status">
                {t("lab.loadingHistory")}
              </aside>
            ) : error ? (
              <aside className="lab-inspector" role="alert">
                {error}
                <button onClick={clear}>{t("lab.clear")}</button>
              </aside>
            ) : (
              <Inspector
                key={selection?.key ?? "none"}
                selection={selection}
                events={historical?.events ?? events}
                teams={sourceTeams}
                sessionId={data.sessionId}
                liveMatchId={data.matchId}
                onSelect={onSelect}
              />
            )}
          </div>
          <footer className="lab-footer">
            <span>{t("lab.orientation")}</span>
            <span>{t("lab.authority")}</span>
          </footer>
        </>
      )}
    </section>
  );
}
