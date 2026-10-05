#!/usr/bin/env bash
# Connected preparation only. Offline startup never executes this file.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$root"
for command in docker curl tar jq python3; do command -v "$command" >/dev/null; done
docker info >/dev/null
[[ -f infrastructure/.env ]] || python3 infrastructure/init-stack.py
python3 -m venv .venv-prepare
.venv-prepare/bin/pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cpu
.venv-prepare/bin/pip install -r local/requirements-ml.txt -r local/requirements-stack.txt
.venv-prepare/bin/python scripts/prepare-models.py --output model-vault
vendor="$root/infrastructure/vendor";mkdir -p "$vendor"
samples_commit=5789681b4f4d24e58fa40f19a69f5496892374b6
curl --fail --location --retry 3 "https://github.com/hyperledger/fabric-samples/archive/$samples_commit.tar.gz" -o "$vendor/samples.tar.gz"
mkdir -p "$vendor/fabric-samples"
tar --no-same-owner -xzf "$vendor/samples.tar.gz" --strip-components=1 -C "$vendor/fabric-samples"
curl --fail --location --retry 3 https://github.com/hyperledger/fabric/releases/download/v2.5.12/hyperledger-fabric-linux-amd64-2.5.12.tar.gz -o "$vendor/fabric.tar.gz"
tar --no-same-owner -xzf "$vendor/fabric.tar.gz" -C "$vendor/fabric-samples"
curl --fail --location --retry 3 https://github.com/hyperledger/fabric-ca/releases/download/v1.5.15/hyperledger-fabric-ca-linux-amd64-1.5.15.tar.gz -o "$vendor/fabric-ca.tar.gz"
tar --no-same-owner -xzf "$vendor/fabric-ca.tar.gz" -C "$vendor/fabric-samples"
.venv-prepare/bin/python infrastructure/fabric/protect-network.py --directory "$vendor/fabric-samples/test-network"
docker compose --env-file infrastructure/.env -f infrastructure/compose.yml build api ai-worker fabric-gateway
docker build -t sentinel-anchor_ccaas_image:latest infrastructure/fabric/chaincode
images=(nginx:1.28-alpine timescale/timescaledb-ha:pg17 minio/minio:RELEASE.2025-04-22T22-12-26Z minio/mc:RELEASE.2025-04-16T18-13-26Z redis:7.4-alpine quay.io/keycloak/keycloak:26.4.7 prom/prometheus:v3.6.0 grafana/grafana:12.2.0 hyperledger/fabric-peer:2.5.12 hyperledger/fabric-orderer:2.5.12 hyperledger/fabric-ca:1.5.15 hyperledger/fabric-baseos:2.5.12)
for image in "${images[@]}"; do docker pull "$image"; done
mkdir -p offline-bundle
docker save -o offline-bundle/images.tar "${images[@]}" sentinel-api:1.1 sentinel-ai:1.1 sentinel-fabric-gateway:1.1 sentinel-anchor_ccaas_image:latest
docker image inspect "${images[@]}" sentinel-api:1.1 sentinel-ai:1.1 sentinel-fabric-gateway:1.1 sentinel-anchor_ccaas_image:latest > offline-bundle/image-inventory.json
mkdir -p offline-bundle/model-vault offline-bundle/fabric-samples
cp -a model-vault/. offline-bundle/model-vault/
cp -a infrastructure/vendor/fabric-samples/. offline-bundle/fabric-samples/
.venv-prepare/bin/python scripts/offline-bundle.py create --directory offline-bundle --private-key infrastructure/runtime/build-private.pem --public-key-output infrastructure/trust/build-public.pem
echo 'Transfer the project, offline-bundle, and the separately trusted build-public.pem to the disconnected Ubuntu machine.'
