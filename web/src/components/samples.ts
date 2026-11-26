import { asset } from "@/base-path";

/** Synthetic records for one fictional soldier, copied from the repository's tests/fixtures. */
export const SAMPLES = [
  { name: "army_2000.txt", type: "text/plain" },
  { name: "army_2000_dd215.json", type: "application/json" },
  { name: "army_vmet.txt", type: "text/plain" },
] as const;

export async function loadSamples(): Promise<File[]> {
  return Promise.all(
    SAMPLES.map(async ({ name, type }) => {
      const path = asset(`/samples/${name}`);
      const response = await fetch(path);
      if (!response.ok) throw new Error(`${path}: HTTP ${response.status}`);
      return new File([await response.blob()], name, { type });
    }),
  );
}
