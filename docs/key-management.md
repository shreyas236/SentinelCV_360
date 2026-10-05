# Key management

ROOT signs custom service, sensor and approval-identity attestations. Ed25519 keys are generated locally, exported only on the server, encrypted using AES-GCM with fresh IVs and stored in key_store. The wrapping key is derived from the protected server secret; raw private keys never appear in ordinary API responses or frontend code.

Administrator can revoke sensor or approval identity keys. Current certificate checks reject inactive/expired keys. Root/service revocation and rotation require a recovery workflow and are blocked rather than performed unsafely. Historical audit verification validates the original signature bytes; current certificate validity is checked separately when accepting live inference or governance decisions.

X.509 CA, CRL/OCSP policies, HSM/TPM custody, key recovery, scheduled rotation and dual-control key revocation are unimplemented. Protect the local configuration and never include local-data in an exported project archive.
