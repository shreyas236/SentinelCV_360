# Declared limitations

Version 1.1 adds working pretrained CV and portable model execution, account administration and native Keycloak sign-in. Infrastructure adapters and deployment scripts are present. It remains an assurance prototype with unvalidated production boundaries.

- The complete Docker stack, PostgreSQL/pgvector/TimescaleDB, MinIO, Redis/Celery and provisioned monitoring have not been executed together in this environment. Docker is unavailable here.
- Fabric contract tests pass, and the real Gateway/chaincode/network startup code is included. Native peer startup failed because this execution environment denies netlink route inspection. No successful live ledger commit is claimed. The sample Fabric CA/network is a test fixture, not independent production organizations.
- Keycloak HTTPS code/PKCE login, signed tokens, fixed roles, client provisioning and logout redirect passed against a real 26.4.7 server with its development database. Interactive OTP, LDAP and the PostgreSQL-backed Keycloak deployment remain unvalidated.
- ONNX/TorchScript support documented tensor contracts, not arbitrary export layouts. PyTorch state dictionaries are restricted to three known classification architectures; arbitrary pickled Python models are rejected. Uploaded models have an 8 MB limit; large approved pretrained weights use the local vault.
- Python CPU/memory/time limits and network audit hooks are present. Hostile native model parsers require the additional container/OS boundary and security review. No secure-enclave, GPU, container/hardware attestation or comprehensive adversarial sandbox validation is claimed.
- Pretrained smoke tests used synthetic images on CPU. They demonstrate real execution and signed provenance, not field-data accuracy, attack recall, production calibration or operational suitability. GPU execution was not tested.
- DINOv2/OpenCLIP scores, Mahalanobis/KNN, STRIP, activation/spectral analysis and bounded Neural Cleanse-style reconstruction require independent clean baselines and calibrated thresholds. Default assessment does not enable reconstruction; an explicit deep-analysis request is required; arbitrary-trigger coverage is incomplete.
- Learned fusion/SHAP, trained drift cause attribution, physical cameras, RTSP/ONVIF/MAVLink, thermal/drone adapters and continuous video/frame-order telemetry remain pending.
- Signed media verification is implemented. Atomic signed software updates/rollback, malware scanning, encrypted versioned backups and verified restore remain pending. A full transitive/container SBOM and independent release-key governance are also required.
- Browser interaction QA, production load/scale, multi-organization tenant governance and complete network-disconnected Ubuntu acceptance have not been performed.

Statistical anomalies do not establish malicious intent. The RGB classifier and measured synthetic calibration are meaningful only for the included color-card fixtures. The 12×12 corner detector does not cover arbitrary or semantic triggers. Native embedding scan coverage is bounded and reported; missing analysis stays unavailable.

Hash mismatches, invalid signatures and replay remain deterministic failures. A compromised host, service key, reference authority or database can undermine software custody. Signed local roots alone are not external immutable proof; the Fabric result is trusted only after successful commit/readback. Verification reports external unavailable/mismatch states explicitly.
