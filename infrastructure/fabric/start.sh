#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
network="$root/infrastructure/vendor/fabric-samples/test-network"
[[ -x "$network/../bin/peer" ]] || { echo 'Prepare the offline bundle on a connected workstation first.' >&2; exit 1; }
docker info >/dev/null
cd "$network"
export PATH="$network/../bin:$PATH"
export FABRIC_CFG_PATH="$network/../config"
export CORE_PEER_LOCALMSPID=Org1MSP
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_ADDRESS=localhost:7051
export CORE_PEER_TLS_ROOTCERT_FILE="$network/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
export CORE_PEER_MSPCONFIGPATH="$network/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp"
export IMAGE_TAG=2.5.12 CA_IMAGE_TAG=1.5.15
if [[ ! -f organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp/signcerts/cert.pem ]]; then
 ./network.sh up createChannel -ca -c sentinel -i "$IMAGE_TAG" -cai "$CA_IMAGE_TAG"
fi
# Use a prebuilt image. Offline startup never performs npm install or docker build.
if ! peer lifecycle chaincode querycommitted -C sentinel -n sentinel-anchor >/dev/null 2>&1; then
 ./network.sh deployCCAAS -c sentinel -ccn sentinel-anchor -ccp "$root/infrastructure/fabric/chaincode" -ccv 1.0 -ccs 1 -ccaasdocker false -ccep "AND('Org1MSP.peer','Org2MSP.peer')"
fi
package_id="$(peer lifecycle chaincode calculatepackageid sentinel-anchor.tar.gz)"
for org in 1 2; do
 if docker inspect "peer0org${org}_sentinel-anchor_ccaas" >/dev/null 2>&1; then
  docker start "peer0org${org}_sentinel-anchor_ccaas" >/dev/null
 else
  docker run -d --name "peer0org${org}_sentinel-anchor_ccaas" --network fabric_test --restart unless-stopped --read-only --cap-drop ALL --security-opt no-new-privileges --tmpfs /tmp \
   -e CHAINCODE_SERVER_ADDRESS=0.0.0.0:9999 -e CHAINCODE_ID="$package_id" -e CORE_CHAINCODE_ID_NAME="$package_id" sentinel-anchor_ccaas_image:latest
 fi
done
echo 'Fabric channel sentinel and two-organization anchor contract started.'
