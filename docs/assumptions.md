# Engineering Assumptions

## Inspected starting point

- The selected workspace was empty and was not a Git repository.
- No existing DUT, source convention, history, remote, or unrelated change was
  available to preserve.
- The configured Git identity is `Paul <paul.yan@mail.utoronto.ca>`.
- No VCS, Questa/ModelSim, Icarus, Verilator, or other HDL simulator was found.
- Python 3.10 or newer and GNU Make are the portable local baseline.

## Protocol and DUT

- The included DUT is a behavioral protocol-level codec model, not an
  implementation of a proprietary compression standard.
- A request/response ready-valid interface represents configuration, frame,
  data, and control transactions. The interface is intentionally replaceable.
- The deterministic data transform exists only to make prediction, ordering,
  error handling, and reset recovery observable.
- Width and height are bounded to 4096, bit depth is 8, 10, or 12, and quality
  is represented by a quantization parameter from 0 through 51.

## Verification architecture

- Codec-independent transaction, sequencing, checking, coverage, and
  orchestration code is separated from the toy-DUT adapter.
- UVM 1.2-compatible APIs are used. Full UVM compilation requires a licensed
  simulator or another simulator with adequate class-library support.
- The open-source path, when available, targets the RTL smoke bench and does
  not change or reduce the UVM architecture.
- Generated commands are testable without claiming that unavailable tools ran.

## Regression and reinforcement learning

- JSON manifests avoid a mandatory configuration-parser dependency.
- Dry-run, mock, and real execution results carry distinct provenance.
- `sb3-contrib` MaskablePPO is the optional maintained policy implementation;
  the core environment and deterministic mock coverage backend remain usable
  without it.
- One flattened discrete action catalog is used so a state-dependent Boolean
  mask can be applied during both training and inference.
- Simulator-backed coverage will use the same backend contract as the mock;
  the initial real adapter is a documented integration boundary rather than a
  fabricated coverage service.

## Validation boundaries

- Python unit tests, mock regression runs, reports, deterministic RL behavior,
  and simulator command generation are expected to be validated locally.
- HDL compilation, UVM execution, proprietary coverage databases, and real
  codec-IP behavior must be validated on a host with the required tools or IP.
- Generated outputs, credentials, license settings, waveforms, and local model
  checkpoints are never source-controlled.
