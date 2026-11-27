# Deploying the translator at rogerhenley.dev/v2c

This is the hosted half: a container image, and exactly what the career site has to add to
run it. Nothing here changes how the app works on your own computer, which is still
`pnpm dev` on port 3009 at `/`.

- [The shape of it](#the-shape-of-it)
- [The two modes](#the-two-modes)
- [Environment](#environment)
- [What the career site has to add](#what-the-career-site-has-to-add)
- [About the Content-Security-Policy](#about-the-content-security-policy)
- [Sizing](#sizing)
- [Rolling out](#rolling-out)
- [Rolling back](#rolling-back)
- [The privacy model](#the-privacy-model)
- [What is still worth doing](#what-is-still-worth-doing)

---

## The shape of it

```
browser ──HTTPS──▶ Caddy ──┬── handle /api/*  ─▶ career-site api
  rogerhenley.dev          ├── handle /v2c*   ─▶ v2c:3009        ◀── this image
                           └── handle         ─▶ career-site web

                     v2c container
                     ├── node server.js          the Next.js page and /v2c/api/*
                     ├── /opt/v2c/venv/bin/dd214kw   the CLI, run per request
                     ├── /opt/v2c/index.sqlite   O*NET + DMDC, built into the image
                     ├── tesseract, pdftoppm     for a scanned page
                     └── /tmp/v2c                tmpfs; uploads live here for seconds
```

One container, not two. A translation is one request: the route writes the uploaded files
to a temp directory and runs `dd214kw translate` on them. Splitting the page from the CLI
would mean sending a veteran's documents over a hop between two containers, which is the
opposite of what the page promises.

The image is published by CI on every push to main, as
`ghcr.io/reh3376/v2c-translator:<12-char-sha>` and `:main`. The twelve-character sha is
career-site's convention, so one `IMAGE_TAG`-shaped value means the same thing in both
repositories.

## The two modes

`V2C_MODE` is read once at boot. It defaults to `local`, so nothing anybody runs today
changes.

| | `local` | `hosted` |
| --- | --- | --- |
| Listens on | 127.0.0.1 | 0.0.0.0, inside the container |
| Turnstile | no widget, no third-party script | required; refuses to boot without the pair |
| Per-visitor limit | none | 10 translations / 10 minutes, keyed on `X-Real-IP` |
| Concurrent translations | 4 | 2, with 8 allowed to wait |
| Whole request | up to 101 MB | up to 25 MB |
| `Content-Security-Policy` | this origin only | this origin plus `challenges.cloudflare.com` |
| What the page promises | the documents stay on this computer | they are sent, read in memory, and deleted |

One thing is not in that table because it cannot be: the path the app is served under.
Next.js resolves `basePath` while it writes the client manifests, so it belongs to the
build. The image is built with `V2C_BASE_PATH=/v2c`; a build arg changes it.

## Environment

| Variable | Default | What it does |
| --- | --- | --- |
| `V2C_MODE` | `local` | `local` or `hosted`. Anything else refuses to start. |
| `TURNSTILE_SITE_KEY` | — | Public half. Rendered into the page at request time, not inlined at build, so CI can build the image without Cloudflare keys. **Required in hosted mode.** |
| `TURNSTILE_SECRET_KEY` | — | Private half, used only to verify a token. **Required in hosted mode**, and the process exits if it is missing. |
| `V2C_MAX_CONCURRENT` | 2 hosted, 4 local | Translations running at once. Each one runs two CLI processes; see [Sizing](#sizing). |
| `V2C_QUEUE_MAX` | 8 | Translations allowed to wait. Past this: 503 and a `Retry-After`. 0 means no waiting. |
| `V2C_RATE_LIMIT` | 10 | Translations per window per visitor. Hosted only. |
| `V2C_RATE_WINDOW_MINUTES` | 10 | The window. |
| `V2C_MAX_BODY_MB` | 25 | The whole multipart request, hosted only. The per-file limit (10 MB) and the file count (10) do not change. |
| `V2C_TMPDIR` | the system temp dir | Where uploads are written, and what the entrypoint exports as `TMPDIR`, so the OCR tools' own temp files go to the same tmpfs. Point it at a tmpfs. |
| `V2C_HOST` | — | Overrides the bind address the mode would choose. |
| `PORT` | 3009 | |
| `DD214KW_BIN` | set in the image | The CLI executable. Unset on a developer's machine, where `uv run` is used instead. |
| `DD214KW_INDEX` | set in the image | The O*NET index. `/api/readyz` fails if it is missing. |

Two endpoints exist for the deploy rather than for a reader:

- `GET /v2c/api/healthz` — is this process serving? No CLI, no file system. This is what
  the container's `HEALTHCHECK` and compose's healthcheck call every thirty seconds.
- `GET /v2c/api/readyz` — can it actually translate? Runs `dd214kw --version`, checks the
  index is there, and runs `dd214kw check-ocr`, which renders a blank page and reads it in
  this container's own temp directory. Cached for a minute on a pass and five seconds on a
  fail. 503 with which of the three it was. **This is the one a rollout should wait on.**
  An image built without the index serves a perfectly healthy page that fails on every
  upload; a container whose temp directory is not writable serves a healthy page that
  translates a text PDF and reads nothing off a scan.

## What the career site has to add

Three changes, and nothing else. None of them touches an existing service.

**1. `docker-compose.prod.yml` — a service.** No host port: it is reached only by Caddy on
the `app` network, which is also what the box's DOCKER-USER rules assume.

```yaml
  # The veteran-to-civilian translator, at /v2c. Its own image, from its own
  # repository (reh3376/v2c-translator), on its own tag, so a rollout of it
  # touches nothing else here.
  v2c:
    image: ghcr.io/${GHCR_OWNER:-reh3376}/v2c-translator:${V2C_IMAGE_TAG:-main}
    restart: unless-stopped
    pull_policy: always
    environment:
      TZ: UTC
      V2C_MODE: hosted
      # The same Turnstile pair the api uses. Turnstile keys are bound to a
      # hostname and this is the same hostname, so a second widget is not
      # needed. One pair also means rotating it is one change.
      TURNSTILE_SITE_KEY: ${TURNSTILE_SITE_KEY}
      TURNSTILE_SECRET_KEY: ${TURNSTILE_SECRET_KEY}
      V2C_MAX_CONCURRENT: ${V2C_MAX_CONCURRENT:-2}
      V2C_QUEUE_MAX: ${V2C_QUEUE_MAX:-8}
      V2C_RATE_LIMIT: ${V2C_RATE_LIMIT:-10}
      V2C_RATE_WINDOW_MINUTES: ${V2C_RATE_WINDOW_MINUTES:-10}
      V2C_MAX_BODY_MB: ${V2C_MAX_BODY_MB:-25}
      V2C_TMPDIR: /tmp/v2c
    # The image writes nothing but its upload directory, so the root
    # filesystem is read-only and the upload directory is memory. An
    # uploaded DD-214 never reaches this box's disk.
    read_only: true
    tmpfs:
      - /tmp/v2c:rw,noexec,nosuid,size=256m,mode=1777
    # See "Sizing" in the v2c repository's docs/deploy.md. Two concurrent
    # OCR translations of a multi-page scan is what this number is for.
    mem_limit: ${V2C_MEM_LIMIT:-3g}
    cpus: ${V2C_CPUS:-2.0}
    healthcheck:
      test:
        - CMD
        - node
        - -e
        - "fetch('http://127.0.0.1:3009/v2c/api/healthz').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 25s
    networks: [app]
```

**2. `deploy/caddy/Caddyfile.prod` — a handle, and a matcher on the site's policy.**

```caddyfile
    # The site's security headers, unchanged, except that the
    # Content-Security-Policy moves out of this block so it can be scoped.
    header {
        Strict-Transport-Security "max-age=63072000; includeSubDomains; preload"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Permissions-Policy "camera=(), microphone=(), geolocation=(), payment=(), usb=(), midi=(), sync-xhr=()"
        X-Frame-Options "DENY"
        Cross-Origin-Opener-Policy "same-origin"
        Cross-Origin-Resource-Policy "same-origin"
        X-Permitted-Cross-Domain-Policies "none"
        -Server
    }

    # The site's policy, everywhere but /v2c, which sends its own. See
    # "About the Content-Security-Policy" in the v2c repository's docs/deploy.md
    # for why this is a matcher and not a site-wide header.
    @site not path /v2c /v2c/*
    header @site Content-Security-Policy "default-src 'self'; img-src 'self' data: https://avatars.githubusercontent.com https://api.github.com; font-src 'self' https://fonts.gstatic.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; script-src 'self' 'unsafe-inline' https://challenges.cloudflare.com; frame-src https://challenges.cloudflare.com; connect-src 'self' https://api.github.com https://api.pwnedpasswords.com https://challenges.cloudflare.com; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"

    # /v2c* -> the translator. `header_up X-Real-IP {remote_host}` for the same
    # reason the /api/* block has it: the app's per-visitor limit has to read an
    # address this proxy set, because a client can send its own.
    handle /v2c* {
        reverse_proxy v2c:3009 {
            header_up X-Real-IP {remote_host}
        }
    }
```

`handle /v2c*` and `handle /api/*` do not overlap: the app's own endpoints are under
`/v2c/api/`, which Caddy matches on the `/v2c*` block.

**3. `.env.prod` — one required line and some optional ones.**

```bash
# Image tag for the v2c translator, from reh3376/v2c-translator CI. A
# 12-character sha, or `main` to follow that branch.
V2C_IMAGE_TAG=main

# Optional; the compose file's defaults are these.
# V2C_MEM_LIMIT=3g
# V2C_CPUS=2.0
# V2C_MAX_CONCURRENT=2
# V2C_QUEUE_MAX=8
# V2C_RATE_LIMIT=10
# V2C_RATE_WINDOW_MINUTES=10
# V2C_MAX_BODY_MB=25
```

`TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` are already there for the api, and the
v2c container reads the same two.

**Not in this list:** a link to the tool from the career site's own pages. That is a
content decision, not a deploy one.

## About the Content-Security-Policy

The thing everybody expects here is wrong, so it is worth a section.

A browser handed two `Content-Security-Policy` headers does enforce both, and a resource
has to be allowed by each. But it is never handed two, because **Caddy's `header`
directive with a value replaces the upstream header rather than adding to it.** Measured
against the built image on 2026-11-26 with `deploy/verify-behind-caddy.sh`: exactly one
policy reaches the browser.

Which one depends on the Caddyfile:

- **Site-wide header, plain `reverse_proxy`.** The site's policy arrives and the app's is
  discarded. The page still works, because the career site allows
  `challenges.cloudflare.com` on `script-src`, `frame-src` and `connect-src` for its own
  Turnstile widget, and allows everything else this app loads. So adding only a
  `reverse_proxy` is not broken on day one.
- **The matcher above.** The app's policy arrives. The page works under that too.

Ship the matcher. Not because the other way is broken today, but because without it this
app's requirements are a side effect of another app's policy: the day the career site
stops using Turnstile and tightens `frame-src`, this page's robot check becomes an empty
box, with no error in any log, and the first person to notice is a veteran whose upload is
refused.

Both arrangements are checked by `deploy/verify-behind-caddy.sh`, which stands up Caddy
and this image with Docker Compose and drives the page with a real browser. Run it before
changing either policy. The one thing it cannot exercise is `frame-src`: Cloudflare's test
site key draws no challenge iframe. So **the first manual check after the deploy is that
the robot check's box actually appears on the page.**

## Sizing

Measured in the container on 2026-11-26, with `deploy/smoke.sh`, on the image built from
this branch. Peak is the container's cgroup peak, so it covers the Node process, both CLI
processes and tesseract together.

| | Peak | |
| --- | --- | --- |
| Image, to pull | 190 MiB | the sum of the compressed layers |
| Image, unpacked on disk | ~555 MiB | what it occupies on the box; 553 on a runner, 556 on a laptop |
| Idle, just booted | 63 MiB | |
| One text translation | 72 MiB | |
| One 1-page 300 dpi scan, OCR'd | 456 MiB | ~4.6 s |
| Two of those at once | 890 MiB | |
| One 5-page scan, OCR'd | 811-851 MiB | 35 s; three runs, two local and one on a GitHub runner |

Pages drive it, not file size: the 1-page and the 5-page scan are both about 1 MB.

The two image sizes are both worth knowing and are easy to confuse, which is why
`deploy/smoke.sh` prints both and labels them. `docker image inspect` reports whichever
the local daemon holds, and for an image buildkit has just loaded that is the compressed
total, about a third of the unpacked one.

Two things multiply it. A translation runs `dd214kw translate` **twice in parallel**, once
for JSON and once for Markdown, so a scan is OCR'd twice. And `V2C_MAX_CONCURRENT`
translations run at once.

What caps it is the 60-second CLI timeout, not the 10 MB file limit: five pages took 35
seconds, so a translation of about eight pages times out before it finishes. Budget
roughly 1.2 GB for one translation of a scan that just fits under that timeout.

So, for `V2C_MAX_CONCURRENT=2`: about 2.4 GB of translations, plus up to 200 MB of queued
request bodies (25 MB × 8 waiting), plus 63 MiB idle. **`mem_limit: 3g`.** On the CPX41's
16 GB with Ollama capped at 7 GB, that leaves room.

If you would rather give it less, `V2C_MAX_CONCURRENT=1` with `mem_limit: 1536m` is the
other sensible point. It halves the worst case, and the queue already absorbs bursts; what
it costs is that a second visitor waits rather than running alongside the first.

## Rolling out

The career site's `deploy/rollout.sh` is the runbook, executable. Until it knows about
this service, the steps by hand, from a checkout on your own machine:

```bash
# 1. Find the tag CI published. The image job's summary prints it, or:
gh api repos/reh3376/v2c-translator/commits/main --jq '.sha[:12]'

# 2. Point .env.prod at it.
ssh career@5.161.62.205 "cd /opt/career-site \
  && cp .env.prod .env.prod.bak \
  && sed -i '/^V2C_IMAGE_TAG=/d' .env.prod \
  && echo 'V2C_IMAGE_TAG=<sha>' >> .env.prod"

# 3. Pull and start that one service. The others are untouched.
ssh career@5.161.62.205 "cd /opt/career-site \
  && docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml \
     pull v2c \
  && docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml \
     up -d v2c"

# 4. Wait for it to say it can translate, not merely that it is alive.
curl -fsS https://rogerhenley.dev/v2c/api/readyz    # {"ok":true,"checks":{"cli":true,"index":true,"ocr":true}}

# 5. Look at the page, and at the one thing no script checks: does the robot
#    check's box appear? Then translate the sample documents.
open https://rogerhenley.dev/v2c
```

If step 4 does not come good, read the container's log. It is allowed to say three kinds
of thing and no more: one line at boot naming the mode and the limits, `v2c cannot start:`
with which variable is missing, and `translate failed id=… kind=…` for a failure. If you
see a file name or a line of someone's document in there, that is a bug and
`web/src/server/logging.test.ts` should have caught it.

```bash
ssh career@5.161.62.205 "cd /opt/career-site && docker compose logs --tail 50 v2c"
```

## Rolling back

Same three steps with the previous tag, and nothing else on the site is affected:

```bash
ssh career@5.161.62.205 "cd /opt/career-site \
  && sed -i '/^V2C_IMAGE_TAG=/d' .env.prod \
  && echo 'V2C_IMAGE_TAG=<previous-sha>' >> .env.prod \
  && docker compose --env-file .env.prod -f docker-compose.yml -f docker-compose.prod.yml \
     up -d v2c"
curl -fsS https://rogerhenley.dev/v2c/api/readyz
```

To take the tool down without a rollback, comment out the `handle /v2c*` block and reload
Caddy. The page disappears; nothing else changes.

## The privacy model

What the hosted page says, and why each clause is true:

> Your documents are sent over HTTPS to this server, read in memory, and deleted as soon
> as your report is ready. Nothing is stored, logged or shared.

- **Sent over HTTPS.** Caddy terminates TLS and the hop to the container is on a private
  Docker network on one box.
- **Read in memory.** `V2C_TMPDIR` is a tmpfs, so the files the CLI reads are in RAM. The
  root filesystem is read-only, so there is nowhere else for them to go.
- **Deleted as soon as your report is ready.** `mkdtemp` at 0700, each file at 0600, and
  `rm -rf` in a `finally`. The route tests assert no directory is left behind on every
  path, including a timeout and a crash.
- **Nothing is stored.** No database, no volume, no object store. The container has one
  writable path and it is memory.
- **Nothing is logged.** A failure logs a request id and a failure kind. Not the file
  name, which a veteran may well have called `john_smith_dd214.pdf`; not the CLI's
  stderr, which begins with that file name; not the visitor's address, which is a map key
  for the rate limit and nothing else. `web/src/server/logging.test.ts` drives the real
  route against the real console with an unmistakable name and body and fails if either
  appears, and `deploy/smoke.sh` repeats that against the running container.
- **Nothing is shared.** One request leaves this server, to
  `challenges.cloudflare.com/turnstile/v0/siteverify`, carrying the Turnstile token, the
  secret key and the visitor's address. No document, no file name, no report. The
  Content-Security-Policy stops the page itself connecting anywhere else.

And the line under it, which is the honest part:

> Don't upload a document you aren't comfortable sending.

Everything above is a property of this code and this box. It is not a property of the
reader's network, and it is not a promise that this box cannot be compromised. A reader
who would rather not send a DD-214 anywhere can run the same tool on their own computer,
where the privacy copy says so instead.

## What is still worth doing

Not in this change, deliberately, and in the order worth doing them:

1. **Render both output formats from one read.** The route runs the CLI twice in parallel,
   for JSON and for Markdown, so a scanned page is OCR'd twice: double the memory and
   double the time, for one document. A `dd214kw translate` that emits both from one
   extraction would halve the numbers in [Sizing](#sizing) and let
   `V2C_MAX_CONCURRENT=2` fit in half the memory. It is a change to the CLI, which is why
   it is not in a deploy change.
2. **Teach `deploy/rollout.sh` about this service**, in the career-site repository, so the
   steps above stop being a list in a document.
3. **Cap the pages in a scan.** Today the 60-second timeout is the de facto cap, which
   means a visitor with a ten-page scan gets a timeout rather than an answer. An explicit
   page limit with a clear message would be kinder and would make the memory ceiling a
   number rather than a consequence.
4. **A second container, behind a shared gate.** Only if the one gets busy. The gate and
   the rate limit are both in memory, so two containers would need them somewhere both
   can see.
