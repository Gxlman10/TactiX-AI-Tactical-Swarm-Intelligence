export interface NarrativeMoment {
  minute: number;
  text: string;
  source_finding_ids: string[];
}

export interface NarrativeFinding {
  id: string;
  agent: "analyst" | "historian";
  claim: string;
}

export function sentenceParts(text: string) {
  return text.match(/[^.!?]+[.!?]+|[^.!?]+$/g)?.map((part) => part.trim()).filter(Boolean) ?? [];
}

export function provenanceLabel(
  ids: string[],
  findings: NarrativeFinding[],
) {
  const agents = [...new Set(
    ids
      .map((id) => findings.find((finding) => finding.id === id)?.agent)
      .filter((agent): agent is NarrativeFinding["agent"] => Boolean(agent)),
  )];
  return agents;
}
