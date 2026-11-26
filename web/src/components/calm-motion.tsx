"use client";

import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";

/**
 * Motion's settings for the whole page. `reducedMotion="user"` drops transform animations for
 * anyone whose system asks for less motion, and keeps opacity, so nothing on the page depends on
 * movement to be understood.
 */
export function CalmMotion({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user">{children}</MotionConfig>;
}
