/**
 * The path the app is served under.
 *
 * Local development serves the app at `/` on port 3009 and this is the empty string.
 * The hosted container is built with `V2C_BASE_PATH=/v2c`, because that is where the
 * career site publishes it.
 *
 * This one value is baked into the build, unlike everything in `server/config.ts`.
 * Next.js resolves `basePath` while it writes the client manifests and the router's
 * route table, so it is a property of the build and cannot be moved at boot.
 * `next.config.ts` passes the same string through its `env` block, which textually
 * replaces `process.env.V2C_BASE_PATH` in the server and the client bundle alike, so
 * both halves of the app agree without the container having to set the variable again.
 *
 * Use `asset()` for every path this code hands to the browser itself: a `fetch`, an
 * `<Image src>` that is `unoptimized` (Next's own basePath handling covers the
 * optimizer's URLs, not a raw src), a download, a sample file. Paths inside `href` on a
 * `next/link` are rewritten by the router and need nothing.
 */

export const BASE_PATH: string = process.env.V2C_BASE_PATH ?? "";

/** A path under `public/`, or an API route, as the browser must ask for it. */
export function asset(rooted: string): string {
  return `${BASE_PATH}${rooted}`;
}
