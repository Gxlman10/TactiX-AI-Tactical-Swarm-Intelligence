import { useTranslation } from "react-i18next";
import {
  displayPoint,
  fixture,
  player,
  timeOf,
  type MatchEvent,
} from "./model";
export function Pitch({
  selected,
  visible,
}: {
  selected: MatchEvent | undefined;
  visible: MatchEvent[];
}) {
  const { t } = useTranslation();
  const chain = selected
    ? visible.filter(
        (e) =>
          e.possession_id === selected.possession_id &&
          timeOf(e) <= timeOf(selected),
      )
    : [];
  const point = selected && displayPoint(selected.start, selected.team_id);
  const end = selected?.end && displayPoint(selected.end, selected.team_id);
  const colour =
    selected?.team_id === fixture.teams[0].id ? "#c4f568" : "#f2ad82";
  return (
    <svg
      className="pitch"
      viewBox="-45 -45 1140 770"
      role="img"
      aria-label={`${t("pitch")}: ${selected ? `${player(selected.player_id)?.name} · ${t(selected.type === "goal" ? "goalEvent" : selected.type)}` : t("none")}`}
    >
      <defs>
        <marker
          id="move-arrow"
          markerWidth="6"
          markerHeight="6"
          refX="5"
          refY="3"
          orient="auto"
        >
          <path d="M0 0 6 3 0 6" fill={colour} />
        </marker>
      </defs>
      <rect x="0" y="0" width="1050" height="680" rx="4" fill="#1f1f1f" />
      {[1, 3, 5, 7, 9].map((i) => (
        <rect
          key={i}
          x={i * 105}
          y="0"
          width="105"
          height="680"
          fill="#272727"
          opacity=".32"
        />
      ))}
      <g fill="none" stroke="#a1a79d" strokeWidth="1.5" opacity=".5">
        <rect width="1050" height="680" />
        <path d="M525 0V680" />
        <circle cx="525" cy="340" r="91.5" />
        <circle cx="525" cy="340" r="3" fill="#a1a79d" />
        <path d="M0 138H165V542H0 M1050 138H885V542H1050 M0 248H55V432H0 M1050 248H995V432H1050 M-18 303H0V377H-18Z M1050 303H1068V377H1050Z" />
        <circle cx="110" cy="340" r="3" fill="#a1a79d" />
        <circle cx="940" cy="340" r="3" fill="#a1a79d" />
        <path d="M165 267A91.5 91.5 0 0 1 165 413 M885 267A91.5 91.5 0 0 0 885 413" />
      </g>
      {chain
        .filter((e) => e.end && ["pass", "carry", "dribble"].includes(e.type))
        .map((e) => {
          const a = displayPoint(e.start, e.team_id);
          const b = displayPoint(e.end!, e.team_id);
          return (
            <path
              key={e.id}
              d={`M${a.x * 10.5} ${a.y * 6.8}L${b.x * 10.5} ${b.y * 6.8}`}
              fill="none"
              stroke={colour}
              strokeWidth="3"
              opacity=".3"
              strokeDasharray={e.outcome === "fail" ? "8 8" : undefined}
            />
          );
        })}
      {point && (
        <>
          <circle
            cx={point.x * 10.5}
            cy={point.y * 6.8}
            r="30"
            fill={colour}
            opacity=".12"
          />
          {end && (
            <path
              d={`M${point.x * 10.5} ${point.y * 6.8}L${end.x * 10.5} ${end.y * 6.8}`}
              stroke={colour}
              strokeWidth="3"
              markerEnd="url(#move-arrow)"
              strokeDasharray={selected?.outcome === "fail" ? "8 8" : undefined}
            />
          )}
          <circle cx={point.x * 10.5} cy={point.y * 6.8} r="17" fill={colour} />
          <text
            x={point.x * 10.5}
            y={point.y * 6.8 + 6}
            fill="#181818"
            textAnchor="middle"
            fontSize="18"
            fontWeight="700"
          >
            {player(selected!.player_id)?.number}
          </text>
          <g
            transform={`translate(${Math.min(850, Math.max(10, point.x * 10.5 - 85))},${point.y * 6.8 + 40})`}
          >
            <rect
              width="180"
              height="40"
              rx="8"
              fill="#181818"
              stroke="#464942"
            />
            <text
              x="90"
              y="26"
              textAnchor="middle"
              fill="#f5f5ef"
              fontSize="16"
            >
              {player(selected!.player_id)?.name}
            </text>
          </g>
        </>
      )}
      <text x="0" y="725" fill="#a7afa0" fontSize="14">
        ASHFORD →
      </text>
      <text x="1050" y="725" fill="#a7afa0" fontSize="14" textAnchor="end">
        ← NORTHBRIDGE
      </text>
    </svg>
  );
}
