# SentinelCV 360 — integration release 1.1

A private assurance workspace with User, Client and Admin accounts, native local CV execution, signed inference records, dataset scans, cases and reports. The Ubuntu stack includes Keycloak OIDC, PostgreSQL/pgvector/TimescaleDB, MinIO, Redis/Celery, Prometheus/Grafana and a Hyperledger Fabric Gateway/contract.

Seven pretrained engines and the native signed-inference path ran successfully on CPU. Keycloak HTTPS sign-in, account provisioning and role enforcement also passed. **The full container stack and live Fabric network have not passed acceptance here. This release does not complete every section of the original production specification.** See `docs/coverage-matrix.md`, `docs/validation.md` and `docs/production-acceptance.md`.

## Accounts

| Account type | Permissions |
|---|---|
| User | Investigations, assessments, evidence and analyst recommendations |
| Client | Submissions and records linked to that client's contributor identity |
| Admin | Accounts, policies and approval of reference datasets/models |
| Supervisor | Separate approval of analyst recommendations |
| Operator / Auditor | Operational inference / read-only audit access |

The private Site first asks its owner to create an Admin username and password. Admin can then create User and Client accounts in Administration. The Site retains its existing private ChatGPT access gate. Selecting an account type never changes a stored account's permissions.

Local password setup creates separate accounts, including `user`, `client` and `admin`, and prints new passwords once. No shared default passwords are included. Keycloak stack accounts require OTP enrollment; passwords are generated in a private runtime file.

## Lightweight Ubuntu profile

Use Node 24+, Python 3.11+ and pnpm. Installation needs connected preparation or preinstalled dependencies.

```bash
corepack pnpm install --frozen-lockfile
python3 -m venv .venv
source .venv/bin/activate
pip install -r local/requirements.txt
python local/setup.py
npm run build:local
uvicorn local.api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Sign in as User or Admin and choose **Initialize baseline** to run the synthetic assurance demonstration. Sign in separately as Supervisor for final case approval. Development UI: `npm run dev:local` at http://127.0.0.1:5173.

## Native pretrained CV profile

Extract `SentinelCV_Pretrained_Model_Vault.zip` into the project root. It supplies the `model-vault` directory with seven real pretrained engines, processor files and an inventory of SHA-256 hashes. Before using supplied media, verify its signature with the separately supplied project key:

```bash
pip install -r local/requirements-stack.txt
python scripts/offline-bundle.py verify --directory model-vault --trusted-key docs/model-vault-public.pem
pip install torch==2.8.0 torchvision==0.23.0 --index-url https://download.pytorch.org/whl/cpu
pip install -r local/requirements-ml.txt
export SENTINEL_SERVICE_TOKEN="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export SENTINEL_AI_URL=http://127.0.0.1:8768
export SENTINEL_MODEL_DIR="$PWD/model-vault"
uvicorn local.ml.service:app --host 127.0.0.1 --port 8768 &
uvicorn local.api:app --host 127.0.0.1 --port 8000
```

These installation commands run on the connected preparation workstation. Installed model execution refuses network requests and uses only local weights.

In Administration, pin a reviewed dataset baseline and an installed pretrained model. Assess the model, then select an accepted model in Inference integrity. DINOv2 and OpenCLIP power embedding and label-anomaly scans; YOLO11n and RT-DETR produce detections; Mask2Former produces segmentation; ResNet18 and ConvNeXt-Tiny produce classifications. Model scores are not validated field assurance probabilities.

For uploaded ONNX/TorchScript models, select their task, classes, input size and declared dataset. Admin must pin a reviewed uploaded model as a signed reference before assessment and operational execution. Supported tensor contracts and safe PyTorch architectures are documented in `docs/model-adapters.md`.

## Full offline service stack

`infrastructure/prepare-offline.sh` builds and saves images and prepares signed dependencies on a connected workstation with Docker. `infrastructure/start-offline.sh` verifies the separately trusted bundle, loads images and starts services without pulling or building. Follow `docs/setup-guide.md` for credentials, TLS, Fabric preparation and target-machine prerequisites. The downloadable model vault is supplied; the Docker image archive must still be built and tested on that workstation.

## Validation

```bash
npm test
python tests/local_api_smoke.py
python tests/oidc_test.py
python tests/portable_ml_smoke.py
python tests/native_ml_smoke.py
```

The last two commands require ML dependencies; the final one also requires the supplied model vault. Native Keycloak/Fabric smoke harnesses are included with explicit distribution-path arguments. See their usage and the recorded JSON results under `docs`.
