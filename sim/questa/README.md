# Questa/ModelSim adapter

The adapter generates five stages from the shared regression manifest:

1. `vlib` work-library creation;
2. `vlog -sv -mfcu -L uvm` compilation;
3. `vopt` optimization with coverage instrumentation;
4. one batch `vsim -c` process per test, saving UCDB coverage when enabled;
5. optional `vcover merge` and `vcover report -html` commands.

Executables default to `vlib`, `vlog`, `vopt`, `vsim`, and `vcover` on `PATH`. Override them without
hard-coding installation paths:

```bash
export VLIB='vlib'
export VLOG='vlog'
export VOPT='vopt'
export VSIM='vsim'
export VCOVER='vcover'
```

Each value may be a quoted wrapper command with fixed arguments. Configure the Siemens license and
any site setup in the invoking shell. Compile, optimize, run, and coverage flags are configured in
`sim/manifests/regression.json`.

Inspect commands without checking tools or launching Questa:

```bash
python3 scripts/regress.py suite nightly --simulator questa --dry-run
python3 scripts/regress.py merge --simulator questa --dry-run \
  --database outputs/planned/a.ucdb --database outputs/planned/b.ucdb
```

Run and merge on a licensed host:

```bash
python3 scripts/regress.py suite nightly --simulator questa
python3 scripts/regress.py merge \
  --simulator questa --results outputs/regression/questa/results.json
```

The command structure is unit-tested and dry-run validated. A host without Questa/ModelSim cannot
validate UVM compilation, execution, waveform generation, UCDB saving, or `vcover` behavior.
