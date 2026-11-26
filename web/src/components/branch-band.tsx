"use client";

import Image from "next/image";
import { motion, useReducedMotion } from "motion/react";
import { BRANCH_PANELS, panelFor, type BranchPanel } from "@/content/branches";
import { item, lift, stagger } from "./motion";

/**
 * The six branch pictures, side by side on a wide screen as one scene from sea level to orbit.
 * Once a report names a branch, that picture is marked and the rest step back, so the band stops
 * being scenery and starts reporting what the documents said.
 */
export function BranchBand({ detected }: { detected?: string | null }) {
  const reduced = useReducedMotion() ?? false;
  const found = panelFor(detected);

  return (
    <section className="band" aria-labelledby="band-heading">
      <h2 id="band-heading" className="visually-hidden">
        The six services
      </h2>
      <motion.ul className="band-strip" {...stagger(reduced, 0.04)}>
        {BRANCH_PANELS.map((panel) => (
          <Panel key={panel.name} panel={panel} marked={found?.name === panel.name} dimmed={Boolean(found)} />
        ))}
      </motion.ul>
      <p className="band-caption">
        {found ? (
          <>
            Your documents name the <strong>{found.name}</strong>. The pictures are drawn for this page, sea level to
            orbit, and carry no service seal, emblem or logo.
          </>
        ) : (
          <>Drawn for this page, sea level to orbit. No service seal, emblem or logo is used.</>
        )}
      </p>
    </section>
  );
}

function Panel({ panel, marked, dimmed }: { panel: BranchPanel; marked: boolean; dimmed: boolean }) {
  const reduced = useReducedMotion() ?? false;

  return (
    <motion.li
      className="band-panel"
      data-marked={marked || undefined}
      data-dimmed={(dimmed && !marked) || undefined}
      {...item(reduced)}
    >
      <motion.figure {...lift(reduced)}>
        {/* Hand-drawn SVGs and any photograph dropped in beside them are served as they are: the
            image optimizer refuses SVG by default, and there is nothing here worth re-encoding.

            Both the day and the night drawing are in the markup, and the stylesheet hides one.
            That way the right one is painted before React runs, and the hidden one leaves the
            accessibility tree with it, so the description is read exactly once either way. */}
        {panel.photo ? (
          <Image src={panel.photo.src} alt={panel.alt} width={480} height={320} unoptimized />
        ) : (
          <>
            <Image className="art-day" src={panel.illustration} alt={panel.alt} width={480} height={320} unoptimized />
            <Image
              className="art-night"
              src={panel.illustrationDark}
              alt={panel.alt}
              width={480}
              height={320}
              unoptimized
            />
          </>
        )}
        <figcaption>
          <span className="band-name">{panel.name}</span>
          <span className="band-setting">{marked ? "From your documents" : panel.setting}</span>
          {panel.photo ? <span className="band-credit">{panel.photo.credit}</span> : null}
        </figcaption>
      </motion.figure>
    </motion.li>
  );
}
