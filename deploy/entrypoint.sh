#!/bin/sh
# The container's two jobs before `node server.js`: say where temporary files go, and
# decide which address to listen on.
#
# TMPDIR, because this image runs with a read-only root filesystem and one writable path,
# the tmpfs at V2C_TMPDIR. Both OCR tools write a temporary file before they do any work:
# pdf2image hands a page to pdftoppm, pytesseract writes the image out and runs tesseract
# on it. Python looks for a temp directory in TMPDIR, then /tmp, /var/tmp, /usr/tmp, and
# last of all the working directory; here the first four are read-only, so without this
# line the only thing that works is the working directory, which a translation happens to
# put on the tmpfs. `dd214kw` run any other way — `/api/readyz`, a `docker exec`, a future
# CLI change — then has no temp directory at all and reads no scan. `/api/readyz` runs
# `dd214kw check-ocr` to prove this line did its job.
#
# Hosted mode is reached by a reverse proxy in another container, so it has to listen on
# every interface in its own network namespace. Local mode keeps the loopback-only
# binding the app has always had, which is what makes "nothing leaves this computer" true
# of `docker run` as well as of `pnpm dev`.
#
# Next.js's standalone server reads the bind address from HOSTNAME, and Docker already
# sets HOSTNAME to the container's name, so that variable cannot also carry an intention.
# V2C_HOST is the override, and it wins over the mode.
set -eu

if [ -n "${V2C_TMPDIR:-}" ]; then
    TMPDIR="${V2C_TMPDIR}"
    export TMPDIR
fi

if [ -n "${V2C_HOST:-}" ]; then
    HOSTNAME="${V2C_HOST}"
elif [ "${V2C_MODE:-local}" = "hosted" ]; then
    HOSTNAME=0.0.0.0
else
    HOSTNAME=127.0.0.1
fi
export HOSTNAME

exec node server.js
