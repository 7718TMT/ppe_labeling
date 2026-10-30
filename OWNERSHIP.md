# Ownership

**This software is owned by De Heus LLC.**

It was produced as an RMIT University capstone project with De Heus LLC as the
industry partner. At handover, ownership of the project's source code in this
repository rests with De Heus LLC. Third-party code, models and data retain
their applicable ownership and license terms.

| | |
| :--- | :--- |
| Owner | De Heus LLC |
| Origin | RMIT University capstone project, De Heus LLC as industry partner |
| Technical contact | Ethan Phuc (Nguyen Trong Phuc), Information Technology — [ethan.phuc@deheus.com](mailto:ethan.phuc@deheus.com) |
| Current checkout | Commit `4d2ea6fc58f9`, branch `inference`; includes uncommitted handover documentation changes |
| Handed over at | `VERIFY:` record the final handover commit and branch |

## What this document is, and is not

This is a statement of ownership for repository readers. It is **not a license
grant**. No project `LICENSE` file has been added; this handover does not draft
one on De Heus's behalf or override third-party licenses.

`VERIFY:` whether De Heus wants a formal `LICENSE` file, and whether the RMIT
capstone arrangement has student IP assignment paperwork to reference here.

## What is covered

The project's source code, configuration, migration and maintenance scripts,
tests, and documentation for the PPE, Sign and Behavior labeling/inference tool.
Training and model evaluation are separate workflows; see [README](README.md).

## Models, data and credentials

- **Model weights are tracked here.** The current Git inventory includes
  `weights/ppe.pt`, `sign.pt`, `pose.pt`, `reid.pt` and `behavior.joblib`.
  Confirm each artifact's provenance, redistribution rights and license with
  its supplier. This ownership statement does not assign third-party model rights.
- **Local datasets and workspaces** are excluded by the configured Git ignore
  rules. Arrange any required images, videos, labels or workspace backups
  separately. Data-use rights must be confirmed for each supplied dataset.
- **Credentials:** `.env` is ignored and `.env.example` supplies development
  defaults. No full-history secret scan has been performed as part of this
  documentation work; this file makes no claim that secrets were never committed.

## Third-party licenses — one item needs a decision

The following selected backend versions and license labels were read from the
installed package metadata in the repository-root `.venv`, not copied from the
dashboard handover. This is not a complete dependency/license audit. Backend
dependencies are declared in `pyproject.toml`/`uv.lock`; frontend dependencies
are declared in `frontend/package.json` and its lockfile.

| Dependency | Installed version | License reported by package metadata |
| :--- | :--- | :--- |
| **ultralytics** | **8.4.61** | **AGPL-3.0** |
| torch | 2.12.0+cu132 | BSD-3-Clause |
| torchvision | 0.27.0+cu132 | BSD |
| scikit-learn | 1.7.2 | BSD-3-Clause |
| xgboost | 3.3.0 | Apache-2.0 |
| opencv-python | 4.13.0.92 | Apache 2.0 |
| fastapi | 0.136.3 | MIT |
| uvicorn | 0.49.0 | BSD-3-Clause |
| pydantic-settings | 2.14.1 | MIT |
| joblib | 1.5.2 | BSD 3-Clause |
| lap | 0.5.13 | BSD-2-Clause |
| onnxruntime | 1.23.2 | MIT License |
| pyarrow | 21.0.0 | Apache Software License |

**Ultralytics is a core dependency**, used for PPE/sign detection and pose
estimation. Its [version-specific license](https://github.com/ultralytics/ultralytics/blob/v8.4.61/LICENSE)
is AGPL-3.0, a copyleft license with provisions covering remote network
interaction with modified software. The applicability to this system and its
intended deployment needs review by De Heus's legal function.

De Heus should decide whether to comply with the applicable AGPL terms, obtain
an [Ultralytics commercial license](https://www.ultralytics.com/license), or
replace the dependency. Raise this before deployment beyond internal evaluation;
internal use is not itself a license clearance. This records a dependency issue,
not a conclusion about De Heus's legal obligations.

`VERIFY:` whether De Heus already holds a commercial license covering this use.

## Attribution

Parts of this codebase and its documentation were written with AI assistance,
including OpenAI Codex. This disclosure does not grant a license to the project.
