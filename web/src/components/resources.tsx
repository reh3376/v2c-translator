"use client";

import { motion, useReducedMotion } from "motion/react";
import { CRISIS_LINE, RESOURCE_GROUPS } from "@/content/resources";
import { item, pressable, stagger } from "./motion";

/**
 * Where to go next: records, work, benefits, and the crisis line.
 *
 * Every link leaves this page, so each opens in a new tab and says so to a screen reader. The
 * addresses carry no query string, so nobody can tell from them that the reader came from here.
 */
export function Resources() {
  const reduced = useReducedMotion() ?? false;

  return (
    <section className="resources" aria-labelledby="resources-heading">
      <h2 id="resources-heading">Resources for veterans</h2>
      <p className="resources-lede">
        These sites are run by other people. Opening one leaves this page; your documents stay on this computer.
      </p>

      <div className="resource-groups">
        {RESOURCE_GROUPS.map((group) => (
          <section key={group.heading} aria-labelledby={`resources-${slug(group.heading)}`}>
            <h3 id={`resources-${slug(group.heading)}`}>{group.heading}</h3>
            <motion.ul className="resource-list" {...stagger(reduced)}>
              {group.links.map((link) => (
                <motion.li key={link.href} {...item(reduced)}>
                  <motion.a href={link.href} target="_blank" rel="noopener noreferrer" {...pressable(reduced)}>
                    {link.title}
                    <span className="visually-hidden"> (opens in a new tab)</span>
                  </motion.a>
                  <span className="resource-blurb">{link.blurb}</span>
                </motion.li>
              ))}
            </motion.ul>
          </section>
        ))}
      </div>

      <section className="crisis" aria-labelledby="crisis-heading">
        <h3 id="crisis-heading">Veterans Crisis Line</h3>
        <p>
          Dial <strong>{CRISIS_LINE.dial}</strong>, then press <strong>{CRISIS_LINE.press}</strong>. Or text{" "}
          <strong>{CRISIS_LINE.text}</strong>. Responders are there every hour of every day, for veterans, service
          members and their families. You do not need to be enrolled in VA benefits or health care.
        </p>
        <p>
          <a href={CRISIS_LINE.href} target="_blank" rel="noopener noreferrer">
            Chat online at {CRISIS_LINE.site}
            <span className="visually-hidden"> (opens in a new tab)</span>
          </a>
        </p>
      </section>
    </section>
  );
}

const slug = (heading: string) => heading.toLowerCase().replace(/[^a-z]+/g, "-");
