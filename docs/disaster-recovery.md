# Disaster recovery

Encrypted, signed versioned backup and verified restore are NOT STARTED. During prototype development, stop Uvicorn and its child engine before taking an operator-controlled copy of the protected local-data directory. This is a manual development snapshot, not the required assurance-grade backup workflow. It includes credentials and the wrapping secret and must be protected separately from source artifacts.

Production recovery must validate database state, object identities, audit chain, externally preserved anchors, certificates, reference signatures and approved policy before reenabling inference. Include PostgreSQL, object storage, reference vault, policies, ledger metadata, reports and recovery-key governance in the full service stack.
