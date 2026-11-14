import type { CompactPart } from "./compactModule";

/**
 * Summary line of the one compact Waivers header module: "394 available · $81 FAAB · Need QB". Everything the old
 * header said (explainer, stat tiles, needs sentence, helper copy) sits in the module body, one tap away.
 * Twin of web-next/src/lib/waiversHeader.ts.
 */
export function waiversHeaderParts(input: { available: number | null | undefined; faabLabel: string; faab: string; need: string }): CompactPart[] {
  const parts: CompactPart[] = [];
  if (input.available != null) parts.push({ key: "available", text: `${input.available} available` });
  if (input.faab && input.faab !== "—") parts.push({ key: "faab", text: `${input.faab} ${input.faabLabel}`.trim() });
  if (input.need && input.need !== "—") {
    const covered = /^covered$/i.test(input.need);
    parts.push({ key: "need", text: covered ? "Needs covered" : `Need ${input.need}`, tone: covered ? "success" : "warning", strong: !covered });
  }
  return parts;
}
