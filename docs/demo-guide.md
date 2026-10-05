# Demonstration guide

Use README.md's eight-step workflow. The initial clean reference is 40 reproducible GREEN, BLUE and AMBER test cards and a real RGB centroid classifier. It is not a pretrained object detector.

For trigger testing, choose the clean dataset, TRIGGER, 5% and seed 47321. The transformation selects two samples and alters their bottom-right pixels. Scanning runs the contrast detector on stored bytes and builds findings/evidence. Ground truth is kept in the attack experiment and is not supplied to the detector. Inspect image thumbnails and the measured corner regions.

Model substitution mutates a centroid in a copied JSON model, changing actual bytes. The model scanner compares its recomputed hash to the immutable approved reference and executes thirty independently generated probes. A trigger-sensitive model routes high-contrast patches to a target class; the probe battery measures actual disagreement. Both remain quarantined and cannot be selected for operational inference.

Run the clean model on the clean dataset. Verify, accept the record once, and then replay it. Verification alone is repeatable; acceptance consumes the nonce. Change output, input, config or signature on a copied record, then rerun verification to identify the failed component. Original signed manifests are retained as evidence.

For drift, use FOG or NIGHT at 100% to represent a change across the current acquisition window. Compare against the clean dataset and inspect brightness, contrast, Laplacian, KS and RBF MMD. Drift cause attribution is a feature rule, not a trained causal model, and does not establish an attack.

Trace contributor-to-batch-to-dataset-to-model-to-inference in the graph. Select a node or calculate impact. Counts come from actual stored edges. Open a finding as a case, record evidence, recommend quarantine, and use the supervisor account for final approval. Generate and download a signed PDF and .sentinel package; reimport it. Altering report.pdf inside the package causes verification to fail.

Run benchmarks at 1/2/5/10/20% for trigger, label flip and OOD on 100 actual generated images per condition. Show confusion counts and runtime. State clearly that these are synthetic tests, not field performance. Finish by verifying the audit and signing its Merkle root. In the full local stack, require a committed Fabric receipt and ledger readback; on the hosted workspace, anchoring is a signed local root only.

For the native CV demonstration, sign in as Admin, pin a reviewed dataset baseline and installed pretrained reference, assess it and run signed inference. Uploaded ONNX/TorchScript models require explicit task contracts and Admin reference approval. See README and model-adapters.md.
