#!/bin/sh
set -eu

source_dir=/etc/letsencrypt/live/134.175.41.179
target_dir=/etc/caddy/certs

install -d -o root -g caddy -m 0750 "$target_dir"
install -o root -g caddy -m 0644 "$source_dir/fullchain.pem" "$target_dir/fullchain.pem"
install -o root -g caddy -m 0640 "$source_dir/privkey.pem" "$target_dir/privkey.pem"

if systemctl is-active --quiet caddy; then
    systemctl reload caddy
fi
