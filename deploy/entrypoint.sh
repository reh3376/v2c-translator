#!/bin/sh
# The container's one job before `node server.js`: decide which address to listen on.
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

if [ -n "${V2C_HOST:-}" ]; then
    HOSTNAME="${V2C_HOST}"
elif [ "${V2C_MODE:-local}" = "hosted" ]; then
    HOSTNAME=0.0.0.0
else
    HOSTNAME=127.0.0.1
fi
export HOSTNAME

exec node server.js
