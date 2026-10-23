import { useId, useState, type KeyboardEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { displayPoint, type Team } from "../match/model";
import { edgePath } from "./evidence";
import type { NetworkEdge, NetworkNode, PassNetwork, Shot } from "./contracts";

const keyActivate = (event: KeyboardEvent<SVGGElement>, action: () => void) => {
  if (event.key === "Enter" || event.key === " ") {
    event.preventDefault();
    action();
  }
};
export function TacticalField({
  title,
  children,
  spatial = true,
}: {
  title: string;
  children: ReactNode;
  spatial?: boolean;
}) {
  return (
    <svg
      className="analyst-field"
      viewBox="-32 -32 1114 744"
      role="group"
      aria-label={title}
    >
      <rect width="1050" height="680" fill="#1f1f1f" />
      {spatial && <g
        fill="none"
        stroke="#747a70"
        strokeWidth="2"
        opacity=".6"
        aria-hidden="true"
      >
        <rect width="1050" height="680" />
        <path d="M525 0V680 M0 138H165V542H0 M1050 138H885V542H1050 M0 248H55V432H0 M1050 248H995V432H1050" />
        <circle cx="525" cy="340" r="91.5" />
        <circle cx="110" cy="340" r="3" />
        <circle cx="940" cy="340" r="3" />
      </g>}
      {children}
    </svg>
  );
}
export function NetworkChart({
  network,
  teams,
  team,
  selectedEdge,
  selectedNode,
  onEdge,
  onNode,
}: {
  network: PassNetwork | null | undefined;
  teams: Team[];
  team: Team;
  selectedEdge?: NetworkEdge;
  selectedNode?: string;
  onEdge: (edge: NetworkEdge) => void;
  onNode: (node: NetworkNode) => void;
}) {
  const { t } = useTranslation();
  const [layout, setLayout] = useState<"topology" | "positions">("topology");
  const marker = useId().replace(/:/g, "");
  const colour = team.id === teams[0].id ? "#c4f568" : "#f2ad82";
  const player = (id: string) =>
    team.players.find((player) => player.id === id);
  const name = (id: string) => player(id)?.name ?? id;
  const located = (network?.nodes ?? []).filter(
    (node) =>
      node.avg_location &&
      Number.isFinite(node.avg_location.x) &&
      Number.isFinite(node.avg_location.y),
  );
  located.sort((a, b) => (player(a.player_id)?.number ?? 0) - (player(b.player_id)?.number ?? 0));
  const points = new Map(
    located.map((node, index) => {
      if (layout === "topology") {
        const angle = -Math.PI / 2 + 2 * Math.PI * index / located.length;
        return [node.player_id, { x: 525 + 370 * Math.cos(angle), y: 340 + 245 * Math.sin(angle) }];
      }
      const point = displayPoint(node.avg_location!, team.id, teams[0].id);
      return [node.player_id, { x: point.x * 10.5, y: point.y * 6.8 }];
    }),
  );
  const edges = (network?.edges ?? []).filter(
    (edge) => points.has(edge.from_player_id) && points.has(edge.to_player_id),
  );
  const label = (edge: NetworkEdge) =>
    `${name(edge.from_player_id)} → ${name(edge.to_player_id)} · ${edge.passes} ${t("lab.passes")}`;
  const picked = (edge: NetworkEdge) =>
    selectedEdge
      ? edge.from_player_id === selectedEdge.from_player_id &&
        edge.to_player_id === selectedEdge.to_player_id
      : selectedNode
        ? [edge.from_player_id, edge.to_player_id].includes(selectedNode)
        : false;
  if (!located.length) return <p className="lab-empty">{t("lab.noNetwork")}</p>;
  return (
    <>
      <div className="network-layout" role="group" aria-label={t("lab.networkLayout")}>
        <button aria-pressed={layout === "topology"} onClick={() => setLayout("topology")}>{t("lab.layoutTopology")}</button>
        <button aria-pressed={layout === "positions"} onClick={() => setLayout("positions")}>{t("lab.layoutPositions")}</button>
      </div>
      <TacticalField spatial={layout === "positions"} title={`${t("lab.network")} · ${team.name}`}>
        <defs>
          <marker
            id={marker}
            markerWidth="12"
            markerHeight="12"
            refX="11"
            refY="6"
            orient="auto"
            markerUnits="userSpaceOnUse"
          >
            <path d="M0 0 12 6 0 12" fill={colour} />
          </marker>
        </defs>
        {edges.map((edge) => (
          <g
            key={`${edge.from_player_id}:${edge.to_player_id}`}
            role="button"
            tabIndex={0}
            aria-label={label(edge)}
            aria-pressed={picked(edge)}
            onClick={() => onEdge(edge)}
            onKeyDown={(event) => keyActivate(event, () => onEdge(edge))}
            className="chart-target"
          >
            <title>{label(edge)}</title>
            <path
              d={edgePath(
                points.get(edge.from_player_id)!,
                points.get(edge.to_player_id)!,
              )}
              fill="none"
              stroke="transparent"
              strokeWidth="24"
            />
            <path
              className="network-link"
              d={edgePath(
                points.get(edge.from_player_id)!,
                points.get(edge.to_player_id)!,
              )}
              fill="none"
              stroke={colour}
              strokeWidth={
                picked(edge) ? 7 : Math.min(6, 1 + Math.sqrt(edge.passes))
              }
              opacity={picked(edge) ? 1 : 0.24}
              markerEnd={`url(#${marker})`}
            />
          </g>
        ))}
        {located.map((node) => {
          const p = points.get(node.player_id)!;
          return (
            <g
              key={node.player_id}
              role="button"
              tabIndex={0}
              aria-label={`${name(node.player_id)} · ${node.touches} ${t("lab.observations")}`}
              aria-pressed={selectedNode === node.player_id}
              onClick={() => onNode(node)}
              onKeyDown={(event) => keyActivate(event, () => onNode(node))}
              className="chart-target"
            >
              <title>{name(node.player_id)}</title>
              <circle
                cx={p.x}
                cy={p.y}
                r={18 + Math.min(12, Math.sqrt(node.touches))}
                fill={selectedNode === node.player_id ? colour : "#181818"}
                stroke={colour}
                strokeWidth="3"
              />
              <text
                x={p.x}
                y={p.y + 8}
                textAnchor="middle"
                fill={selectedNode === node.player_id ? "#181818" : colour}
                fontSize="24"
                fontWeight="700"
              >
                {player(node.player_id)?.number ?? "?"}
              </text>
              {layout === "topology" && <text x={p.x} y={p.y + 55} textAnchor="middle" fill="#deded8" fontSize="20">{name(node.player_id).split(" ").at(-1)}</text>}
            </g>
          );
        })}
      </TacticalField>
      <p className="chart-legend">{t(layout === "topology" ? "lab.topologyLegend" : "lab.networkLegend")}</p>
      <div className="network-ranking">
        <h4>{t("lab.strongest")}</h4>
        {[...edges]
          .sort(
            (a, b) => b.passes - a.passes || label(a).localeCompare(label(b)),
          )
          .slice(0, 6)
          .map((edge) => (
            <button
              key={`${edge.from_player_id}:${edge.to_player_id}`}
              onClick={() => onEdge(edge)}
              aria-pressed={picked(edge)}
            >
              <span>
                {name(edge.from_player_id)} <span aria-hidden="true">→</span>{" "}
                {name(edge.to_player_id)}
              </span>
              <strong>{edge.passes}</strong>
            </button>
          ))}
      </div>
    </>
  );
}
export function ShotChart({
  shots,
  teams,
  team,
  selectedId,
  onShot,
}: {
  shots: Shot[];
  teams: Team[];
  team: Team;
  selectedId?: string;
  onShot: (shot: Shot) => void;
}) {
  const { t } = useTranslation();
  const player = (id: string) =>
    team.players.find((player) => player.id === id)?.name ?? id;
  const colour = team.id === teams[0].id ? "#c4f568" : "#f2ad82";
  const label = (shot: Shot) =>
    `${player(shot.player_id)} · ${t(`lab.outcome_${shot.outcome}`, { defaultValue: shot.outcome })} · ${t("xg")} ${shot.xg.toFixed(2)}`;
  if (!shots.length) return <p className="lab-empty">{t("lab.noShots")}</p>;
  return (
    <>
      <TacticalField title={`${t("lab.shots")} · ${team.name}`}>
        {shots.map((shot) => {
          const point = displayPoint(shot.location, team.id, teams[0].id);
          const x = point.x * 10.5,
            y = point.y * 6.8,
            r = 7 + Math.sqrt(Math.max(0, shot.xg)) * 28;
          const selected = shot.event_id === selectedId;
          return (
            <g
              key={shot.event_id}
              role="button"
              tabIndex={0}
              aria-label={label(shot)}
              aria-pressed={selected}
              onClick={() => onShot(shot)}
              onKeyDown={(event) => keyActivate(event, () => onShot(shot))}
              className="chart-target"
            >
              <title>{label(shot)}</title>
              <circle
                cx={x}
                cy={y}
                r={Math.max(22, r + 8)}
                fill="transparent"
              />
              {shot.outcome === "goal" ? (
                <path
                  d={`M${x} ${y - r}L${x + r} ${y}L${x} ${y + r}L${x - r} ${y}Z`}
                  fill={selected ? colour : "#181818"}
                  stroke={colour}
                  strokeWidth={selected ? 6 : 3}
                />
              ) : (
                <circle
                  cx={x}
                  cy={y}
                  r={r}
                  fill={selected ? colour : "#181818"}
                  stroke={colour}
                  strokeWidth={selected ? 6 : 3}
                />
              )}
            </g>
          );
        })}
      </TacticalField>
      <p className="chart-legend">{t("lab.shotLegend")}</p>
      <div className="shot-ranking">
        <h4>{t("lab.highValueShots")}</h4>
        {[...shots]
          .sort((a, b) => b.xg - a.xg || a.event_id.localeCompare(b.event_id))
          .slice(0, 6)
          .map((shot) => (
            <button
              key={shot.event_id}
              onClick={() => onShot(shot)}
              aria-pressed={selectedId === shot.event_id}
            >
              <span>
                {player(shot.player_id)}
                <small>
                  {t(`lab.outcome_${shot.outcome}`, {
                    defaultValue: shot.outcome,
                  })}
                </small>
              </span>
              <strong>{shot.xg.toFixed(2)}</strong>
            </button>
          ))}
      </div>
    </>
  );
}
