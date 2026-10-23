import assert from "node:assert/strict";
import process from "node:process";

const origin = (process.argv[2] ?? "http://127.0.0.1:8000").replace(/\/$/, "");
const at = (event) => event.minute * 60 + event.second;
async function api(path, body, method = body ? "POST" : "GET") {
  const response = await fetch(`${origin}/api/v1${path}`, {
    method,
    body: body ? JSON.stringify(body) : undefined,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    signal: AbortSignal.timeout(30000),
  });
  assert(response.ok, `${method} ${path}: HTTP ${response.status}`);
  return response.status === 204 ? null : response.json();
}
const session = await api("/sessions", {
  scenario: "ashford-demo-v1",
  speed: 4,
});
const prefix = `/sessions/${session.session_id}`;
try {
  const counts = [];
  for (const second of [3719, 3720]) {
    const state = await api(`${prefix}/controls`, { action: "seek", second });
    const events = [];
    let cursor = 0;
    for (;;) {
      const page = await api(
        `${prefix}/events?after_sequence=${cursor}&limit=100&revision=${state.revision}`,
      );
      assert.equal(page.revision, state.revision);
      events.push(...page.events.map((item) => item.event));
      if (!page.has_more) break;
      assert(page.next_sequence - 1 > cursor);
      cursor = page.next_sequence - 1;
    }
    assert(events.every((event) => at(event) <= second));
    const response = await api(
      `${prefix}/metrics?advanced=true&at_second=${second}`,
    );
    assert.equal(response.revision, state.revision);
    assert.equal(response.at_second, second);
    const index = new Map(events.map((event) => [event.id, event]));
    let edgeCount = 0,
      shotCount = 0;
    for (const team of response.snapshot.teams) {
      for (const metric of team.values)
        for (const id of metric.evidence.event_ids)
          assert(index.has(id), `Unresolved ${metric.key}: ${id}`);
      const networkIds = team.values.find(
        (metric) => metric.key === "pass_network_passes",
      ).evidence.event_ids;
      const passes = networkIds.map((id) => index.get(id));
      for (const edge of team.pass_network.edges) {
        assert.equal(
          passes.filter(
            (event) =>
              event.player_id === edge.from_player_id &&
              event.related_player_id === edge.to_player_id,
          ).length,
          edge.passes,
        );
        edgeCount++;
      }
      for (const node of team.pass_network.nodes)
        assert.equal(
          passes.filter((event) => event.player_id === node.player_id).length +
            passes.filter((event) => event.related_player_id === node.player_id)
              .length,
          node.touches,
        );
      for (const shot of team.shot_map) {
        const event = index.get(shot.event_id);
        assert(event);
        assert.equal(event.type, "shot");
        assert.equal(event.expected_value, shot.xg);
        assert.deepEqual(event.start, shot.location);
        shotCount++;
      }
      assert.deepEqual(
        new Set(
          team.values.find((metric) => metric.key === "xg_like").evidence
            .event_ids,
        ),
        new Set(team.shot_map.map((shot) => shot.event_id)),
      );
    }
    const context = await api(`${prefix}/context`);
    assert.equal(context.revision, state.revision);
    if (second === 3719) assert.equal(context.climax, null);
    else {
      assert.equal(context.climax.elapsed_seconds, 20);
      assert(context.climax.event_ids.every((id) => index.has(id)));
      for (const [fixtureId, patterns] of Object.entries(
        context.historical_patterns,
      )) {
        const artifact = await api(`${prefix}/history/${fixtureId}`);
        const sources = new Map(
          artifact.frames
            .flatMap((frame) => frame.events)
            .map((event) => [event.id, event]),
        );
        for (const pattern of patterns) {
          assert.equal(artifact.match_id, pattern.match_id);
          assert(
            pattern.event_ids.every(
              (id) =>
                sources.has(id) && at(sources.get(id)) <= pattern.goal_second,
            ),
          );
        }
      }
    }
    counts.push({
      cut: second,
      events: events.length,
      networkEdges: edgeCount,
      shots: shotCount,
      score: state.score,
      revision: state.revision,
    });
  }
  console.log(
    JSON.stringify(
      {
        backend: origin,
        checks:
          "metric IDs, directed edge counts, node observations, shot sources, temporal cuts and historical artifacts",
        cuts: counts,
      },
      null,
      2,
    ),
  );
} finally {
  await api(prefix, undefined, "DELETE");
}
