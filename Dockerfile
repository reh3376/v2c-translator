# syntax=docker/dockerfile:1.7
#
# The hosted v2c translator: the Next.js page, the dd214kw CLI it shells out to, the
# O*NET index that CLI looks every specialty up in, and the two binaries OCR needs.
#
# One image, because the page and the CLI are one request: `/api/translate` writes the
# uploaded files to a temp directory and runs `dd214kw translate` on them once, for both
# output formats. Splitting them into two containers would mean shipping documents over a
# network hop between them, which is the opposite of what this service promises.
#
# Node and Python in the same image, because of that. The base is a Node image and Python
# comes from Debian, rather than the other way round, because the Node runtime is the
# harder of the two to graft on.
#
# Base images are pinned by digest. The tag beside each is what the digest was, so
# Dependabot's docker ecosystem can read and bump it.

ARG NODE_IMAGE=node@sha256:f0960f8dc047f358e3fb428f36ccba21732194fa5f0cac849f401e63e62fb9e6
# node:22-trixie-slim — Debian 13, Node 22.23.5, Python 3.13 from apt
ARG UV_IMAGE=ghcr.io/astral-sh/uv@sha256:df4cae8f3a96d175e2e5f992e597550000edbe78fdc2594d5cd8de1a217f504c
# ghcr.io/astral-sh/uv:0.11.32

ARG PNPM_VERSION=10.28.0

# The path the app is served under. Baked, because Next.js resolves `basePath` while it
# writes the client manifests. Everything else about the deploy is read at boot.
ARG V2C_BASE_PATH=/v2c

# Named, because `COPY --from` takes a stage name and not a variable.
FROM ${UV_IMAGE} AS uv


# --------------------------------------------------------------- the web app, installed
#
# pnpm arrives in two pieces. corepack installs the package; pnpm then downloads its own
# native binary the first time it is invoked. `pnpm --version` here forces that download
# into a layer keyed on the pnpm version alone, so an ordinary code change reuses it and
# makes no network call. career-site's web Dockerfile learned this the hard way; the note
# there has the date.
FROM ${NODE_IMAGE} AS web-deps
ARG PNPM_VERSION
RUN corepack enable \
 && corepack prepare pnpm@${PNPM_VERSION} --activate \
 && pnpm --version
WORKDIR /app
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store \
    pnpm install --frozen-lockfile


# ------------------------------------------------------------------ the web app, built
FROM ${NODE_IMAGE} AS web-build
ARG PNPM_VERSION
ARG V2C_BASE_PATH
RUN corepack enable \
 && corepack prepare pnpm@${PNPM_VERSION} --activate \
 && pnpm --version
WORKDIR /app
# V2C_STANDALONE asks next.config.ts for `output: "standalone"`, which is only ever what
# this image wants: `next start`, which README tells a developer to run, refuses to work
# with a standalone build.
ENV NEXT_TELEMETRY_DISABLED=1 \
    V2C_STANDALONE=1 \
    V2C_BASE_PATH=${V2C_BASE_PATH} \
    NODE_ENV=production
COPY --from=web-deps /app/node_modules ./node_modules
COPY web/ ./
RUN pnpm build


# ------------------------------------------------- the CLI, and the index it reads from
#
# Installed non-editable, so the virtualenv is the whole of it and no repository source
# has to be carried into the runtime.
FROM ${NODE_IMAGE} AS cli-build
COPY --from=uv /uv /usr/local/bin/uv
RUN apt-get update \
 && apt-get install -y --no-install-recommends python3 \
 && rm -rf /var/lib/apt/lists/*

# Debian's python3, not one uv downloads, so the runtime stage gets the same interpreter
# from the same pinned base image and the virtualenv's paths line up. Debian does not
# change the Python minor version within a release, so `lib/python3.13` stays right.
ENV UV_PROJECT_ENVIRONMENT=/opt/v2c/venv \
    UV_PYTHON=/usr/bin/python3 \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1

WORKDIR /src
# Dependencies first, in a layer invalidated only by the lockfile.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project --extra ocr
COPY src/ ./src/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-editable --extra ocr

# The index, built here so the image ships ready to translate. The sources are O*NET and
# the DMDC military crosswalk, both public under CC BY 4.0; the attribution the licence
# asks for is in src/dd214kw/index.py and in README, and it travels with this file.
#
# This is the one step that needs the network at build time. It is also the step that
# makes the image useful: without the index the page loads and every upload fails, which
# is what /api/readyz exists to catch.
ENV DD214KW_INDEX=/opt/v2c/index.sqlite
RUN /opt/v2c/venv/bin/dd214kw build-index --download --raw-dir /tmp/onet \
 && test -s /opt/v2c/index.sqlite \
 && rm -rf /tmp/onet


# ----------------------------------------------------------------------- what is served
FROM ${NODE_IMAGE} AS runtime
ARG V2C_BASE_PATH

# python3 to run the CLI, tesseract to read a scan, poppler to turn a scanned PDF's
# pages into images for it. tesseract-ocr-eng is named explicitly: the metapackage's
# recommended language data is not installed with --no-install-recommends, and without
# it tesseract exits on every scan.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      python3 \
      tesseract-ocr \
      tesseract-ocr-eng \
      poppler-utils \
 && rm -rf /var/lib/apt/lists/*

RUN groupadd --system --gid 65532 v2c \
 && useradd --system --uid 65532 --gid 65532 --no-create-home --home-dir /nonexistent v2c

WORKDIR /app

COPY --from=cli-build --chown=root:root /opt/v2c /opt/v2c
COPY --from=web-build --chown=root:root /app/.next/standalone ./
COPY --from=web-build --chown=root:root /app/.next/static ./.next/static
COPY --from=web-build --chown=root:root /app/public ./public
COPY --chown=root:root deploy/entrypoint.sh /usr/local/bin/v2c

# Everything is owned by root and read by an unprivileged user, so the image works with
# `read_only: true`. The only thing this process writes is a temp directory under
# V2C_TMPDIR, which the compose file mounts as a tmpfs, so an uploaded document never
# reaches a disk.
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3009 \
    V2C_BASE_PATH=${V2C_BASE_PATH} \
    V2C_TMPDIR=/tmp/v2c \
    DD214KW_BIN=/opt/v2c/venv/bin/dd214kw \
    DD214KW_INDEX=/opt/v2c/index.sqlite

USER v2c
EXPOSE 3009

# node's own fetch, so the image needs no curl or wget. Asks the app, through the base
# path, the one question that costs nothing to answer.
HEALTHCHECK --interval=30s --timeout=5s --start-period=25s --retries=3 \
  CMD node -e "const u='http://127.0.0.1:'+(process.env.PORT||3009)+(process.env.V2C_BASE_PATH||'')+'/api/healthz';fetch(u).then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

ENTRYPOINT ["/usr/local/bin/v2c"]
