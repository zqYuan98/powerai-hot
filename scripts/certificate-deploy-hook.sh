#!/bin/sh
set -eu

SRC="${POWERAI_CERT_SOURCE:-/etc/letsencrypt-ip/live/hermes-ip}"
DST="${POWERAI_CERT_DESTINATION:-/etc/caddy/certs/powerai-ip}"
CADDYFILE="${POWERAI_CADDYFILE:-/etc/caddy/Caddyfile}"

install -d -o root -g caddy -m 0750 "$DST"
install -o root -g caddy -m 0644 "$SRC/fullchain.pem" "$DST/fullchain.pem.new"
install -o root -g caddy -m 0640 "$SRC/privkey.pem" "$DST/privkey.pem.new"
mv "$DST/fullchain.pem.new" "$DST/fullchain.pem"
mv "$DST/privkey.pem.new" "$DST/privkey.pem"
sudo -u caddy caddy validate --config "$CADDYFILE" >/dev/null
systemctl reload caddy
