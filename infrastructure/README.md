# Infrastructure configuration

compose.services.yml describes a starting support-service environment. These services are not used by the implemented prototype, have not been started or tested here, and do not satisfy the requested full production stack. Set every required secret in your own protected environment. No credentials are committed. Acquire and verify container images before transferring them into a disconnected environment; internal: true prohibits external network access after startup.

TimescaleDB, MinIO application adapters, Keycloak realm/client/RBAC integration, Celery routing, metrics collectors and Hyperledger Fabric are pending. The file intentionally does not claim a complete offline deployment or substitute placeholder Fabric peers for a working network. Use the local npm/Uvicorn profile in README.md for the tested implementation.
