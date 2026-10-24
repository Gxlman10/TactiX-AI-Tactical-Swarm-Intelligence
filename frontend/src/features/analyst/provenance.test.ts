import { expect, it } from "vitest";
import { provenanceLabel, sentenceParts } from "./provenance";

it("splits a narrative into inspectable sentences", () => {
  expect(sentenceParts("The press shifted. The goal followed!")).toEqual([
    "The press shifted.",
    "The goal followed!",
  ]);
});

it("resolves unique contributing agents and ignores unknown findings", () => {
  const findings = [
    { id: "a1", agent: "analyst" as const, claim: "pressure" },
    { id: "h1", agent: "historian" as const, claim: "pattern" },
  ];
  expect(provenanceLabel(["a1", "h1", "missing", "a1"], findings)).toEqual([
    "analyst",
    "historian",
  ]);
});
