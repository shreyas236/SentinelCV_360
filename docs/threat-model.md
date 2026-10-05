# Threat model

Threat actors include a malicious contributor, compromised model vendor, external attacker, insider, compromised sensor and compromised update source. The prototype provides bounded ingestion, deterministic identity checks, signed outputs, persistent replay gates, audit verification and role enforcement. It does not establish operating-system, hardware or firmware integrity.

Trust boundaries are: browser to authenticated API; external bytes to bounded ingestion; storage to detector rereads; accepted model identity to inference; manifest to signature verifier; analyst identity to supervisor identity; and evidence package to pinned local trust key. Hosted role switching exists only under the private Site owner's authentication boundary and is unsuitable as independent-person governance.

Protected assets include artifact bytes, reference hashes, model/config/runtime records, private keys, sessions, evidence, cases, policies, audit and reports. Software private keys are encrypted at rest with a server-held wrapping secret. If both the database and secret are compromised, the encryption provides no further protection. Public keys embedded in imported evidence packages are not accepted as trust roots; they must match the workspace's pinned active key.

No pickle or executable model checkpoint is loaded. No archive file is executed. Dataset parsing checks traversal, symlinks, duplicate entries, bounds, image format, decompression size and allowed extensions before decoding.
