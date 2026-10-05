# Validation performed

| Check | Observed result | Practical limit |
|---|---|---|
| Core/ingestion/auth/Fabric contract Node tests | Six passed | Contract execution is in-memory, not a live Fabric network |
| TypeScript and production frontend builds | Passed | Browser interaction QA unavailable |
| FastAPI password/API assurance workflow | Passed | SQLite/filesystem profile |
| Seven pretrained adapters | CPU inference passed for DINOv2, OpenCLIP, YOLO11n, RT-DETR R18, Mask2Former, ResNet18 and ConvNeXt-Tiny | Synthetic inputs, not accuracy measurement |
| ONNX and TorchScript | Four task contracts passed in both formats; uploaded ONNX approval, assessment and signed inference passed | Explicit contract layouts, not every architecture |
| Native signed provenance | Reference pinning, model assessment, native output verification, acceptance, replay/tamper rejection and embedding dataset scan passed | CPU and local API |
| Real Keycloak 26.4.7 | HTTPS code/PKCE, signed JWTs, administrator-created client, contributor identity, RBAC, forged-role rejection and logout redirect passed | Development-file Keycloak database; automated fixture skips OTP enrollment |
| JWT negative checks | Signature, issuer/audience, nonce, expiration and strict role checks passed | Unit checks |
| Signed offline media | Valid bundle, wrong key, byte edits, unmanifested files, path traversal and symlink rejection checked | Media verifier only, not complete offline startup |
| Fabric native network | Orderer/channel initialization reached; peer failed on denied netlink route inspection | No live endorsement/commit claim |
| Container service stack | Configuration and scripts checked | Docker unavailable; no combined service execution |

Recorded ML/identity results are in `native-ml-validation.json`, `portable-model-validation.json` and `keycloak-validation.json`. The core fixture identified two injected corner triggers and four feature-model probe failures; fifteen real synthetic benchmark experiments measured confusion counts and runtime. These are fixture results, not field-performance estimates.

Reproduce with README test commands. The native Keycloak test accepts `--home` for an unpacked 26.4.7 distribution and `--java-home` for Java 21+. The Fabric harness accepts its documented binaries/distribution paths and must run on a machine that permits ordinary peer networking. Neither harness downloads dependencies during its test.

The release is not marked production-ready or complete against the full original specification. Complete the Ubuntu sequence in `production-acceptance.md` before making those claims.
