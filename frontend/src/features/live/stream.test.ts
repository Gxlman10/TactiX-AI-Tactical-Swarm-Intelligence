import { expect, it, vi } from "vitest";
import { ApiError } from "./api";
import { ReplayStream } from "./stream";

function response(chunks: string[]) {
  return new Response(
    new ReadableStream({
      start(controller) {
        for (const chunk of chunks)
          controller.enqueue(new TextEncoder().encode(chunk));
        controller.close();
      },
    }),
    { headers: { "Content-Type": "text/event-stream; charset=utf-8" } },
  );
}

it("resumes with Last-Event-ID and parses chunked CRLF, comments and multiline data", async () => {
  const fetcher = vi
    .fn<typeof fetch>()
    .mockResolvedValue(
      response([
        ": heartbeat\r\nevent: replay\r",
        "\nid: session:2:8\r\ndata: first\r\n",
        "data: second\r\n\r",
        "\nevent: reset\ndata: third\n\n",
      ]),
    );
  const stream = new ReplayStream(
    "https://test/stream",
    "session:2:7",
    fetcher,
  );
  const events: MessageEvent[] = [];
  stream.addEventListener("replay", (event) =>
    events.push(event as MessageEvent),
  );
  stream.addEventListener("reset", (event) =>
    events.push(event as MessageEvent),
  );
  await new Promise<void>((resolve) => {
    stream.onerror = () => resolve();
  });
  expect(fetcher.mock.calls[0][1]?.headers).toMatchObject({
    "Last-Event-ID": "session:2:7",
  });
  expect(events.map((e) => [e.type, e.data, e.lastEventId])).toEqual([
    ["replay", "first\nsecond", "session:2:8"],
    ["reset", "third", "session:2:8"],
  ]);
});

it.each([404, 409, 503])(
  "preserves HTTP %i and server retry hints",
  async (status) => {
    const stream = new ReplayStream(
      "https://test/stream",
      undefined,
      vi
        .fn<typeof fetch>()
        .mockResolvedValue(
          new Response(null, { status, headers: { "Retry-After": "12" } }),
        ),
    );
    const error = await new Promise<unknown>((resolve) => {
      stream.onerror = resolve;
    });
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status, retryAfter: 12 });
  },
);

it("honors SSE retry and never dispatches an unterminated frame on EOF", async () => {
  const stream = new ReplayStream(
    "https://test/stream",
    undefined,
    vi
      .fn<typeof fetch>()
      .mockResolvedValue(
        response(["retry: 14000\nevent: replay\ndata: incomplete"]),
      ),
  );
  const listener = vi.fn();
  stream.addEventListener("replay", listener);
  const error = await new Promise<unknown>((resolve) => {
    stream.onerror = resolve;
  });
  expect(listener).not.toHaveBeenCalled();
  expect(error).toMatchObject({ retryAfter: 14 });
});

it("aborts pending reads without triggering reconnect after disposal", async () => {
  let signal: AbortSignal | undefined;
  const fetcher: typeof fetch = async (_url, options) => {
    signal = options?.signal as AbortSignal;
    return new Promise((_resolve, reject) =>
      signal!.addEventListener("abort", () => reject(new Error("aborted"))),
    );
  };
  const stream = new ReplayStream("https://test/stream", undefined, fetcher);
  const listener = vi.fn();
  stream.onerror = listener;
  stream.close();
  await Promise.resolve();
  expect(signal?.aborted).toBe(true);
  expect(listener).not.toHaveBeenCalled();
});

it("rejects HTML responses instead of treating a proxy page as a live stream", async () => {
  const stream = new ReplayStream(
    "https://test/stream",
    undefined,
    vi
      .fn<typeof fetch>()
      .mockResolvedValue(new Response("<html>offline</html>")),
  );
  const error = await new Promise<unknown>((resolve) => {
    stream.onerror = resolve;
  });
  expect(String(error)).toContain("did not return an event stream");
});
