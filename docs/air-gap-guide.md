# Air-gap guide

The published Site is cloud-hosted and is not air-gapped. Use the local profile for network-independent core evaluation.

Prepare Node, Python, installed dependencies, offline-dist and the included demo-assets on an authorized connected workstation. Transfer the complete prepared environment through your approved process. No weights, fonts, authentication APIs or CDNs are fetched by the running local core. Local HTTP between the browser, FastAPI and the analysis engine is expected.

The archive contains source, built frontend assets and synthetic test fixtures. It does not contain Node/Python binaries, node_modules, a wheelhouse, pretrained weights, container images or operating-system packages. It is therefore not a complete bootstrappable air-gap appliance by itself.

After installation, disconnect external networking on your own evaluation machine. Start Uvicorn and run every step in demo-guide.md. Verify login, ZIP upload, scans, model hashes, inference, verification, tampering, replay, drift, graph traversal, case governance, signed PDF, package reimport, benchmarks and audit. Record the machine, versions, network state, results and logs. An actual network-disconnected operating-system validation has not been executed in this build environment.

The full requested on-premises stack and pretrained detectors remain unintegrated. Do not mark the entire specification DEMO READY until those integrations and the complete disconnected acceptance test pass.
