import { ApiError } from "./api";

export interface ReplaySource {
  close(): void;
  addEventListener(type: string, listener: EventListener): void;
  onerror: ((error?: unknown) => void) | null;
}

/** One SSE connection. LiveSession owns retry and revision reconciliation. */
export class ReplayStream extends EventTarget implements ReplaySource {
  onerror: ((error?: unknown) => void) | null = null;
  private abort = new AbortController();
  constructor(
    url: string,
    lastEventId?: string,
    fetcher: typeof fetch = fetch,
  ) {
    super();
    void this.read(url, lastEventId, fetcher);
  }
  close() {
    this.abort.abort();
  }
  private async read(
    url: string,
    lastEventId: string | undefined,
    fetcher: typeof fetch,
  ) {
    let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
    let retrySeconds = 5;
    try {
      const response = await fetcher(url, {
        signal: this.abort.signal,
        headers: {
          Accept: "text/event-stream",
          ...(lastEventId ? { "Last-Event-ID": lastEventId } : {}),
        },
      });
      if (!response.ok)
        throw new ApiError(
          response.status,
          `Stream HTTP ${response.status}`,
          Number(response.headers.get("Retry-After")) || 5,
        );
      if (
        !response.headers.get("Content-Type")?.includes("text/event-stream") ||
        !response.body
      )
        throw new Error("Server did not return an event stream");
      reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "",
        eventType = "message",
        eventId = lastEventId ?? "",
        data: string[] = [];
      const line = (value: string) => {
        if (!value) {
          if (data.length)
            this.dispatchEvent(
              new MessageEvent(eventType, {
                data: data.join("\n"),
                lastEventId: eventId,
              }),
            );
          data = [];
          eventType = "message";
          return;
        }
        if (value.startsWith(":")) return;
        const colon = value.indexOf(":");
        const field = colon < 0 ? value : value.slice(0, colon);
        const content =
          colon < 0 ? "" : value.slice(colon + 1).replace(/^ /, "");
        if (field === "data") data.push(content);
        if (field === "event") eventType = content || "message";
        if (field === "id" && !content.includes("\0")) eventId = content;
        if (field === "retry" && /^\d+$/.test(content))
          retrySeconds = Math.max(5, Number(content) / 1000);
      };
      while (!this.abort.signal.aborted) {
        const chunk = await reader.read();
        if (chunk.done)
          throw new ApiError(0, "Stream disconnected", retrySeconds);
        buffer += decoder.decode(chunk.value, { stream: true });
        if (buffer.length + data.join("").length > 1024 * 1024)
          throw new Error("Stream frame exceeds the supported size");
        let end: number;
        while ((end = buffer.search(/[\r\n]/)) >= 0) {
          if (buffer[end] === "\r" && end === buffer.length - 1) break;
          const width = buffer.slice(end, end + 2) === "\r\n" ? 2 : 1;
          const value = buffer.slice(0, end);
          buffer = buffer.slice(end + width);
          if (this.abort.signal.aborted) return;
          line(value);
        }
      }
    } catch (error) {
      if (!this.abort.signal.aborted) this.onerror?.(error);
    } finally {
      await reader?.cancel().catch(() => undefined);
    }
  }
}
