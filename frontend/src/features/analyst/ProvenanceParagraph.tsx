import { useTranslation } from "react-i18next";
import {
  provenanceLabel,
  sentenceParts,
  type NarrativeFinding,
  type NarrativeMoment,
} from "./provenance";

export function ProvenanceParagraph({
  moments,
  findings,
}: {
  moments: NarrativeMoment[];
  findings: NarrativeFinding[];
}) {
  const { t } = useTranslation();
  if (!moments.length) return null;
  return (
    <section className="provenance-paragraph panel" aria-label={t("provenanceTitle")}>
      <div className="panel-heading">
        <div>
          <span className="section-tag">{t("provenanceTag")}</span>
          <h2>{t("provenanceTitle")}</h2>
        </div>
        <small>{t("provenanceHint")}</small>
      </div>
      <p className="provenance-copy">
        {moments.flatMap((moment) =>
          sentenceParts(moment.text).map((sentence, index) => {
            const agents = provenanceLabel(moment.source_finding_ids, findings);
            return (
              <span
                className="provenance-sentence"
                key={`${moment.minute}:${index}:${sentence}`}
                tabIndex={0}
                title={
                  agents.length
                    ? agents.map((agent) => t(`agent_${agent}`)).join(" · ")
                    : t("provenanceUnavailable")
                }
              >
                {sentence}{" "}
                <small aria-hidden="true">
                  {agents.length
                    ? agents.map((agent) => t(`agent_${agent}`)).join(" + ")
                    : "?"}
                </small>
              </span>
            );
          }),
        )}
      </p>
    </section>
  );
}
