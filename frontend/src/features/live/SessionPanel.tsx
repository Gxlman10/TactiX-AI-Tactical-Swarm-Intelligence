import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { type LiveState, type LiveSession } from "./session";
import { useStudio, type Language } from "../preferences/store";

export function SessionPanel(props: {
  local?: boolean;
  onConnect?: () => void;
  data?: LiveState;
  controller?: LiveSession;
  onLocal?: () => void;
}) {
  const { t } = useTranslation();
  const [joinId, setJoinId] = useState("");
  const preferences = useStudio();
  const { data, controller } = props;
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!data?.retryAt) return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [data?.retryAt]);
  if (props.local)
    return (
      <section className="connection-panel">
        <strong>{t("rehearsal")}</strong>
        <button onClick={props.onConnect}>{t("useServer")}</button>
      </section>
    );
  const start = () => {
    void controller!.start();
  };
  const initial = !data?.info || !data.teams.length;
  return (
    <section
      className="connection-panel"
      aria-label={t("connection")}
      aria-busy={data?.connection === "connecting" || data?.rebuilding}
    >
      <div className="connection-copy">
        <strong role="status">
          {t(
            data?.rebuilding && data.connection === "connected"
              ? "loadingHistory"
              : `connection_${data?.connection ?? "idle"}`,
          )}
        </strong>
        {data?.info ? (
          <code>{data.info.session_id}</code>
        ) : (
          <p>{t("connectDescription")}</p>
        )}
        {data?.connection === "reconnecting" && (
          <p className="recovery-hint" role="status">
            {data.retryAt
              ? t("retryScheduled", {
                  seconds: Math.max(0, Math.ceil((data.retryAt - now) / 1000)),
                  attempt: data.retryAttempt,
                })
              : t("recoveringHistory")}
          </p>
        )}
        {data?.connection === "closed" && <p>{t("sessionEndedHint")}</p>}
        {data?.error && (
          <p role="alert">
            {t("requestError")} {data.error}
          </p>
        )}
      </div>
      {initial && (
        <label>
          {t("language")}
          <select
            aria-label={t("language")}
            value={preferences.language}
            onChange={(event) =>
              preferences.setLanguage(event.target.value as Language)
            }
          >
            <option value="en">EN</option>
            <option value="es">ES</option>
          </select>
        </label>
      )}
      {initial || data?.connection === "closed" ? (
        <button disabled={data?.busy} onClick={start}>
          {t("createSession")}
        </button>
      ) : (
        <button
          disabled={
            data?.busy ||
            data?.connection === "connected" ||
            (data?.connection === "reconnecting" && !data.retryAt)
          }
          onClick={controller?.retryConnection}
        >
          {t("reconnect")}
        </button>
      )}
      {data?.connection === "connected" && (
        <button
          disabled={data.analyzing}
          onClick={() => void controller!.analyze()}
        >
          {t(data.analyzing ? "analyzing" : "analyzeMatch")}
        </button>
      )}
      {initial && (
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void controller!.start(joinId.trim());
          }}
        >
          <label>
            {t("sessionId")}
            <input
              required
              pattern="[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}"
              value={joinId}
              onChange={(event) => setJoinId(event.target.value)}
            />
          </label>
          <button disabled={data?.busy || !joinId.trim()}>
            {t("joinSession")}
          </button>
        </form>
      )}
      <button onClick={props.onLocal}>{t("useLocal")}</button>
      <small>{t("serverHint")}</small>
    </section>
  );
}
