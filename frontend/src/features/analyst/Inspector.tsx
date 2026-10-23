import { useState } from "react";
import { useTranslation } from "react-i18next";
import { ArrowDown, Crosshair } from "@phosphor-icons/react";
import { Pitch } from "../match/Pitch";
import { clock, type MatchEvent, type Team } from "../match/model";
import { resolveEvidence } from "./evidence";

export interface Selection {
  key: string;
  title: string;
  value?: string;
  definition: string;
  eventIds: string[];
  matchId: string;
  cutoff: number;
  revision: number;
  historical?: string;
  expectedCount?: number;
  chronological?: boolean;
}
export function Inspector({
  selection,
  events,
  teams,
  sessionId,
  liveMatchId,
  onSelect,
}: {
  selection: Selection | null;
  events: MatchEvent[];
  teams: Team[];
  sessionId: string;
  liveMatchId: string;
  onSelect: (id: string) => void;
}) {
  const { t } = useTranslation();
  const [page, setPage] = useState(0);
  const [focusedId, setFocused] = useState<string | null>(null);
  if (!selection)
    return (
      <aside className="lab-inspector lab-inspector-empty">
        <Crosshair size={28} />
        <h3>{t("lab.inspectTitle")}</h3>
        <p>{t("lab.inspectHint")}</p>
        <ol>
          <li>{t("lab.inspectStep1")}</li>
          <li>{t("lab.inspectStep2")}</li>
          <li>{t("lab.inspectStep3")}</li>
        </ol>
      </aside>
    );
  const resolved = resolveEvidence(
    selection.eventIds,
    events,
    selection.matchId,
    selection.cutoff,
  );
  const ordered = selection.chronological
    ? resolved.events
    : [...resolved.events].reverse();
  const focused =
    resolved.events.find((event) => event.id === focusedId) ??
    resolved.events.at(-1);
  const player = (id: string) =>
    teams.flatMap((team) => team.players).find((player) => player.id === id)
      ?.name ?? id;
  const choose = (event: MatchEvent) => {
    setFocused(event.id);
    if (selection.matchId === liveMatchId) onSelect(event.id);
  };
  const incomplete =
    resolved.missing.length > 0 ||
    (selection.expectedCount !== undefined &&
      resolved.events.length !== selection.expectedCount);
  return (
    <aside
      className="lab-inspector"
      id="analysis-evidence"
      aria-label={t("lab.inspector")}
    >
      <div className="inspector-heading">
        <span className="eyebrow">{t("lab.inspector")}</span>
        <span className="lab-cut">
          {selection.historical ? t("lab.historical") : t("lab.currentMatch")}
        </span>
      </div>
      <h3>{selection.title}</h3>
      {selection.value && (
        <strong className="inspector-value">{selection.value}</strong>
      )}
      <p className="lab-definition">{selection.definition}</p>
      <p className="lab-resolution" role="status">
        {resolved.events.length} {t("lab.sourcesResolved")} ·{" "}
        {clock(selection.cutoff)}
        {incomplete && <span>{t("lab.incompleteSources")}</span>}
      </p>
      {focused && teams.length === 2 && (
        <div className="evidence-pitch">
          <Pitch selected={focused} visible={resolved.events} teams={teams} />
        </div>
      )}
      <div className="lab-source-list" aria-label={t("lab.sourceActions")}>
        {ordered.slice(page * 12, (page + 1) * 12).map((event) => (
          <button
            key={event.id}
            aria-label={`${clock(event.minute * 60 + event.second)} ${t(event.type === "goal" ? "goalEvent" : event.type, { defaultValue: event.type })} ${player(event.player_id)}`}
            onClick={() => choose(event)}
            aria-pressed={focused?.id === event.id}
          >
            <time>{clock(event.minute * 60 + event.second)}</time>
            <span>
              <strong>
                {t(event.type === "goal" ? "goalEvent" : event.type, {
                  defaultValue: event.type,
                })}
              </strong>
              <small>{player(event.player_id)}</small>
            </span>
            <ArrowDown size={14} />
          </button>
        ))}
      </div>
      {!resolved.events.length && (
        <p className="lab-empty">
          {t(
            selection.eventIds.length
              ? "lab.sourceUnavailable"
              : "lab.noSources",
          )}
        </p>
      )}
      {ordered.length > 12 && (
        <div className="lab-pagination">
          <button disabled={page === 0} onClick={() => setPage((n) => n - 1)}>
            {t("lab.previous")}
          </button>
          <span>
            {page + 1} / {Math.ceil(ordered.length / 12)}
          </span>
          <button
            disabled={(page + 1) * 12 >= ordered.length}
            onClick={() => setPage((n) => n + 1)}
          >
            {t("lab.next")}
          </button>
        </div>
      )}
      {focused && (
        <dl className="lab-event-facts">
          <div>
            <dt>{t("start")}</dt>
            <dd>
              {focused.start.x.toFixed(1)}, {focused.start.y.toFixed(1)}
            </dd>
          </div>
          <div>
            <dt>{t("end")}</dt>
            <dd>
              {focused.end
                ? `${focused.end.x.toFixed(1)}, ${focused.end.y.toFixed(1)}`
                : "—"}
            </dd>
          </div>
          <div>
            <dt>{t("outcome")}</dt>
            <dd>{t(focused.outcome === "success" ? "success" : "fail")}</dd>
          </div>
        </dl>
      )}
      <details className="lab-provenance">
        <summary>{t("lab.provenance")}</summary>
        <dl>
          <dt>{t("sessionId")}</dt>
          <dd>
            <code>{sessionId}</code>
          </dd>
          <dt>{t("lab.matchId")}</dt>
          <dd>
            <code>{selection.matchId}</code>
          </dd>
          <dt>{t("lab.revision")}</dt>
          <dd>{selection.revision}</dd>
          <dt>{t("lab.cut")}</dt>
          <dd>{clock(selection.cutoff)}</dd>
          {selection.historical && (
            <>
              <dt>{t("lab.fixture")}</dt>
              <dd>
                <code>{selection.historical}</code>
              </dd>
            </>
          )}
          {focused && (
            <>
              <dt>{t("eventId")}</dt>
              <dd>
                <code>{focused.id}</code>
              </dd>
              <dt>{t("possessionId")}</dt>
              <dd>
                <code>{focused.possession_id ?? "—"}</code>
              </dd>
            </>
          )}
        </dl>
        {resolved.missing.length > 0 && (
          <p>
            {t("lab.unresolvedIds")}
            <code>{resolved.missing.join("\n")}</code>
          </p>
        )}
      </details>
    </aside>
  );
}
