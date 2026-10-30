# Known limitations

These are application limitations observed in the current source. Installation
acceptance results and model accuracy must be recorded separately.

| Area | Current behavior and operational implication |
|---|---|
| Access control | API routes have no application authentication/authorization. A client with backend access can invoke data-changing endpoints. CORS does not provide access control. Use a trusted local environment; shared deployment requires an access-control design. |
| Runtime | The documented launcher runs FastAPI, a persistent video worker and Vite locally. Production hosting, service supervision and identity integration need separate deployment work. |
| Platform support | The locked macOS PyTorch wheels target Apple Silicon/macOS 14+; Intel Mac is not covered. Device selection supports CPU/CUDA, not MPS. Linux/macOS end-to-end validation remains to be performed; see [platform notes](OPERATIONS.md#platform-notes). |
| Label quality | AI predictions and generated initial Behavior timelines can be wrong. Editable generated segments exist before review; inspect all labels before approval. Approval is a workflow state, not measured accuracy. |
| Image exports | Export All is not an approved-only dataset. Missing labels are represented by empty text files; these must not be assumed to be reviewed negative examples. |
| Model artifacts | Auto-labeling and inference require the corresponding compatible local models. Artifact provenance, license and class/feature contract must be supplied by the model owner. |
| Trusted serialized models | Joblib/pickle loading can execute code. Only load explicitly trusted artifacts; the external video-model API requires trusted-local confirmation. |
| Storage | SQLite alone is not a complete backup: media, labels, pose/features and other large artifacts live on disk. SQLite WAL requires a proper backup or a clean stop before copying. |
| Image approvals | Only current approval state is retained; there is no image-approval audit history. Video annotation history is a separate mechanism. |
| Image rename/delete | Filesystem and SQLite operations are not one distributed transaction. Unexpected failure can leave a partial operation or `.renaming` files; inspect and reconcile as described in operations. |
| Filenames | Manually added images with the same stem but different extensions conflict because label keys use the stem. Mutable/export workflows reject these conflicts. |
| Video export | Only included, approved videos contribute. Missing windows/features can block export; unresolved or excluded windows can reduce the exported samples. Review validation warnings. |
| Throughput | Video processing depends on duration, resolution, hardware, tracking and model settings. No hardware-independent processing-time guarantee is provided. |

See [operations](OPERATIONS.md), [data export](DATA_EXPORT.md) and the
[handover checklist](handover/CHECKLIST.md) for handling and outstanding checks.
