# Annotation tool handover checklist

Scope: install, operate, annotate, export and restore the application. Training
code, dataset splitting, model evaluation and dashboard deployment are separate
deliverables. Use this checklist to verify the receiving installation.

## 1. Receive and identify

- [ ] Record repository URL, branch and exact commit, sender and recipient.
- [ ] Confirm the configured model files are present, including `weights/reid.pt`
  for video tracking. Ask the sender for any missing files.
- [ ] Confirm source/data/model access rights with [OWNERSHIP.md](../../OWNERSHIP.md).
- [ ] Decide whether this is a clean installation or a restoration of existing
  work; a training export does not contain the complete workspace.

## 2. Install and configure

- [ ] Follow your OS/shell instructions in [README](../../README.md#install): Python 3.12, uv, Node.js, `uv sync`,
  frontend dependencies, and `.env.example` copied to `.env`.
- [ ] Review [CONFIGURATION](../CONFIGURATION.md), model paths and class maps.
- [ ] Check CPU/CUDA using [operator diagnostics](../OPERATIONS.md#troubleshooting). Record the actual
  environment; do not change quality settings to make the acceptance run faster.
- [ ] Use the OS-specific [port checks](../OPERATIONS.md#port-checks) for 8000/5173. If occupied, identify the owner; do not terminate
  someone else's process. Restrict access to a trusted local environment.

## 3. Verify on disposable sample data

- [ ] Launch with `uv run python -m backend.scripts.start_app` (PowerShell, Bash or Zsh).
- [ ] Complete one PPE and one Sign image cycle: import, edit, save, reopen,
  approve and export; inspect image/label filenames and class IDs.
- [ ] Where the corresponding model is supplied, test AI labeling and review
  its output. Record missing optional artifacts as unavailable capabilities.
- [ ] Complete one Behavior sample: import, wait for processing, review/edit
  worker labels, approve, validate, create export and inspect the ZIP contents.
- [ ] If inference is included in the inventory, test it separately from labeling.

## 4. Preserve and restore

- [ ] Follow the [backup/restore procedure](../OPERATIONS.md#handover-backup-and-restore).
- [ ] Restore into a separate disposable installation, with distinct ports and
  paths, or stop only the test instance before checking the restored copy.
- [ ] Verify image labels, image approvals, video timeline, approvals and media
  still open. Confirm the worker starts without missing-artifact errors.

## 5. Accept and transfer responsibility

- [ ] Review [KNOWN_LIMITATIONS](../KNOWN_LIMITATIONS.md), unresolved items,
  artifact suppliers and the separate training-team contact.
- [ ] Share test results and unresolved issues with the recipient. Confirm
  company repository/access arrangements separately.