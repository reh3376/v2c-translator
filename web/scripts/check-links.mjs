/**
 * Visits every address in `src/content/resources.ts` and fails on a dead one.
 *
 * Run it by hand, or let the weekly `Link check` workflow run it. It is deliberately not part of
 * pull-request CI: these sites belong to other people, and a pull request should not fail because
 * one of them is having a bad morning.
 *
 *   node scripts/check-links.mjs
 *
 * Two answers fail the run:
 *
 *   dead        404 or 410, or nothing answered at all. The page has gone.
 *   unavailable 5xx twice in a row. The site is broken, or something between here and it is.
 *
 * Three answers are reported and tolerated, because each says more about the checker than about
 * the link:
 *
 *   blocked     403, 405 or 429. Several federal sites refuse anything that is not a browser.
 *   redirected  the address works but now points elsewhere. Worth following up by hand.
 *   tls         the certificate did not verify. DoD sites are signed by the DoD's own authority,
 *               which is not in a public trust store. Verification is never switched off here.
 */

import { ALL_LINKS } from "../src/content/resources.ts";

const TIMEOUT_MS = 25_000;

/** Several .gov sites answer 403 to anything that does not look like a browser. */
const USER_AGENT =
  "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const DEAD = "dead";
const UNAVAILABLE = "unavailable";
const FATAL = [DEAD, UNAVAILABLE];

const pause = (ms) => new Promise((done) => setTimeout(done, ms));

async function attempt(href) {
  for (const method of ["HEAD", "GET"]) {
    const stop = AbortSignal.timeout(TIMEOUT_MS);
    let response;
    try {
      response = await fetch(href, {
        method,
        redirect: "follow",
        signal: stop,
        headers: { "user-agent": USER_AGENT, accept: "text/html,*/*" },
      });
    } catch (error) {
      const code = error?.cause?.code ?? error?.code ?? "";
      if (/CERT|SSL|SELF_SIGNED|UNABLE_TO_VERIFY/i.test(code)) {
        return { state: "tls", detail: code };
      }
      if (method === "GET") return { state: DEAD, detail: code || String(error?.message ?? error) };
      continue; // some servers reject HEAD outright; try GET
    }

    const { status, url } = response;
    if (status === 404 || status === 410) {
      if (method === "HEAD") continue;
      return { state: DEAD, detail: `HTTP ${status}` };
    }
    if (status >= 500) {
      if (method === "HEAD") continue;
      return { state: UNAVAILABLE, detail: `HTTP ${status}` };
    }
    if (status === 403 || status === 405 || status === 429) {
      if (method === "HEAD") continue;
      return { state: "blocked", detail: `HTTP ${status}` };
    }
    if (url !== href) return { state: "redirected", detail: `now ${url}` };
    return { state: "ok", detail: `HTTP ${status}` };
  }
  return { state: DEAD, detail: "no answer" };
}

/** A site that is merely having a bad minute gets a second chance before it fails the run. */
async function visit(href) {
  const first = await attempt(href);
  if (first.state !== UNAVAILABLE) return first;
  await pause(3000);
  return attempt(href);
}

const results = await Promise.all(ALL_LINKS.map(async (href) => ({ href, ...(await visit(href)) })));

const width = Math.max(...results.map((result) => result.href.length));
for (const { href, state, detail } of results) {
  const label = FATAL.includes(state) ? state.toUpperCase() : state;
  console.log(`${label.padEnd(12)} ${href.padEnd(width)}  ${detail}`);
}

const broken = results.filter((result) => FATAL.includes(result.state));
console.log(`\n${results.length} links, ${broken.length} broken.`);
if (broken.length > 0) {
  console.error("Fix or replace them in web/src/content/resources.ts.");
  process.exitCode = 1;
}
