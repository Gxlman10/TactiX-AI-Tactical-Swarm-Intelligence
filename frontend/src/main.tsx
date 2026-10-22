import { Component, StrictMode, Suspense, type ReactNode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/manrope";
import i18n from "./i18n";
import "./styles.css";
import App from "./App";
class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="not-found">
        <h1>{i18n.t("error")}</h1>
        <button onClick={() => window.location.reload()}>
          {i18n.t("reload")}
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <Suspense
        fallback={
          <div className="loading-shell" aria-busy="true">
            {i18n.t("loading")}
          </div>
        }
      >
        <App />
      </Suspense>
    </ErrorBoundary>
  </StrictMode>,
);
