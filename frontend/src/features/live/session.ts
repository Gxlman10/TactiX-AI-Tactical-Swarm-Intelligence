import { ReplayStream, type ReplaySource } from "./stream";
import type {
  HistoricalMatch,
  HistoricalArtifact,
  FixtureSummary,
} from "../analyst/contracts";
import {
  MatchApi,
  ApiError,
  readReplay,
  type ReplayUpdate,
  type SessionInfo,
  type League,
  type EventPage,
  type MetricsResponse,
  type ApiContext,
  type Control,
  type MatchReportRun,
} from "./api";
import { timeOf, type MatchEvent, type Team } from "../match/model";

export type Connection =
  "idle" | "connecting" | "connected" | "reconnecting" | "closed" | "error";
export interface LiveState {
  connection: Connection;
  info: SessionInfo | null;
  teams: Team[];
  clubs: Team[];
  fixtures: FixtureSummary[];
  season: string;
  events: ReplayUpdate["events"];
  metrics: MetricsResponse | null;
  context: ApiContext | null;
  selectedId: string | null;
  busy: boolean;
  rebuilding: boolean;
  error: string;
  report: MatchReportRun | null;
  analyzing: boolean;
  retryAt: number | null;
  retryAttempt: number;
}
const initial = (): LiveState => ({
  connection: "idle",
  info: null,
  teams: [],
  clubs: [],
  fixtures: [],
  season: "",
  events: [],
  metrics: null,
  context: null,
  selectedId: null,
  busy: false,
  rebuilding: false,
  error: "",
  report: null,
  analyzing: false,
  retryAt: null,
  retryAttempt: 0,
});

/** Owns one browser subscription, not the shared match clock. */
export class LiveSession {
  private state = initial();
  private listeners = new Set<() => void>();
  private generation = 0;
  private reconstruction = 0;
  private source: ReplaySource | null = null;
  private timer: ReturnType<typeof setInterval> | undefined;
  private retry: ReturnType<typeof setTimeout> | undefined;
  private abort = new AbortController();
  private owned: string | null = null;
  private refreshing = false;
  private controlPending = false;
  private following = true;
  private resumeToken: string | undefined;
  private recovering = false;
  constructor(
    private api = new MatchApi(),
    private sourceFactory: (url: string, token?: string) => ReplaySource = (
      url,
      token,
    ) => new ReplayStream(url, token),
  ) {}
  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };
  getSnapshot = () => this.state;
  private set(change: Partial<LiveState>) {
    this.state = { ...this.state, ...change };
    this.listeners.forEach((listener) => listener());
  }
  private current(generation: number) {
    return generation === this.generation && !this.abort.signal.aborted;
  }
  private async get<T>(path: string, signal?: AbortSignal) {
    return this.api.request<T>(path, {
      signal: AbortSignal.any([
        this.abort.signal,
        AbortSignal.timeout(20000),
        ...(signal ? [signal] : []),
      ]),
    });
  }
  dispose = () => {
    this.generation++;
    this.reconstruction++;
    this.abort.abort();
    this.resumeToken = undefined;
    this.recovering = false;
    this.source?.close();
    this.source = null;
    clearInterval(this.timer);
    clearTimeout(this.retry);
    const owned = this.owned;
    this.owned = null;
    if (owned) void this.api.remove(owned).catch(() => undefined);
  };
  leave = () => {
    this.dispose();
    this.state = initial();
    this.set({});
  };
  async start(joinId?: string) {
    this.dispose();
    this.abort = new AbortController();
    this.refreshing = false;
    this.controlPending = false;
    this.following = true;
    const generation = this.generation;
    this.state = initial();
    this.set({ connection: "connecting", busy: true });
    try {
      // Do not abort POST creation: if the viewer leaves, its response still lets us release it.
      const info = joinId
        ? await this.api.session(joinId, this.abort.signal)
        : await this.api.create();
      if (!this.current(generation)) {
        if (!joinId) await this.api.remove(info.session_id);
        return;
      }
      if (!joinId) this.owned = info.session_id;
      this.set({ info });
      const league = await this.get<League>(
        `/sessions/${info.session_id}/league`,
      );
      if (!this.current(generation)) return;
      const teams = [info.home_club_id, info.away_club_id].map((id) => {
        const club = league.clubs.find((club) => club.id === id);
        if (!club) throw new Error("Session club is missing from its league");
        return {
          id: club.id,
          name: club.name,
          city: club.city,
          formation: club.tactical_identity.formation,
          players: club.squad,
        };
      });
      this.set({
        teams,
        season: league.season,
        fixtures: league.fixtures ?? [],
        clubs: league.clubs.map((club) => ({
          id: club.id,
          name: club.name,
          city: club.city,
          formation: club.tactical_identity.formation,
          players: club.squad,
        })),
      });
      if (!joinId) {
        const update = await this.api.control(info.session_id, {
          action: "seek",
          second: 3660,
        });
        if (!this.current(generation)) return;
        this.apply(update);
      }
      await this.rebuild(generation);
      if (!this.current(generation)) return;
      this.set({ busy: false, connection: "connected" });
      this.connect(generation);
    } catch (error) {
      this.failure(error, generation);
    }
  }
  private failure(error: unknown, generation: number) {
    if (!this.current(generation)) return;
    const closed = error instanceof ApiError && error.status === 404;
    clearTimeout(this.retry);
    this.set({
      connection: closed ? "closed" : "error",
      retryAt: null,
      busy: false,
      error: error instanceof Error ? error.message : "Connection failed",
    });
    this.source?.close();
    clearInterval(this.timer);
  }
  private merge(events: ReplayUpdate["events"], cutoff: number) {
    const merged = new Map(
      this.state.events.map((item) => [item.sequence, item]),
    );
    for (const item of events)
      if (timeOf(item.event) <= cutoff) merged.set(item.sequence, item);
    return [...merged.values()]
      .filter((item) => timeOf(item.event) <= cutoff)
      .sort((a, b) => a.sequence - b.sequence);
  }
  private apply(update: ReplayUpdate) {
    const info = this.state.info;
    if (
      !info ||
      update.match_id !== info.state.match_id ||
      update.revision < info.state.revision
    )
      return;
    const reset = update.revision > info.state.revision;
    if (!reset && update.position_seconds < info.state.position_seconds) return;
    if (reset) {
      this.following = true;
      this.resumeToken = undefined;
    }
    if (reset)
      this.set({
        report: null,
        events: [],
        metrics: null,
        context: null,
        selectedId: null,
        rebuilding: true,
      });
    const events = this.merge(update.events, update.position_seconds);
    const selectedId =
      !this.following &&
      events.some((item) => item.event.id === this.state.selectedId)
        ? this.state.selectedId
        : (events.at(-1)?.event.id ?? null);
    this.set({ info: { ...info, state: update }, events, selectedId });
  }
  private async rebuild(generation: number) {
    const reconstruction = ++this.reconstruction;
    this.set({ rebuilding: true });
    const info = this.state.info!;
    const revision = info.state.revision;
    let cursor = 0;
    for (;;) {
      const page = await this.get<EventPage>(
        `/sessions/${info.session_id}/events?after_sequence=${cursor}&limit=500&revision=${revision}`,
      );
      if (
        !this.current(generation) ||
        reconstruction !== this.reconstruction ||
        this.state.info?.state.revision !== revision
      )
        return;
      if (page.revision !== revision)
        throw new ApiError(409, "Timeline revision changed");
      const events = this.merge(
        page.events,
        this.state.info.state.position_seconds,
      );
      this.set({
        events,
        selectedId:
          !this.following &&
          events.some((item) => item.event.id === this.state.selectedId)
            ? this.state.selectedId
            : (events.at(-1)?.event.id ?? null),
      });
      if (!page.has_more) break;
      if (page.next_sequence - 1 <= cursor)
        throw new Error("Event history cursor did not advance");
      cursor = page.next_sequence - 1;
    }
    await this.refresh(generation);
    if (this.current(generation) && reconstruction === this.reconstruction)
      this.set({ rebuilding: false });
  }
  private connect(generation: number) {
    clearInterval(this.timer);
    const info = this.state.info!;
    this.source?.close();
    if (info.state.status === "finished") return;
    this.timer = setInterval(() => {
      void this.refresh(generation);
    }, 1000);
    const source = this.sourceFactory(
      this.api.url(`/sessions/${info.session_id}/stream`),
      this.resumeToken,
    );
    this.source = source;
    const receive = (event: Event) => {
      if (!this.current(generation) || this.source !== source) return;
      try {
        const update = readReplay((event as MessageEvent<string>).data);
        const oldRevision = this.state.info!.state.revision;
        if (
          update.match_id !== this.state.info!.state.match_id ||
          update.revision < oldRevision
        )
          return;
        this.apply(update);
        const token = (event as MessageEvent<string>).lastEventId;
        const parts = token?.split(":");
        if (
          parts?.length === 3 &&
          parts[0] === info.session_id &&
          Number(parts[1]) === update.revision &&
          /^\d+$/.test(parts[2])
        )
          this.resumeToken = token;
        this.set({
          connection: "connected",
          error: "",
          retryAt: null,
          retryAttempt: 0,
        });
        if (update.revision > oldRevision)
          void this.rebuild(generation).catch((error) =>
            this.reconnect(error, generation),
          );
        if (update.status === "finished") {
          source.close();
          clearInterval(this.timer);
          void this.refresh(generation);
        }
      } catch (error) {
        this.reconnect(error, generation);
      }
    };
    source.addEventListener("replay", receive);
    source.addEventListener("reset", receive);
    source.addEventListener("closed", () => {
      if (this.current(generation) && this.source === source) {
        source.close();
        clearInterval(this.timer);
        this.set({
          connection: "closed",
          busy: false,
          error: "",
          retryAt: null,
        });
      }
    });
    source.onerror = (error) => {
      if (this.source === source)
        this.reconnect(error ?? new Error("Stream disconnected"), generation);
    };
  }
  private reconnect(error: unknown, generation: number) {
    if (!this.current(generation)) return;
    if (error instanceof ApiError && error.status === 404) {
      this.failure(error, generation);
      return;
    }
    if (error instanceof ApiError && error.status === 409)
      this.resumeToken = undefined;
    this.source?.close();
    this.source = null;
    clearInterval(this.timer);
    clearTimeout(this.retry);
    const delay = Math.max(
      Math.min(30, 5 * 2 ** Math.min(3, this.state.retryAttempt)),
      error instanceof ApiError ? error.retryAfter : 0,
    );
    this.set({
      retryAt: Date.now() + delay * 1000,
      retryAttempt: this.state.retryAttempt + 1,
      connection: "reconnecting",
      error: error instanceof Error ? error.message : "Stream disconnected",
    });
    this.retry = setTimeout(() => {
      void this.recover(generation);
    }, delay * 1000);
  }
  retryConnection = () => {
    clearTimeout(this.retry);
    void this.recover(this.generation);
  };
  private async recover(generation: number) {
    if (!this.state.info || !this.current(generation) || this.recovering)
      return;
    this.recovering = true;
    this.set({ retryAt: null });
    try {
      const info = await this.get<SessionInfo>(
        `/sessions/${this.state.info.session_id}`,
      );
      if (!this.current(generation)) return;
      this.apply(info.state);
      await this.rebuild(generation);
      if (!this.current(generation)) return;
      this.set({ connection: "connected", error: "" });
      this.connect(generation);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404)
        this.failure(error, generation);
      else this.reconnect(error, generation);
    } finally {
      if (this.current(generation)) this.recovering = false;
    }
  }
  private async refresh(generation: number) {
    if (this.refreshing || !this.current(generation) || !this.state.info)
      return;
    this.refreshing = true;
    const info = this.state.info;
    const revision = info.state.revision;
    const second = Math.floor(info.state.position_seconds);
    try {
      const [metrics, context] = await Promise.all([
        this.get<MetricsResponse>(
          `/sessions/${info.session_id}/metrics?advanced=true&at_second=${second}`,
        ),
        info.scenario === "ashford-demo-v1"
          ? this.get<ApiContext>(`/sessions/${info.session_id}/context`)
          : Promise.resolve(null),
      ]);
      const now = this.state.info?.state;
      if (!this.current(generation) || !now || now.revision !== revision)
        return;
      if (
        metrics.revision === revision &&
        metrics.snapshot.match_id === now.match_id &&
        metrics.at_second <= now.position_seconds
      )
        this.set({ metrics });
      if (
        context &&
        context.revision === revision &&
        context.at_second <= now.position_seconds
      )
        this.set({ context });
    } catch (error) {
      if (!this.current(generation)) return;
      if (error instanceof ApiError && error.status === 404)
        this.failure(error, generation);
      else if (
        error instanceof TypeError ||
        (error instanceof DOMException && error.name === "TimeoutError")
      )
        this.reconnect(error, generation);
      else if (!(
        error instanceof ApiError && [409, 422].includes(error.status)
      ))
        this.set({
          error: error instanceof Error ? error.message : "Metrics unavailable",
        });
    } finally {
      if (this.current(generation)) this.refreshing = false;
    }
  }
  async control(control: Control) {
    if (
      !this.state.info ||
      this.controlPending ||
      this.state.connection !== "connected"
    )
      return;
    this.controlPending = true;
    this.set({ busy: true, error: "" });
    const generation = this.generation;
    try {
      const update = await this.api.control(
        this.state.info.session_id,
        control,
      );
      if (!this.current(generation)) return;
      this.apply(update);
      if (control.action === "seek") await this.rebuild(generation);
    } catch (error) {
      if (this.current(generation)) {
        if (error instanceof ApiError && error.status === 404)
          this.failure(error, generation);
        else
          this.set({
            error: error instanceof Error ? error.message : "Control failed",
          });
      }
    } finally {
      if (this.current(generation)) {
        this.controlPending = false;
        this.set({ busy: false });
      }
    }
  }
  async analyze() {
    if (!this.state.info || this.state.analyzing) return;
    const generation = this.generation;
    const revision = this.state.info.state.revision;
    this.set({ analyzing: true, error: "" });
    try {
      const report = await this.api.analyze(this.state.info.session_id);
      if (
        this.current(generation) &&
        this.state.info?.state.revision === revision
      )
        this.set({ report });
    } catch (error) {
      if (this.current(generation))
        this.set({
          error: error instanceof Error ? error.message : "Analysis failed",
        });
    } finally {
      if (this.current(generation)) this.set({ analyzing: false });
    }
  }
  history = async (
    fixtureId: string,
    signal: AbortSignal,
  ): Promise<HistoricalMatch> => {
    const info = this.state.info;
    if (
      !info ||
      !Object.hasOwn(this.state.context?.historical_patterns ?? {}, fixtureId)
    )
      throw new Error(
        "Historical fixture is not part of this session's evidence",
      );
    const generation = this.generation;
    const revision = info.state.revision;
    const artifact = await this.get<HistoricalArtifact>(
      `/sessions/${info.session_id}/history/${encodeURIComponent(fixtureId)}`,
      signal,
    );
    if (
      !this.current(generation) ||
      this.state.info?.state.revision !== revision ||
      signal.aborted
    )
      throw new Error("Timeline changed; discard historical response");
    if (
      !Array.isArray(artifact.frames) ||
      !artifact.frames.every((frame) => Array.isArray(frame.events))
    )
      throw new Error("Historical artifact has no valid event frames");
    return {
      ...artifact,
      events: artifact.frames.flatMap((frame) => frame.events),
    };
  };
  select = (id: string) => {
    if (this.state.events.some((item) => item.event.id === id)) {
      this.following = false;
      this.set({ selectedId: id });
    }
  };
}

export function metricRows(metrics: MetricsResponse | null, teams: Team[]) {
  return teams.map(
    (team) =>
      Object.fromEntries(
        (
          metrics?.snapshot.teams.find((row) => row.team_id === team.id)
            ?.values ?? []
        ).map((value) => [value.key, value.value]),
      ) as Record<string, number>,
  );
}
export function visibleLiveEvents(state: LiveState): MatchEvent[] {
  return state.events
    .map((item) => item.event)
    .filter(
      (event) => timeOf(event) <= (state.info?.state.position_seconds ?? 0),
    );
}
