# Offline updates

Version 1.1 implements connected dependency/image preparation and Ed25519 verification of an exact offline-bundle inventory. The verifier uses an independently pinned public key, checks every file hash/size, and rejects symlinks, traversal and unmanifested content. Offline startup loads prepared images and uses pull-never/no-build service startup.

Atomic signed application installation, rollback, malware scanning, dual approval and encrypted recovery remain pending. The bundled build identity covers core/authentication, local Python CV/API and frontend sources. The SBOM records installed direct JavaScript dependencies and declared pinned Python packages; it is not a full transitive/container inventory or independent release attestation.

Production release handling must use a governed build station/release key, trusted media import, signature/dependency verification and malware scanning before installation. Preserve verified image/model inventories independently of the application database. Do not treat a model checkpoint as a software update.
