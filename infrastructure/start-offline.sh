#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -f "$root/infrastructure/.env" ]] || { echo 'Run python infrastructure/init-stack.py first.' >&2; exit 1; }
[[ -f "$root/offline-bundle/model-vault/manifest.json" ]] || { echo 'Import the prepared local model vault first.' >&2; exit 1; }
[[ -f "$root/offline-bundle/images.tar" ]] || { echo 'Import the connected-workstation offline bundle first.' >&2; exit 1; }
[[ -x "$root/offline-bundle/fabric-samples/bin/fabric-ca-client" ]] || { echo 'Prepared Fabric CA binaries are missing; prepare a complete bundle.' >&2; exit 1; }
python3 "$root/scripts/offline-bundle.py" verify --directory "$root/offline-bundle"
mkdir -p "$root/model-vault" "$root/infrastructure/vendor/fabric-samples"
cp -a "$root/offline-bundle/model-vault/." "$root/model-vault/"
cp -a "$root/offline-bundle/fabric-samples/." "$root/infrastructure/vendor/fabric-samples/"
docker load -i "$root/offline-bundle/images.tar"
bash "$root/infrastructure/fabric/start.sh"
docker compose --env-file "$root/infrastructure/.env" -f "$root/infrastructure/compose.yml" up -d --no-build --pull never
echo 'Local workspace: https://localhost:8443. Use the URL configured by init-stack.py for LAN access.'
