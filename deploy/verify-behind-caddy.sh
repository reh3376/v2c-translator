#!/usr/bin/env bash
# Run the hosted image behind a Caddy configured like the career site's, and check it
# with a real browser.
#
#   deploy/verify-behind-caddy.sh v2c:local
#   deploy/verify-behind-caddy.sh ghcr.io/reh3376/v2c-translator:main
#
# Why this exists, and why it is not in CI: the career site's Caddy sends its own
# Content-Security-Policy, and whether this app's policy survives that depends on how the
# proxy is configured. The failure mode is silent either way. Turnstile's iframe renders
# as an empty box, no error appears anywhere, and the first person to notice is a veteran
# whose upload is refused. Reading the two policies side by side does not tell you what a
# browser does with them; loading the page in one does.
#
# It runs both arrangements:
#
#   behind-caddy/Caddyfile                  the site's policy scoped away from /v2c, so
#                                           this app's own policy reaches the browser.
#                                           This is what docs/deploy.md asks for.
#   behind-caddy/Caddyfile.site-policy-only the site's policy left site-wide. Caddy's
#                                           `header` replaces rather than appends, so the
#                                           app's policy is discarded and the site's is
#                                           the only one in force.
#
# Both have to pass. The second one passing is what says the career site is not broken on
# the day it adds a plain reverse_proxy and nothing else.
#
# Needs Docker, Docker Compose, the Chrome web/ already uses for its end-to-end tests,
# and a route to challenges.cloudflare.com.
set -euo pipefail

IMAGE="${1:?usage: verify-behind-caddy.sh IMAGE}"
REPO_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RIG="${REPO_DIR}/deploy/behind-caddy"
URL="http://127.0.0.1:8080"

export V2C_IMAGE="$IMAGE"

down() { docker compose -f "${RIG}/docker-compose.yml" down -v --remove-orphans >/dev/null 2>&1 || true; }
trap down EXIT

run_variant() {
    local caddyfile="$1" expect_policies="$2" expect_owner="$3"

    printf '\n======== %s\n' "$caddyfile"
    down
    V2C_CADDYFILE="./${caddyfile}" docker compose -f "${RIG}/docker-compose.yml" up -d --wait

    printf '\n== which policy reaches the browser\n'
    local headers count
    headers=$(curl -fsSI "${URL}/v2c")
    count=$(grep -ci '^content-security-policy:' <<<"$headers" || true)
    [ "$count" = "$expect_policies" ] || {
        echo "expected ${expect_policies} policy header(s), got ${count}" >&2
        grep -i '^content-security-policy:' <<<"$headers" >&2
        return 1
    }
    # The app's policy names no host but Cloudflare's; the site's also names GitHub's.
    if [ "$expect_owner" = app ]; then
        grep -i '^content-security-policy:' <<<"$headers" | grep -q "api.github.com" \
            && { echo "the site's policy is still being sent for /v2c" >&2; return 1; }
        echo "ok: one policy, and it is the app's"
    else
        grep -i '^content-security-policy:' <<<"$headers" | grep -q "api.github.com" \
            || { echo "expected the site's policy here" >&2; return 1; }
        echo "ok: one policy, and it is the site's"
    fi

    printf '\n== the page, in a browser, under it\n'
    (cd "${REPO_DIR}/web" && V2C_RIG_URL="$URL" pnpm exec playwright test --config playwright.behind-caddy.config.ts)
}

run_variant Caddyfile 1 app
run_variant Caddyfile.site-policy-only 1 site

printf '\nBEHIND-CADDY OK (both arrangements)\n'
