import { useState } from "react";
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
    <section className="connection-panel" aria-label={t("connection")}>
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
          disabled={data?.busy || data?.connection === "connected"}
          onClick={controller?.retryConnection}
        >
          {t("reconnect")}
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
