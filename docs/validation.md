# Validation Record

This record separates executable local evidence from simulator plans. Generated logs, coverage
artifacts, reports, and checkpoints are intentionally ignored; the commands below reproduce them.

## Validation environment

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

The final history audit must observe commit 68 itself, so it is run immediately after that commit:

```bash
python scripts/audit_repo.py
git status --short
```
