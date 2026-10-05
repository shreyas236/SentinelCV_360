# Model adapter contracts

The local AI worker executes real model code in a resource-limited child. It verifies model bytes before loading, uses offline Hugging Face APIs with remote code disabled, and denies Python network/subprocess calls. The Docker worker adds a read-only filesystem, no capabilities and an internal network. Python audit hooks alone are not an OS security boundary against hostile native libraries.

| Adapter | Supported execution |
|---|---|
| DINOv2 Small | Normalized 384-dimensional embeddings |
| OpenCLIP ViT-B/32 | Image embeddings and supplied text-label probabilities |
| YOLO11n / RT-DETR R18 | Object detections with source-image xyxy boxes, class and confidence |
| Mask2Former Swin Small | Semantic segmentation derived from pretrained instance model output; uint16 NumPy mask and per-class pixel counts |
| ResNet18 / ConvNeXt-Tiny | 1,000-class pretrained classification |
| PyTorch state dictionary | ResNet18, ResNet50 or ConvNeXt-Tiny; declared class count; `weights_only=True`, strict state keys |
| ONNX / TorchScript | The four explicit portable tensor contracts below |

For portable models the single input is float32 NCHW `[1,3,S,S]`, where S is the declared input size (16–2048). Images are resized, divided by 255, then normalized with ImageNet mean `[0.485,0.456,0.406]` and standard deviation `[0.229,0.224,0.225]`. Models trained with another preprocessing contract must be exported accordingly. ONNX external data, multiple inputs/outputs, non-finite outputs and unsupported shapes are rejected.

| Task | Required output |
|---|---|
| Classification | `[1,C]` logits, C equals the declared class names; softmax applied |
| Detection | `[1,N,6]`, N ≤ 1,000; each row is input-pixel x1, y1, x2, y2, score, integer class ID. Coordinates/classes/scores are validated; boxes are rescaled and scores below 0.25 omitted |
| Segmentation | `[1,C,H,W]` logits; C equals declared classes and H/W ≤ 2,048. Resized logits are converted to class masks at source-image size |
| Embedding | `[1,D]`, D ≤ 8,192; L2 normalization applied |

TorchScript may return the tensor directly, a single-element tuple, or a dictionary keyed `logits`, `detections`, `out` or `embedding` for the respective task. These contracts do not decode every vendor-specific export layout. Raw YOLO heads or multiple ONNX output tensors must be exported to this documented layout.

Uploaded candidates stay in review. A reference administrator deliberately pins reviewed bytes into a separate signed snapshot. Assessment recomputes identity and executes candidate/reference probes. Operational inference requires an accepted assessment, matching reference digest and valid signature; edited weights are blocked.

DINOv2/OpenCLIP dataset analysis requires a separately reviewed and signed reference dataset. Sampling limits appear in scan coverage. KNN, Mahalanobis, cosine, CLIP disagreement, embedding MMD/PSI/KS, STRIP entropy and activation scores are uncalibrated statistical evidence. Neural Cleanse-style reconstruction is an optional worker operation limited to differentiable classifiers with at most 20 targets, and is enabled only by an explicit scan request with `deep_analysis: true`. None establishes malicious intent or universal attack detection.

Source URLs, revisions, license labels and file digests are in the vault manifest. New prepared weights create a new release requiring reference review. The supplied model smoke tests use synthetic images and measure execution/integrity rather than accuracy on field imagery.
