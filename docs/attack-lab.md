# Attack lab

Available transformations create persisted derived artifacts with actual modified bytes, labels or model parameters. Source records are not replaced. Experiments store seed, parameters, source/modified registry IDs and separately recorded ground truth. Detectors never use that ground truth as a shortcut.

Implemented: label flips, duplicate substitution/flooding, high-contrast corner triggers, RGB OOD, illumination/night, haze/fog, noise, blur, model centroid substitution and a transparent trigger-sensitive feature classifier. Inference controls modify input, output, configuration or signature on its stored artifact, then run the actual verifier. Replay calls the real acceptance gate.

The complete requested threat suite, arbitrary trigger sizes/locations, actual neural-model backdoors, record deletion/reordering lab controls, sensor replacement and attack sweeps are partial or missing. Use the coverage matrix before making any support claim.
