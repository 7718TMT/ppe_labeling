# Handover baseline — current snapshot

Record the measured repository state so handover claims can be checked against
observed results. This snapshot was captured **after** the handover documentation
was committed, not before that work started. It does not reconstruct an earlier
baseline. No application code, dependencies or generated references were fixed
during this capture.

| Field | Observed value |
|---|---|
| Commit measured | `7a533ca63e7565be6a530c16e8686abc24157786` (`7a533ca`) |
| Commit date | 2026-10-30 |
| Commit subject | `[ADD] Handover checklist, documentation, document generation scripts and archive video workspace sync notes` |
| Branch measured | `inference`; no new measurement branch was created |
| Capture window | 2026-10-30 10:29:17–10:30:23 UTC (17:29:17–17:30:23 Asia/Saigon) |
| Platform | Windows 11, build 10.0.26200, AMD64 |
| Working tree before capture | Clean; BASELINE.md and its logs did not yet exist |

Full combined stdout/stderr is retained in [baseline-logs/](baseline-logs/).
Command logs include the actual invocation, working directory, timestamps, exit
code and elapsed time. Absolute capture-machine paths are retained. No content
redactions were applied; `.env` contents were not captured. This is not a
full-history secret scan.
Supplemental read-only inspections (logs 06/07) followed the main capture window.

## 1. Environment

Source: [00-environment.txt](baseline-logs/00-environment.txt).

| Tool / component | Measured version or state |
|---|---|
| Python | 3.12.13; repository-root `.venv/Scripts/python.exe` |
| pytest | 9.0.3 |
| uv | 0.12.23 |
| Node.js / npm | v22.19.0 / 10.9.3 |
| TypeScript / Vite / Vitest | 5.9.3 / 5.4.21 / 4.1.10; installed frontend dependencies |
| PyTorch / torchvision | 2.12.0+cu132 / 0.27.0+cu132 |
| CUDA | Build 13.2; `torch.cuda.is_available()` returned True |
| GPU / driver | NVIDIA GeForce RTX 5060 Ti / 610.88 |
| Ultralytics / scikit-learn / XGBoost | 8.4.61 / 1.7.2 / 3.3.0 |
| Ruff | Not installed in the project venv; no Ruff configuration in pyproject or root Ruff config files |
| Frontend lint | No `lint` script or ESLint configuration found |

Backend commands used the project venv directly. Node commands used the existing
`frontend/node_modules`; npm scripts were invoked through Node and `npm-cli.js`
on this Windows machine. No dependency installation or lockfile update occurred.

## 2. Results

Commands below use equivalent portable invocations; logs retain the absolute
commands actually executed. Working directories are relative to the repository.

| # | Command | Working dir | Exit | Observed result | Log |
|---|---|---|---|---|---|
| 1 | `uv run --frozen --no-sync python -m pytest -q` | root | 0 | 146 passed, 1 warning; pytest reported 21.22 s | [01](baseline-logs/01-backend-pytest.txt) |
| 2 | `node node_modules/typescript/bin/tsc --noEmit` | `frontend/` | 0 | No output; no type errors | [02](baseline-logs/02-frontend-tsc.txt) |
| 3 | `npm run test` | `frontend/` | 0 | 106 tests passed in 23 files; Vitest reported 19.46 s | [03](baseline-logs/03-frontend-tests.txt) |
| 4 | `npm run build` | `frontend/` | 0 | TypeScript + production build passed; Vite reported 4.81 s | [04](baseline-logs/04-frontend-build.txt) |
| 5 | `uv run --frozen --no-sync python -m backend.scripts.generate_docs --check` | root | 1 | CONFIGURATION.md, API.md and DATABASE.md reported out of date | [05](baseline-logs/05-generated-docs-check.txt) |
| 6 | Local Markdown link audit (full script in log) | root | 1 | One missing target in the existing checklist | [07](baseline-logs/07-local-links.txt) |

Backend/frontend lint was **not run**: no configured lint workflow was available
in this environment. This is not a clean lint result. Tests and checks ran
sequentially; runner timings above differ from wrapper elapsed times in logs.

## 3. Findings

- **Backend:** all 146 tests passed. One Starlette deprecation warning concerns
  HTTPX use in TestClient; it is retained in log 01.
- **Frontend tests:** all 106 tests passed, but jsdom printed unimplemented
  canvas/media messages (`getContext`, `pause`, `load`). Passing these tests is
  not evidence that real browser video playback was exercised.
- **Build:** the main minified JavaScript chunk was 573.54 kB, above Vite's
  500 kB warning threshold. The build still exited 0; no bundle changes were made.
- **Generated docs:** all three reference notices identify commit
  `4d2ea6fc58f9`; the current generator expects `7a533ca63e75`. A read-only diff
  confirmed that only this commit stamp differs; content outside the generated
  notice is identical. See [06-generated-docs-diff.txt](baseline-logs/06-generated-docs-diff.txt).
  The exit-1 result was left untouched. Because the generator stamps HEAD, a
  later commit can trigger this check even without reference-content changes.
- **Document link:** CHECKLIST.md links to `EMAIL_TEMPLATE.md`, which is absent
  from the measured checkout. The read-only audit records the missing target
  in [07-local-links.txt](baseline-logs/07-local-links.txt); it was not repaired.

## 4. Comparison and caveats

- Earlier focused test counts in the documentation work are subsets, not a
  previous full-suite baseline. Do not infer regressions from those totals.
- This was an in-place Windows run, not a fresh clone or Linux/macOS validation.
  Installed versions above can differ from version ranges in package.json.
- A local ignored `.env` and model weights were present. Application Settings
  can load `.env`, including on import; tests override paths/dependencies in
  many cases. This capture does not establish independence from local settings
  or successful installation without the existing environment.
- Tests include temporary SQLite/media fixtures and mocked model paths. No
  full real-video labeling pilot, model-accuracy evaluation, GPU throughput
  benchmark, CPU-only run or backup/restore exercise was performed here.
- No application server or user-run process was stopped/restarted. Build/cache
  artifacts may have changed; the five main checks did not change Git-tracked files.
- One run per check; no repeated-run flakiness claim is made. A future failure
  should be investigated before being classified as a regression.

## 5. Reproduce

Use the measured commit in a separate checkout with matching dependencies and
configuration. Do not overwrite an active workspace. Follow [README](../../README.md#install)
for the OS-specific setup; a fresh install is a separate validation from this
in-place snapshot. In PowerShell, Bash or Zsh, from the repository root:

```sh
uv run --frozen --no-sync python -m pytest -q
uv run --frozen --no-sync python -m backend.scripts.generate_docs --check
cd frontend
node node_modules/typescript/bin/tsc --noEmit
npm run test
npm run build
```

`--frozen --no-sync` reuses an already installed environment without updating
the lockfile or syncing packages. Compare counts, warnings and exit codes, not
machine-dependent durations. To repeat the historical doc check, use the
measured HEAD: checking at a different commit changes its expected stamp.
