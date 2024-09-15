# Coverage-Guided PPO Design

## Objective

The RL prototype demonstrates a sound, extensible method for selecting codec transactions according
to functional coverage feedback. It is not intended to establish PPO optimality. The design favors
reproducible semantics, explicit legality, testable reward accounting, and a replaceable coverage
backend over simulator-specific coupling.

The implementation uses SB3-Contrib `MaskablePPO`, a maintained PPO variant that accepts a Boolean
action mask during rollout. The same mask is passed to every inference call and checked before an
action reaches the backend.

## Action model

The policy sees one `Discrete(135)` action. Stable catalog indexes expand into complete,
JSON-serializable transactions:

| Category | Count | Parameters |
|:--|--:|:--|
| Configuration | 72 | 3 profiles × 4 resolutions × 2 depths × 3 quantizers |
| Frame/input | 54 | 3 frame types × 3 input sizes × 2 timing modes × 3 stall choices |
| Control | 4 | start, flush, stop, reset |
| Error injection | 4 | invalid config, invalid input, invalid control, response timeout |
| Idle | 1 | one unproductive cycle |

Flattening the structured choices creates a simple policy output while preserving an inspectable
mapping. `ActionCatalog` requires contiguous indexes, unique names, complete fields, deterministic
serialization, and a reproducibility digest. Training writes the exact catalog beside each model.

This illustrative RL vocabulary is intentionally smaller than the SystemVerilog transport
vocabulary. A real bridge must define one reviewed mapping rather than assuming the two models are
identical.

## Protocol and capability model

The mock backend exposes `UNCONFIGURED`, `CONFIGURED`, and `RUNNING` states plus current
configuration and capabilities. Relational capability rules matter: Baseline is 8-bit-only, QCIF is
8-bit-only, and Baseline excludes B frames. A flat list of choices alone would not express these
restrictions.

Intentional error-injection actions are valid verification stimulus when their preconditions hold.
Accidental state-illegal control, frame, and configuration actions are masked. This keeps negative
testing explicit and prevents the policy from earning reward by repeatedly violating the protocol.

## Observation

The default observation is a `Dict` suitable for `MultiInputPolicy`:

| Field | Representation | Purpose |
|:--|:--|:--|
| `coverage` | 90-bit vector | current reached functional bins |
| `recent_transactions` | 8 normalized indexes, `-1` padded | short action history |
| `protocol_state` | 3-bit one-hot | unconfigured/configured/running state |
| `current_configuration` | concatenated one-hot choices | active profile, resolution, depth, QP |
| `available_configurations` | 135-bit vector | capability-supported configuration indexes |
| `remaining_budget` | scalar in `[0,1]` | fraction of episode steps remaining |
| `recent_rewards` | 8 clipped values | short reward trend |
| `recent_coverage_gains` | 8 normalized values | recent novelty trend |
| `action_mask` | 135-bit vector | current legal action choices |

The coverage vector's meaning is fixed by the backend bin ordering and digest. Histories are
right-aligned. The action mask is present both in the observation for policy context and through the
`action_masks()` method required by MaskablePPO.

## Dynamic action mask

Mask rules are pure functions of the catalog and current snapshot:

- configure only when not running and only for supported relational combinations;
- start only when configured;
- frames only when running and supported by the active profile;
- flush only when running;
- stop only when configured or running;
- reset and idle at any state;
- each explicit error action only in a state where that error scenario is meaningful.

The environment defensively checks direct callers too. If a caller ignores the advertised mask, the
action is penalized, logged as illegal, and never passed to `CoverageBackend.execute`. Repeated mask
violations truncate the episode. Evaluation rejects an excluded prediction before even calling
`env.step`, proving inference-time enforcement at a second boundary.

## Coverage backend

`CoverageBackend` exposes four core semantics:

- stable `bin_names` for the observation lifetime;
- `reset(seed)` to start an episode;
- `execute(action)` to return protocol effects and coverage changes;
- `snapshot()` for state without advancing the simulator.

Every step carries the full immutable snapshot, exact new-bin names, accepted/status/latency data,
and timeout, invalid-transition, and infrastructure-failure flags. Contract validation rejects
unknown or duplicate bins, non-monotonic snapshots, stale gains, and any mismatch between the
reported gain and the exact pre-step/post-step coverage delta.

`MockCoverageBackend` deterministically models 90 goals: codec choices, legal and illegal
configuration, frame/input/timing choices, backpressure and latency classes, reset/error/control
scenarios, and focused crosses. Identical seeds and action indexes produce identical state, latency,
coverage, and reward trajectories across Python processes. Mock bins are not simulator functional
or code coverage.

A real implementation may batch simulator work but must preserve these semantics. It should record
the action-catalog and coverage-bin digests with every result so a checkpoint is never silently used
with incompatible observation meanings.

## Reward

The default reward is additive:

| Event | Reward |
|:--|--:|
| each newly reached bin | `+1.00` |
| reaching coverage target | `+5.00` |
| no new coverage | `-0.05` |
| repeat of the previous action with no gain | additional `-0.10` |
| caller selects masked action | `-2.00` |
| backend timeout | `-3.00` |
| backend reports invalid transition | `-3.00` |
| verification infrastructure failure | `-10.00` |

New functional coverage is deliberately dominant. Small redundancy penalties discourage long
unproductive loops without overwhelming delayed exploration. Invalid transitions and timeouts are
more costly because they waste verification budget. Infrastructure failures receive the strongest
penalty and terminate rather than being learned as a normal DUT outcome.

Reward values live in `RewardConfig`, so experiments can change shaping without changing backend
semantics. Training metrics retain raw per-step gains and rewards, allowing reward behavior to be
audited independently of the policy.

## Episode rules

Default episodes have a 200-step budget, 90% target, three-mask-violation limit, and 60-step stale
limit.

Termination represents a task or infrastructure terminal state:

- the configured coverage target was reached; or
- the verification infrastructure failed.

Truncation represents an external or budget limit:

- backend response timeout;
- step budget exhausted;
- stale-step limit reached; or
- repeated mask violations reached the configured limit.

Resetting with a seed controls the deterministic backend. Subsequent unseeded resets draw episode
seeds reproducibly from Gymnasium's seeded random generator.

## Training and inference

Install the optional dependencies:

```bash
./scripts/bootstrap.sh --rl
. .venv/bin/activate
```

Training uses `MaskablePPO("MultiInputPolicy", env, ...)`. SB3-Contrib calls `action_masks()` before
each rollout decision. The training entry point seeds Python, NumPy, PyTorch, the model, and the
environment, then writes periodic checkpoints and a final model:

```bash
python -m rl.train \
  --output-dir outputs/rl/training \
  --timesteps 20000 --seed 2024 --max-steps 200 \
  --coverage-target 0.90 --checkpoint-frequency 5000 \
  --evaluation-episodes 5 --device auto
```

Evaluation passes the current mask to `model.predict` on every step:

```bash
python -m rl.evaluate \
  --model outputs/rl/training/maskable_ppo_final.zip \
  --output-dir outputs/rl/evaluation \
  --episodes 10 --seed 2024 --max-steps 200 --coverage-target 0.90
```

Use `--stochastic` only when sampled masked inference is desired; deterministic masked inference is
the default.

## Constrained-random baseline

The comparison uses a uniform policy over the exact same legal mask as PPO. Both strategies receive
identical episode seeds and step budgets. This isolates action selection from legality and budget
advantages:

```bash
python -m rl.compare \
  --model outputs/rl/training/maskable_ppo_final.zip \
  --output-dir outputs/rl/comparison \
  --episodes 20 --budget 200 --seed 2024 --coverage-target 0.99
```

The summary reports mean final coverage, fixed-budget normalized coverage-curve area, reward, steps,
deltas, and mean coverage progression for both strategies. Shorter episodes are padded with their
terminal coverage when computing area and progression, so early termination cannot receive a budget
advantage. Environments are closed after evaluation even when a model or backend raises. This is a
reproducible engineering comparison, not a statistical proof of superiority.

## Artifacts and reproducibility

Training writes:

- `action_catalog.json` and `training_metadata.json`;
- periodic `checkpoints/*.zip` and `maskable_ppo_final.zip`;
- JSON and CSV training progression plus a compact summary;
- post-training evaluation JSON, CSV, and summary.

Evaluation and comparison write per-step/per-episode metrics and summaries. All live under
`outputs/rl/` by default and are ignored by Git.

Fixed environment seeds guarantee deterministic mock trajectories. Neural training may still vary
across dependency versions, devices, thread schedules, or hardware. The metadata records dependency
versions, configuration, catalog digest, and coverage-bin digest so results can be interpreted and
recreated responsibly.

## Extending to a simulator

1. Align the action catalog with the real SystemVerilog transaction vocabulary and capabilities.
2. Implement a service that keeps compilation and elaboration outside the per-action hot path.
3. Map catalog actions to UVM sequences or transaction files.
4. Export stable functional-coverage bins after each action or batch.
5. Implement `CoverageBackend` and flag DUT timeouts separately from infrastructure failures.
6. Version catalog/bin changes and reject incompatible checkpoints.
7. Compare batched PPO and constrained-random runs using the same seeds, budget, build, and coverage
   model.

For expensive simulators, one action need not mean one process launch. A backend can execute a batch,
return incremental coverage after each accepted transaction, or treat one policy decision as a
short sequence while retaining explicit reward attribution.
