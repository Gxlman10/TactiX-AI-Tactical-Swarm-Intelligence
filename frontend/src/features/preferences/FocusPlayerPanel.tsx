import { useTranslation } from "react-i18next";
import { type MatchEvent, type Team, timeOf } from "../match/model";

export function FocusPlayerPanel({
  playerId,
  teams,
  events,
  second,
}: {
  playerId: string | null;
  teams: Team[];
  events: MatchEvent[];
  second: number;
}) {
  const { t } = useTranslation();
  if (!playerId) return null;
  const team = teams.find((candidate) =>
    candidate.players.some((player) => player.id === playerId),
  );
  const player = team?.players.find((candidate) => candidate.id === playerId);
  if (!team || !player) return null;
  const actions = events.filter(
    (event) => event.player_id === playerId && timeOf(event) <= second,
  );
  const successful = actions.filter((event) => event.outcome === "success");
  const proxyRating = actions.length
    ? Math.min(10, (successful.length / actions.length) * 7 + Math.min(actions.length, 6) * 0.5)
    : 0;
  const points = actions
    .filter((event) => event.start)
    .map((event) => `${event.start.x},${100 - event.start.y}`)
    .join(" ");
  return (
    <section className="focus-player panel" aria-label={t("focusSummary")}>
      <div className="panel-heading">
        <div>
          <span className="section-tag">{t("focusPlayer")}</span>
          <h2>{player.name}</h2>
          <p>{team.name} · #{player.number}</p>
        </div>
        <strong className="focus-rating">
          {proxyRating.toFixed(1)}<small>/10 {t("proxy")}</small>
        </strong>
      </div>
      <div className="focus-grid">
        <div className="focus-heatmap" aria-label={t("focusHeatmap")}>
          <svg viewBox="0 0 100 100" role="img" aria-hidden="true">
            <rect x="1" y="1" width="98" height="98" rx="4" />
            <line x1="50" y1="1" x2="50" y2="99" />
            <circle cx="50" cy="50" r="15" />
            {points && <polyline points={points} />}
            {actions.map((event) => (
              <circle
                key={event.id}
                className="focus-point"
                cx={event.start.x}
                cy={100 - event.start.y}
                r="2.2"
              />
            ))}
          </svg>
        </div>
        <dl className="focus-stats">
          <div>
            <dt>{t("focusActions")}</dt>
            <dd>{actions.length}</dd>
          </div>
          <div>
            <dt>{t("focusSuccessful")}</dt>
            <dd>{successful.length}</dd>
          </div>
          <div>
            <dt>{t("focusShots")}</dt>
            <dd>{actions.filter((event) => ["shot", "goal"].includes(event.type)).length}</dd>
          </div>
        </dl>
      </div>
      <p className="focus-note">{t("focusProxyNote")}</p>
    </section>
  );
}
