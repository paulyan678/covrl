# Project Scope

## Goals

- Provide a reusable UVM environment around a replaceable codec transaction interface.
- Exercise a small behavioral codec model without proprietary specifications or tools.
- Generate VCS and Questa commands from one simulator-neutral regression configuration.
- Demonstrate coverage-guided stimulus through a deterministic mock backend and masked PPO.

## Boundaries

- The toy DUT is a protocol model, not a standards-compliant encoder or decoder.
- Licensed simulator execution is optional; command generation and mock execution remain testable.
- Simulator-backed RL coverage is an extension point behind the same backend contract as the mock.

## Completion signals

The repository is complete when its reusable verification components, regression orchestration,
coverage reporting, RL prototype, automated tests, and integration guidance work together without
requiring proprietary codec material.
