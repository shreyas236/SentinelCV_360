# Remaining production acceptance

The requested integrations are now implemented in source. Seven native CV engines, portable formats and Keycloak sign-in have run. The checks below are still required on an Ubuntu workstation with Docker before the full offline deployment can be accepted.

1. Run connected preparation, inspect every built image and pinned model/source revision, and verify the independently trusted release signature. Produce the full transitive/container SBOM and retain immutable inventory outside the application database.
2. Start the complete Compose stack and two-organization Fabric network. Confirm all services, schema extensions, versioned MinIO objects, shared account sessions and internal service authentication. Confirm the Fabric bridge is internal and only the intended TLS interface is exposed.
3. Complete first-login OTP enrollment for User, Client, Admin and Supervisor; validate lockout, distinct approval identities, contributor ownership, sign-out, expired/replayed OIDC state and unavailable identity service. Configure and test LDAP only if required by the intended deployment.
4. Run approved dataset/model ingestion, all seven native engine tasks, four portable format contracts, identity-change rejection, signed inference verification, replay/tamper rejection, queue ownership and report/package verification through the deployed HTTPS UI/API.
5. Sign a Merkle root and require successful endorsement by both Fabric organizations, committed transaction status and a matching ledger readback. Retry idempotently, reject modified digests/signatures, then verify audit prefix roots against Fabric. Test unavailable peers and ledger mismatch without producing a false confirmation.
6. Exercise PostgreSQL atomic sequence allocation under concurrent requests, Redis/Celery recovery, MinIO persistence/restarts, vector retrieval and Timescale inserts. Verify Prometheus/Grafana show actual collected values and alert on failed services.
7. Disable outbound network access at the OS/router, restart all services using only prepared images/media, and repeat login, CV, queue, ledger and report workflows. Capture evidence that no dependency/weight/image download occurs. Confirm missing or modified local artifacts fail rather than being fetched.
8. Validate independent clean/attack field datasets, thresholds, calibration, task accuracy, load/latency, memory limits and parser isolation. Synthetic smoke tests cannot substitute for these measurements.
9. Implement and test governed key rotation, organizational Fabric PKI, signed atomic updates/rollback, encrypted backups/restore, disaster recovery, sensor/video adapters and any remaining original specification sections required for the intended production use.

This checklist records unfinished acceptance, not successful results. Do not remove a gap from the coverage matrix without reproducible runtime evidence.
