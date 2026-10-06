# Validation Record

This record separates executable local evidence from simulator plans. Generated logs, coverage
artifacts, reports, and checkpoints are intentionally ignored; the commands below reproduce them.

## Prior validation record (retained)

The following environment and results were recorded before the reliability update below.
They are historical claims, not a substitute for current CI.

### Validation environment

- macOS 26.5.2 on arm64
- Python 3.10.14
- NumPy 2.2.6, Gymnasium 1.3.0
- Stable-Baselines3 and SB3-Contrib 2.9.0, PyTorch 2.13.0
- pytest 9.1.1, Ruff 0.15.21, MyPy 2.3.0
- no VCS, Questa/ModelSim, or Icarus executables on `PATH`

## Executed results

| Check | Result |
|:--|:--|
| Python unit and integration tests, including a real 128-step MaskablePPO smoke | 118 passed |
| Ruff lint and formatting | 50 Python files clean |
| MyPy | 50 source files, no issues |
| Full mock regression | 6 of 6 tests passed with `mock` provenance |
| Mock coverage merge | executed successfully and wrote deterministic merged coverage |
| JSON, Markdown, and HTML report regeneration | executed successfully |
| VCS nightly regression and VDB merge | command plans generated with `dry_run` provenance |
| Questa nightly regression and UCDB merge | command plans generated with `dry_run` provenance |
| Icarus portable smoke | command plan generated with `dry_run` provenance |
| Non-dry VCS request without installed tools | exited 2 with explicit `unavailable` outcome |

The mock run exercised compilation/elaboration staging, three parallel workers, deterministic and
persisted random seeds, per-attempt artifacts, aggregation, and reporting. Dedicated tests also
executed timeout termination, fixed-seed failed-test reruns, unavailable-tool handling, assertion
and UVM failure detection, malformed configuration rejection, and report escaping.

## PPO validation

A short CPU run trained MaskablePPO for 256 timesteps with seed 2024, 32-step episodes, two saved
checkpoints, and two post-training evaluation episodes. The training trace reached a maximum of
60/90 mock bins (0.6667); its final sampled episode reached 36/90 (0.4000). A separate three-episode
evaluation ended at 7/90 (0.0778) mean coverage and mean reward 2.35.

The equal-budget three-episode comparison used the same episode seeds and 32 decisions for each
policy. The briefly trained PPO policy reached mean final coverage 0.0778 and normalized area
0.0778; constrained-random reached 0.5000 and normalized area 0.3519. This intentionally short smoke
validates training, checkpoint load, inference masking, metric generation, and fair comparison
accounting; it is not evidence that PPO outperforms constrained-random stimulus. Repeated evaluation
and comparison commands produced byte-identical JSON files.

```bash
python -m rl.train \
  --output-dir outputs/rl/validation \
  --timesteps 256 --seed 2024 --max-steps 32 --coverage-target 0.90 \
  --checkpoint-frequency 128 --evaluation-episodes 2 --device cpu
python -m rl.evaluate \
  --model outputs/rl/validation/maskable_ppo_final.zip \
  --output-dir outputs/rl/evaluation \
  --episodes 3 --seed 2024 --max-steps 32 --coverage-target 0.90
python -m rl.compare \
  --model outputs/rl/validation/maskable_ppo_final.zip \
  --output-dir outputs/rl/comparison \
  --episodes 3 --budget 32 --seed 2024 --coverage-target 0.90
```

## Reproduction commands

```bash
RUN_RL_TRAINING_SMOKE=1 python -m unittest discover -s tests -v
python -m ruff check regression rl scripts tests
python -m ruff format --check regression rl scripts tests
python -m mypy regression rl scripts tests

python scripts/regress.py full --simulator mock \
  --output outputs/final-validation/mock --jobs 3 --seed-base 2024 --reruns 1
python scripts/regress.py merge --simulator mock \
  --results outputs/final-validation/mock/results.json \
  --output outputs/final-validation/mock-merge
python scripts/regress.py report \
  --results outputs/final-validation/mock/results.json \
  --output outputs/final-validation/regenerated-report --formats json,md,html

python scripts/regress.py suite nightly --simulator vcs --dry-run \
  --output outputs/final-validation/vcs-dry-run --seed-base 2024
QUESTA_UVM_SRC=/opt/uvm/src python scripts/regress.py suite nightly \
  --simulator questa --dry-run \
  --output outputs/final-validation/questa-dry-run --seed-base 2024
python scripts/regress.py suite portable --simulator iverilog --dry-run \
  --output outputs/final-validation/iverilog-dry-run --seed-base 2024
```

## Licensed-tool boundary

No HDL source was compiled or simulated locally. The VCS, Questa, and Icarus results are explicit
command plans, not successful RTL/UVM runs. VDB/UCDB creation, vendor coverage merge execution,
waveform correctness, assertion behavior in a simulator, and integration with real codec IP remain
to be validated where those tools or IP are available.

Repository hygiene no longer prescribes commit counts, dates, subjects, or identical histories
across branches. It still checks tracked artifacts, ignored credential paths, and high-confidence
secret patterns in files and **all-ref patch history**. Normal later commits do not invalidate it.

## Reliability validation — 2026-10-06

Executed on macOS arm64, Python 3.12.14 and Icarus Verilog 13.0. Direct Python dependency versions
are in `constraints.txt`; this snapshot is not a full transitive lockfile.

- Baseline Python: 117 passed, one opt-in training test skipped.
- Revised Python: 127 tests passed with `RUN_RL_TRAINING_SMOKE=1` (includes actual PPO
  training/reload and three real HDL tests). Ruff, formatting and MyPy passed; `pip check` passed.
- Actual portable RTL: 28 checked responses across latency 0–15, backpressure, malformed input,
  stop/reconfigure behavior, and cancellation of an in-flight response by reset. Negative mutation
  tests fail as intended when response data is corrupted or a stalled response is dropped.
- Full mock regression: six tests passed. This is orchestration evidence, not UVM execution.
- UVM predictor now preserves the accepted request cycle; timeout arithmetic guards against unsigned
  underflow. The normal UVM test delays requests beyond the scoreboard timeout to expose regressions.
  This UVM path has **not** been compiled or run here; licensed-simulator validation remains required.
- All final and periodic checkpoints from the real 128-step PPO smoke were loaded through the
  checked loader and evaluated. Missing/malformed sidecars, same-sized reordered actions/bins,
  changed observation history, and swapped zip bytes are rejected by dedicated tests.

### Bounded mock policy comparison

Each of three training seeds received 256 PPO steps. Each saved model and constrained-random policy
then used the same five evaluation seeds 5000–5004, a 32-action budget, target 0.99, and no stale-step
termination. The deterministic backend makes these small repeated episodes highly correlated;
this is an engineering smoke, not a benchmark of real verification effectiveness.

| Training seed | PPO final coverage | Random final coverage | PPO normalized AUC | Random AUC |
|:--|--:|--:|--:|--:|
| 2024 | 0.07778 | 0.47778 | 0.07778 | 0.30417 |
| 2025 | 0.34444 | 0.47778 | 0.27167 | 0.30417 |
| 2026 | 0.32222 | 0.47778 | 0.30021 | 0.30417 |

Mean final-coverage delta (PPO − random): **−0.22963**, sample standard deviation across training
seeds **0.14796**. All three briefly trained policies lost to constrained-random. No training seed,
failed run, or negative result was discarded; no claim of PPO improvement follows from this smoke.

```bash
# Python 3.12; installs tested direct constraints
./scripts/bootstrap.sh --rl
. .venv/bin/activate
OMP_NUM_THREADS=1 RUN_RL_TRAINING_SMOKE=1 python -m unittest discover -s tests -v
python -m ruff check regression rl scripts tests
python -m ruff format --check regression rl scripts tests
python -m mypy regression rl scripts tests
python scripts/regress.py suite portable --simulator iverilog --output outputs/verification/hdl --reruns 0
python scripts/regress.py full --simulator mock --jobs 3 --seed-base 2024 --output outputs/verification/mock
for seed in 2024 2025 2026; do
  OMP_NUM_THREADS=1 python -m rl.train --output-dir outputs/verification/benchmark/$seed \
    --timesteps 256 --seed $seed --max-steps 32 --checkpoint-frequency 128 \
    --evaluation-episodes 1 --device cpu
  OMP_NUM_THREADS=1 python -m rl.compare \
    --model outputs/verification/benchmark/$seed/maskable_ppo_final.zip \
    --output-dir outputs/verification/benchmark/$seed/comparison \
    --episodes 5 --budget 32 --seed 5000 --coverage-target 0.99
done
python scripts/audit_repo.py
```
