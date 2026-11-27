"use client";

import Image from "next/image";
import {
  motion,
  useMotionValue,
  useReducedMotion,
  useScroll,
  useSpring,
  useTransform,
  type MotionValue,
} from "motion/react";
import { useEffect, useRef, useState, type PointerEvent } from "react";
import { asset } from "@/base-path";
import {
  actorArt,
  BRANCH_PANELS,
  panelFor,
  planeArt,
  PLANES,
  type BranchPanel,
  type Layer,
  type Plane,
} from "@/content/branches";
import { lengthOf, VIGNETTES, type Beat } from "@/content/vignettes";
import { PARALLAX, pressable, vignette } from "./motion";
import { useAnimated } from "./use-animated";

/**
 * The six branch pictures, side by side on a wide screen as one scene from sea level to orbit.
 *
 * Each picture is three drawn planes stacked back to front. They move at slightly different
 * rates as the band passes up the window, and lean a little under the pointer, and that
 * difference is what reads as depth. The planes are cut from one drawing by
 * `scripts/dark-art.mjs`, so the resting composition is exactly the picture as it was drawn.
 *
 * Each picture is also a button. Pressing it plays that branch's vignette once: a salute, a
 * boarding, a dismount, a flyover, a sweep of a map. Nothing plays on its own, nothing loops,
 * and the scene always settles back to the resting picture.
 *
 * Once a report names a branch, that picture is marked and the rest step back, so the band stops
 * being scenery and starts reporting what the documents said.
 */
export function BranchBand({ detected }: { detected?: string | null }) {
  const strip = useRef<HTMLUListElement>(null);
  const found = panelFor(detected);

  // One scroll subscription for the whole band: 0 as it comes up from below, 1 as it leaves above.
  const { scrollYProgress } = useScroll({ target: strip, offset: ["start end", "end start"] });

  return (
    <section className="band" aria-labelledby="band-heading">
      <h2 id="band-heading" className="visually-hidden">
        The six services
      </h2>
      <ul className="band-strip" ref={strip}>
        {BRANCH_PANELS.map((panel) => (
          <Panel
            key={panel.name}
            panel={panel}
            pass={scrollYProgress}
            marked={found?.name === panel.name}
            dimmed={Boolean(found)}
          />
        ))}
      </ul>
      <p className="band-caption">
        {found ? (
          <>
            Your documents name the <strong>{found.name}</strong>. The pictures are drawn for this page, sea level to
            orbit, and carry no service seal, emblem or logo. Press one to watch its scene.
          </>
        ) : (
          <>
            Drawn for this page, sea level to orbit. No service seal, emblem or logo is used. Press one to watch its
            scene.
          </>
        )}
      </p>
    </section>
  );
}

function Panel({
  panel,
  pass,
  marked,
  dimmed,
}: {
  panel: BranchPanel;
  pass: MotionValue<number>;
  marked: boolean;
  dimmed: boolean;
}) {
  const reduced = useReducedMotion() ?? false;
  const moving = useAnimated() && !reduced;
  const scene = VIGNETTES[panel.name];

  // Mounted on the first hover, focus or press, so the actor drawings are fetched before they are
  // wanted and the first play has nothing to wait for.
  const [armed, setArmed] = useState(false);
  const [run, setRun] = useState(0);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!playing) return;
    const done = setTimeout(() => setPlaying(false), lengthOf(scene) * 1000);
    return () => clearTimeout(done);
  }, [playing, run, scene]);

  function play() {
    setArmed(true);
    setRun((taken) => taken + 1);
    setPlaying(true);
  }

  // Where the pointer is across the picture, -1 to 1. Sprung, so taking the pointer away settles
  // the planes back rather than snapping them, and parked in the middle when there is no pointer.
  const pointer = useMotionValue(0);
  const lean = useSpring(pointer, { stiffness: 130, damping: 18, mass: 0.4 });

  function onPointerMove(event: PointerEvent<HTMLButtonElement>) {
    if (!moving || event.pointerType !== "mouse") return;
    const box = event.currentTarget.getBoundingClientRect();
    pointer.set(((event.clientX - box.left) / box.width) * 2 - 1);
  }

  return (
    <li className="band-panel" data-marked={marked || undefined} data-dimmed={(dimmed && !marked) || undefined}>
      <figure>
        <motion.button
          type="button"
          className="band-stage"
          aria-label={`Play the ${panel.name} scene`}
          data-state={playing ? "playing" : "rest"}
          onClick={play}
          onPointerEnter={() => setArmed(true)}
          onFocus={() => setArmed(true)}
          onPointerMove={onPointerMove}
          onPointerLeave={() => pointer.set(0)}
          {...pressable(reduced)}
        >
          {/* The planes carry the description between them, so it is read once. Each plane and
              each actor is in the markup twice, as a day and a night drawing, and the stylesheet
              shows one: `data-theme` is on `<html>` before the first paint, so no drawing is
              ever seen in the wrong theme, and the hidden one leaves the accessibility tree with
              it. A photograph, where one has been dropped in, replaces the lot. */}
          <span className="band-art" role="img" aria-label={panel.alt}>
            {panel.photo ? (
              <span className="plane">
                <Image src={asset(panel.photo.src)} alt="" width={480} height={320} unoptimized />
              </span>
            ) : (
              PLANES.map((plane) => (
                <Drawing key={plane} art={planeArt(panel, plane)} plane={plane} pass={pass} lean={lean} moving={moving} />
              ))
            )}
            {armed
              ? scene.beats.map((beat) => (
                  <Actor
                    key={`${beat.actor}-${run}`}
                    art={actorArt(panel, beat.actor)}
                    beat={beat}
                    playing={playing}
                    reduced={reduced}
                  />
                ))
              : null}
          </span>
        </motion.button>
        <figcaption>
          <span className="band-name">{panel.name}</span>
          <span className="band-setting">{marked ? "From your documents" : panel.setting}</span>
          {panel.photo ? <span className="band-credit">{panel.photo.credit}</span> : null}
        </figcaption>
      </figure>
    </li>
  );
}

/** One plane of the resting picture. With motion off it carries no transform at all. */
function Drawing({
  art,
  plane,
  pass,
  lean,
  moving,
}: {
  art: Layer;
  plane: Plane;
  pass: MotionValue<number>;
  lean: MotionValue<number>;
  moving: boolean;
}) {
  const rate = PARALLAX[plane];
  const y = useTransform(pass, [0, 1], [rate.scroll / 2, -rate.scroll / 2]);
  const x = useTransform(lean, [-1, 1], [-rate.pointer, rate.pointer]);

  return (
    <motion.span className="plane" data-plane={plane} style={moving ? { x, y } : undefined}>
      <Pair art={art} />
    </motion.span>
  );
}

/** One actor in a vignette: invisible at rest, played once on a press. */
function Actor({ art, beat, playing, reduced }: { art: Layer; beat: Beat; playing: boolean; reduced: boolean }) {
  return (
    <motion.span
      className="plane actor"
      data-actor={beat.actor}
      style={{ transformOrigin: beat.origin, opacity: playing ? undefined : 0 }}
      {...(playing ? vignette(reduced, beat) : {})}
    >
      <Pair art={art} />
    </motion.span>
  );
}

/**
 * The same drawing twice: by day and after dark. The stylesheet shows one.
 *
 * `asset()` because these are `unoptimized`. Next.js rewrites the URL it hands its own
 * image optimizer to sit under `basePath`, but an unoptimized image is served as the src
 * says, so under `/v2c` a bare `/branches/...` is a 404. `e2e/base-path.spec.ts` loads
 * the page under a base path and fails on any request that 404s, which is how that was
 * found and how it stays found.
 */
function Pair({ art }: { art: Layer }) {
  return (
    <>
      <Image className="art-day" src={asset(art.day)} alt="" width={480} height={320} unoptimized />
      <Image className="art-night" src={asset(art.night)} alt="" width={480} height={320} unoptimized />
    </>
  );
}
