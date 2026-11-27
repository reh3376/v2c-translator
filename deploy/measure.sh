#!/usr/bin/env bash
# What a translation costs this container: peak memory and wall time, per case.
#
#   deploy/measure.sh IMAGE --case "1-page scan=/tmp/s1.pdf" --case "5-page scan=/tmp/s5.pdf"
#
# This is where the numbers in the Sizing table in docs/deploy.md come from, so that the
# table is something a reader can reproduce rather than something they have to believe.
# `deploy/smoke.sh` reports one peak for a whole smoke run; this reports a peak and a
# time per case, single and two at once, over several runs, with the spread.
#
# The container is restarted before every run, because the kernel's peak counter only
# ever goes up: one run's peak would otherwise be reported as the next one's.
#
# Options:
#   --case LABEL=PATH   One upload to translate, or several comma-separated files as one
#                       upload. Repeatable. A scan is drawn by tests/make_scan.py; pages
#                       drive the cost, not file size.
#   --runs N            Runs per case (default 3). The table wants the median and range.
#   --at-once "1 2"     How many translations to start together (default "1 2").
#   --max-pages N       V2C_MAX_PAGES for the container.
#   --mode MODE         hosted (default) or local. Hosted is how production runs, and it
#                       verifies every upload's token with Cloudflare; local skips that,
#                       for a machine with no route out.
set -euo pipefail

IMAGE="${1:?usage: measure.sh IMAGE --case LABEL=PATH [--case ...] [--runs N]}"
shift

LABELS=()
PATHS=()
RUNS=3
AT_ONCE="1 2"
MAX_PAGES=""
MODE=hosted

while [ $# -gt 0 ]; do
    case "$1" in
        --case) LABELS+=("${2%%=*}"); PATHS+=("${2#*=}"); shift 2 ;;
        --runs) RUNS="$2"; shift 2 ;;
        --at-once) AT_ONCE="$2"; shift 2 ;;
        --max-pages) MAX_PAGES="$2"; shift 2 ;;
        --mode) MODE="$2"; shift 2 ;;
        *) echo "unknown argument: $1" >&2; exit 2 ;;
    esac
done
[ "${#PATHS[@]}" -gt 0 ] || { echo "measure.sh: give at least one --case LABEL=PATH" >&2; exit 2; }

# Cloudflare's documented test pair, which always passes. Public values, not credentials.
SITE_KEY=1x00000000000000000000AA
SECRET_KEY=1x0000000000000000000000000000000AA
DUMMY_TOKEN=XXXX.DUMMY.TOKEN.XXXX
BASE=/v2c
PORT=3409
NAME=v2c-measure-$$
URL="http://127.0.0.1:${PORT}${BASE}"

cleanup() { docker rm -f "$NAME" >/dev/null 2>&1 || true; }
trap cleanup EXIT

boot() {
    cleanup
    local extra=()
    if [ -n "$MAX_PAGES" ]; then extra+=(-e "V2C_MAX_PAGES=${MAX_PAGES}"); fi
    # Local mode listens on loopback inside the container, so nothing outside it can ask.
    if [ "$MODE" = local ]; then extra+=(-e V2C_HOST=0.0.0.0); fi
    docker run -d --name "$NAME" \
        --read-only \
        --tmpfs /tmp/v2c:rw,noexec,nosuid,size=256m,mode=1777 \
        -e "V2C_MODE=${MODE}" \
        -e "TURNSTILE_SITE_KEY=${SITE_KEY}" \
        -e "TURNSTILE_SECRET_KEY=${SECRET_KEY}" \
        -e V2C_MAX_CONCURRENT=2 \
        "${extra[@]}" \
        -p "127.0.0.1:${PORT}:3009" \
        "$IMAGE" >/dev/null
    local tries=60
    until curl -fsS -o /dev/null "${URL}/api/healthz" 2>/dev/null; do
        tries=$((tries - 1))
        [ "$tries" -gt 0 ] || { docker logs "$NAME" 2>&1 | tail -20 >&2; echo "never became healthy" >&2; exit 1; }
        sleep 1
    done
}

# The container's own peak, cgroup v2 first and v1 second. Digits only: a container that
# has gone away answers with a sentence, and a sentence is not a number of bytes.
peak_mib() {
    local bytes
    bytes=$(docker exec "$NAME" sh -c \
        'cat /sys/fs/cgroup/memory.peak 2>/dev/null || cat /sys/fs/cgroup/memory/memory.max_usage_in_bytes 2>/dev/null' \
        2>/dev/null | tr -dc '0-9')
    echo $(( ${bytes:-0} / 1048576 ))
}

# One translation of one upload, which is one or more comma-separated files. Prints
# "<http code> <seconds>", so a failed run cannot pass as a fast one.
translate() {
    local form=() path
    if [ "$MODE" = hosted ]; then form=(-F "turnstileToken=${DUMMY_TOKEN}"); fi
    IFS=, read -ra files <<< "$1"
    for path in "${files[@]}"; do form+=(-F "files=@${path}"); done
    curl -s -o /dev/null -w '%{http_code} %{time_total}' --max-time 300 \
        "${form[@]}" "${URL}/api/translate"
}

median() { sort -g | awk '{v[NR]=$1} END {print (NR % 2) ? v[(NR+1)/2] : (v[NR/2] + v[NR/2+1]) / 2}'; }
lo() { sort -g | head -1; }
hi() { sort -g | tail -1; }

boot
echo "image:  $IMAGE"
echo "mode:   $MODE${MAX_PAGES:+, V2C_MAX_PAGES=$MAX_PAGES}"
echo "idle:   $(peak_mib) MiB, just booted"
echo "runs:   $RUNS per case; load average now:$(uptime | sed 's/.*average://')"
printf '\n%-22s %-8s %-22s %-18s %s\n' case at-once "peak MiB (median)" "seconds (median)" "codes"

for i in "${!PATHS[@]}"; do
    for at_once in $AT_ONCE; do
        peaks=() times=() codes=""
        for _ in $(seq "$RUNS"); do
            boot
            slowest=0
            for n in $(seq "$at_once"); do
                translate "${PATHS[$i]}" > "/tmp/v2c-measure-$$-$n" &
            done
            wait
            for n in $(seq "$at_once"); do
                # `|| true`: curl writes no trailing newline, so read sets both and reports EOF.
                read -r code seconds < "/tmp/v2c-measure-$$-$n" || true
                codes="${codes}${code} "
                if awk -v a="$seconds" -v b="$slowest" 'BEGIN {exit !(a > b)}'; then slowest="$seconds"; fi
                rm -f "/tmp/v2c-measure-$$-$n"
            done
            peaks+=("$(peak_mib)")
            times+=("$slowest")
        done
        printf '%-22s %-8s %-22s %-18s %s\n' \
            "${LABELS[$i]}" "$at_once" \
            "$(printf '%s\n' "${peaks[@]}" | median) ($(printf '%s\n' "${peaks[@]}" | lo)-$(printf '%s\n' "${peaks[@]}" | hi))" \
            "$(printf '%s\n' "${times[@]}" | median) ($(printf '%s\n' "${times[@]}" | lo)-$(printf '%s\n' "${times[@]}" | hi))" \
            "$(echo "$codes" | tr ' ' '\n' | sort -u | tr '\n' ' ')"
    done
done
