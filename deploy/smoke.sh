#!/usr/bin/env bash
# Run the built image the way production will and check that it works.
#
#   deploy/smoke.sh ghcr.io/reh3376/v2c-translator:abc123 [--scan path/to/scan.pdf]
#
# What it asserts, in order:
#
#   1. hosted mode refuses to boot without TURNSTILE_SECRET_KEY
#   2. local mode listens on loopback only, so the container is not reachable
#   3. hosted mode, read-only root filesystem, tmpfs for uploads: healthz, readyz, page
#   4. the page carries the hosted privacy copy and not the local claim
#   5. a translation with no Turnstile token is refused
#   6. a translation with Cloudflare's always-pass test token succeeds
#   7. the logs hold no file name, no document text and no address
#   8. peak memory during an OCR translation, which is what sizes mem_limit
#
# Cloudflare publishes the test keys this uses, documented at
# developers.cloudflare.com/turnstile/troubleshooting/testing/: site key
# 1x00000000000000000000AA always passes, and secret 1x0000000000000000000000000000000AA
# always validates. They are public values, not credentials.
set -euo pipefail

IMAGE="${1:?usage: smoke.sh IMAGE [--scan SCAN.pdf]}"
shift
SCAN=""
while [ $# -gt 0 ]; do
    case "$1" in
        --scan) SCAN="${2:?--scan needs a path}"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done

SITE_KEY=1x00000000000000000000AA
SECRET_KEY=1x0000000000000000000000000000000AA
DUMMY_TOKEN=XXXX.DUMMY.TOKEN.XXXX
BASE=/v2c
PORT=3309
NAME=v2c-smoke-$$

# A name a log must never repeat, and a body no extractor recognises, so the run ends in
# the CLI's error path with both of them in play.
LEAK_NAME="Sgt-Jane-Q-Veteran-dd214.txt"
LEAK_BODY="Notes for my counselor. Jane Q Veteran. Nothing here is a form."

fail() { echo "SMOKE FAIL: $*" >&2; exit 1; }
step() { printf '\n== %s\n' "$*"; }

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

wait_for() {
    local url="$1" tries=60
    while [ "$tries" -gt 0 ]; do
        if curl -fsS -o /dev/null "$url" 2>/dev/null; then return 0; fi
        if ! docker ps --filter "name=^${NAME}$" --format '{{.Names}}' | grep -q .; then
            echo "--- container exited; its log ---" >&2
            docker logs "$NAME" 2>&1 | tail -30 >&2
            return 1
        fi
        sleep 1
        tries=$((tries - 1))
    done
    return 1
}

step "the image"
# Two numbers, because `docker image inspect` reports whichever the local daemon happens
# to hold: the sum of compressed layers for an image buildkit has just loaded, and the
# uncompressed total for one unpacked on disk. Those differ by about three times, which is
# enough to make a size quoted in a document meaningless unless it says which it is. So:
# what it costs to pull, and what it costs to keep.
bytes=$(docker image inspect "$IMAGE" --format '{{.Size}}') || fail "no such image: $IMAGE"
echo "size, as this daemon holds it: ${bytes} bytes ($((bytes / 1048576)) MiB)"
rootfs=$(docker run --rm --user 0 --entrypoint du "$IMAGE" -xsm / 2>/dev/null | cut -f1 || echo 0)
echo "size, unpacked root filesystem:  ${rootfs} MiB"
{
    echo "IMAGE_MIB=$((bytes / 1048576))"
    echo "ROOTFS_MIB=${rootfs}"
} >> "${GITHUB_OUTPUT:-/dev/null}"

step "1. hosted mode refuses to boot without the Turnstile secret"
# Detached and then waited on, with a deadline: a container that stays up is the failure
# this asserts against, so the check must not be the one that hangs.
docker run -d --name "$NAME" -e V2C_MODE=hosted -e TURNSTILE_SITE_KEY="$SITE_KEY" "$IMAGE" >/dev/null
if ! timeout 45 docker wait "$NAME" >/tmp/v2c-noboot.code 2>/dev/null; then
    docker logs "$NAME" 2>&1 | tail -5 >&2
    fail "hosted mode with no TURNSTILE_SECRET_KEY was still running after 45s"
fi
[ "$(cat /tmp/v2c-noboot.code)" != "0" ] || fail "it exited, but it exited successfully"
docker logs "$NAME" 2>&1 | grep -q "TURNSTILE_SECRET_KEY" \
    || fail "it refused to start, but said nothing about the missing key"
echo "ok: exited $(cat /tmp/v2c-noboot.code), and said which key was missing"
cleanup

step "2. local mode listens on loopback inside the container only"
docker run -d --name "$NAME" -p "127.0.0.1:${PORT}:3009" "$IMAGE" >/dev/null
sleep 8
if curl -fsS -o /dev/null --max-time 5 "http://127.0.0.1:${PORT}${BASE}/api/healthz" 2>/dev/null; then
    fail "local mode was reachable from outside the container"
fi
docker exec "$NAME" node -e "
  fetch('http://127.0.0.1:3009${BASE}/api/healthz').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))
" || fail "local mode did not answer on loopback inside the container"
echo "ok: answers inside, unreachable outside"
cleanup

step "3. hosted mode, read-only root filesystem, uploads on a tmpfs"
docker run -d --name "$NAME" \
    --read-only \
    --tmpfs /tmp/v2c:rw,noexec,nosuid,size=256m,mode=1777 \
    -e V2C_MODE=hosted \
    -e TURNSTILE_SITE_KEY="$SITE_KEY" \
    -e TURNSTILE_SECRET_KEY="$SECRET_KEY" \
    -p "127.0.0.1:${PORT}:3009" \
    "$IMAGE" >/dev/null
wait_for "http://127.0.0.1:${PORT}${BASE}/api/healthz" || fail "never became healthy"
curl -fsS "http://127.0.0.1:${PORT}${BASE}/api/healthz" | grep -q '"mode":"hosted"' \
    || fail "healthz did not report hosted mode"
curl -fsS "http://127.0.0.1:${PORT}${BASE}/api/readyz" | grep -q '"ok":true' \
    || fail "readyz says the CLI or the index is missing"
echo "ok: healthy, ready, on a read-only root filesystem"

step "4. the page says what a hosted deploy can honestly say"
page=$(curl -fsS "http://127.0.0.1:${PORT}${BASE}")
grep -q "sent over HTTPS to this server" <<<"$page" || fail "page is missing the hosted privacy copy"
grep -q "aren&#x27;t comfortable sending\|aren't comfortable sending" <<<"$page" \
    || fail "page is missing the line about not uploading what you would rather not"
grep -q "Stays on this computer" <<<"$page" && fail "page still claims the documents stay on this computer"
grep -q "$SITE_KEY" <<<"$page" || fail "page does not carry the Turnstile site key"
grep -q "challenges.cloudflare.com" <<<"$(curl -fsSI "http://127.0.0.1:${PORT}${BASE}")" \
    || fail "the response headers do not allow Turnstile"
echo "ok: hosted copy, site key rendered at request time, policy allows Turnstile"

step "5. a translation with no Turnstile token is refused"
printf '%s' "$LEAK_BODY" > /tmp/v2c-leak.txt
code=$(curl -s -o /tmp/v2c-out.json -w '%{http_code}' \
    -F "files=@/tmp/v2c-leak.txt;filename=${LEAK_NAME}" \
    "http://127.0.0.1:${PORT}${BASE}/api/translate")
[ "$code" = "403" ] || fail "expected 403 with no token, got $code: $(cat /tmp/v2c-out.json)"
echo "ok: 403"

step "6. a translation with the test token succeeds"
code=$(curl -s -o /tmp/v2c-report.json -w '%{http_code}' \
    -F "files=@web/public/samples/army_2000.txt" \
    -F "files=@web/public/samples/army_2000_dd215.json" \
    -F "turnstileToken=${DUMMY_TOKEN}" \
    "http://127.0.0.1:${PORT}${BASE}/api/translate")
[ "$code" = "200" ] || fail "expected 200, got $code: $(head -c 400 /tmp/v2c-report.json)"
grep -q '"ok":true' /tmp/v2c-report.json || fail "the report does not say ok"
grep -q '11B' /tmp/v2c-report.json || fail "the report does not name the sample's specialty"
echo "ok: translated, and the report names 11B"

step "7. a failed translation leaves nothing about the document in the log"
code=$(curl -s -o /tmp/v2c-out.json -w '%{http_code}' \
    -F "files=@/tmp/v2c-leak.txt;filename=${LEAK_NAME}" \
    -F "turnstileToken=${DUMMY_TOKEN}" \
    -H "X-Real-IP: 198.51.100.23" \
    "http://127.0.0.1:${PORT}${BASE}/api/translate")
[ "$code" = "422" ] || fail "expected 422 for an unreadable file, got $code"
logs=$(docker logs "$NAME" 2>&1)
for secret in "$LEAK_NAME" "Jane" "198.51.100.23" "Unrecognised document" "army_2000"; do
    grep -qF "$secret" <<<"$logs" && fail "the log repeats \"$secret\""
done
grep -q "v2c hosted mode" <<<"$logs" || fail "the log is missing the one line boot is allowed"
echo "ok: the log holds the boot line and nothing about anybody's documents"

step "8. peak memory"
peak=$(docker exec "$NAME" sh -c 'cat /sys/fs/cgroup/memory.peak 2>/dev/null || cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null || echo 0')
if [ -n "$SCAN" ] && [ -f "$SCAN" ]; then
    echo "translating a scanned PDF through OCR: $SCAN"
    code=$(curl -s -o /tmp/v2c-scan.json -w '%{http_code}' --max-time 120 \
        -F "files=@${SCAN}" -F "turnstileToken=${DUMMY_TOKEN}" \
        "http://127.0.0.1:${PORT}${BASE}/api/translate")
    [ "$code" = "200" ] || echo "note: the scan came back $code: $(head -c 300 /tmp/v2c-scan.json)"
    peak=$(docker exec "$NAME" sh -c 'cat /sys/fs/cgroup/memory.peak 2>/dev/null || cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null || echo 0')
else
    echo "note: no --scan given, so this peak covers the text translations only"
fi
if [ "$peak" -gt 0 ] 2>/dev/null; then
    echo "peak memory: ${peak} bytes ($((peak / 1048576)) MiB)"
    echo "PEAK_RSS_MIB=$((peak / 1048576))" >> "${GITHUB_OUTPUT:-/dev/null}"
else
    echo "note: this kernel's cgroup files did not report a peak"
fi

printf '\nSMOKE OK\n'
