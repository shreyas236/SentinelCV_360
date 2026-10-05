# Ubuntu setup and offline preparation

## Password and native CV profiles

Run README commands from the project root. `local/setup.py` preserves existing credentials and adds the User/Client/Admin aliases. Set `SENTINEL_USER_PASSWORD`, `SENTINEL_CLIENT_PASSWORD` or `SENTINEL_ADMIN_PASSWORD` before first provisioning to choose passwords. Admin can create more accounts in Administration. Password reset/rotation is not yet provided by the workspace; use Keycloak account management in the stack profile.

The default data directory is `local-data`. Set `SENTINEL_DATA_DIR` to a protected absolute path to move it. Users/configuration are mode 0600 and the directory is mode 0700. Keep these private files out of source packages. FastAPI starts a token-protected Node engine on 127.0.0.1:8766. The AI worker is separately authenticated with `SENTINEL_SERVICE_TOKEN`; keep its listener on loopback in the native profile.

Install the supplied model vault, verify it against `docs/model-vault-public.pem`, and use the README ML commands. All seven engine files are supplied separately from the small project ZIP. To prepare a different vault on a connected station, run `python scripts/prepare-models.py --output model-vault` using the ML environment. Review and sign that release before importing it. No downloader runs during inference.

Uploaded ZIP datasets are limited to 10 MB compressed, 32 MB expanded, 250 entries and 100 decoded images. Individual images are limited to four megapixels. Workspace model uploads are limited to 8 MB; large pretrained weights use the administrative local vault. YOLO/COCO boxes and ImageFolder labels are parsed. Arbitrary segmentation annotation formats and continuous video are not supported.

## Connected stack preparation

Use an Ubuntu x86-64 preparation workstation with Python 3.11+, the cryptography package, Docker Engine, Docker Compose v2, curl, tar, jq and adequate disk/RAM. These host prerequisites must already be installed on the disconnected target; the source package is not an operating-system installer. Native AI CPU memory is limited to 8 GB per child and the container to 9 GB; reserve additional memory for all other services.

```bash
python3 -m venv .venv-stack
source .venv-stack/bin/activate
pip install -r local/requirements.txt -r local/requirements-stack.txt
python infrastructure/init-stack.py --url https://localhost:8443
bash infrastructure/prepare-offline.sh
```

For LAN access, choose the real HTTPS hostname in `--url` and set `SENTINEL_BIND_ADDRESS` in `infrastructure/.env` to the intended protected interface. The generator creates a local CA/server certificate, private random service secrets, Keycloak realm and account credentials, and preserves existing secrets. Trust `infrastructure/runtime/tls/ca.crt` on authorized clients. Keep `ca.key` in protected offline custody. Replace demonstration PKI with organizationally governed certificates before production acceptance.

The preparation script builds API, AI and Gateway images, downloads pinned Fabric sample source and Fabric 2.5.12 binaries, saves all required images, prepares the local model vault, and signs an exact offline-bundle file inventory. It records image IDs/digests in `offline-bundle/image-inventory.json`. Resolve any build or image availability failures while connected; this preparation has not run in the current environment because Docker is absent.

## Disconnected startup

Transfer the project, `offline-bundle`, and confidential `infrastructure/.env`/runtime configuration to the target. Transfer and verify the release public key independently, then place it at `infrastructure/trust/build-public.pem`. A key found inside untrusted media alone does not establish trust.

```bash
python scripts/offline-bundle.py verify --directory offline-bundle --trusted-key infrastructure/trust/build-public.pem
bash infrastructure/start-offline.sh
```

Startup uses image loading and `--no-build --pull never`; it does not install packages. The application opens at the HTTPS URL selected during initialization. The Keycloak account passwords are in the private `infrastructure/runtime/credentials.json`; the first interactive sign-in requires OTP setup. Identity roles are fixed and client contributor IDs are administrator-managed profile attributes.

Fabric startup creates the sample two-organization channel using local CAs and prebuilt chaincode-as-a-service images, with both organizations required to endorse. This sample is a runnable integration fixture, not independent production organizations. The Gateway submits real transactions and reports a receipt only after successful commit/readback. The first service Ed25519 key is pinned in the contract; replacing it requires a governed ledger migration.

Use `docker compose --env-file infrastructure/.env -f infrastructure/compose.yml ps` and service logs to inspect startup. The reverse proxy exposes HTTPS only; databases/workers remain on the internal service network. Connected preparation rewrites the pinned Fabric Compose network as internal and binds its required host ports to loopback. Keep outbound networking disabled during the acceptance sequence in `docs/production-acceptance.md`.

The complete container startup, PostgreSQL/MinIO/Redis integrations, interactive OTP and disconnected acceptance remain unvalidated. Do not mark a configuration as passing until those runtime checks succeed.
