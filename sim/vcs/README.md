# VCS adapter

The adapter generates four stages from the shared regression manifest:

1. `vlogan -full64 -sverilog -ntb_opts uvm-1.2` compilation;
2. `vcs -full64 -ntb_opts uvm-1.2` elaboration and coverage instrumentation;
3. one `simv` process per test with the resolved seed and UVM plusargs;
4. optional `urg` coverage merge and HTML report generation.

Executables default to `vlogan`, `vcs`, and `urg` on `PATH`. Override them without hard-coding a
repository path:

```bash
export VLOGAN='vlogan'
export VCS='vcs'
export URG='urg'
```

Each value may be a quoted wrapper command with fixed arguments. Configure the Synopsys license and
any site setup in the invoking shell. Compile, elaborate, run, and coverage flags are configured in
`sim/manifests/regression.json`.

Inspect the complete UVM plan without checking tools or launching VCS:

```bash
python3 scripts/regress.py suite nightly --simulator vcs --dry-run
python3 scripts/regress.py merge --simulator vcs --dry-run \
  --database outputs/planned/a.vdb --database outputs/planned/b.vdb
```

Run and merge on a licensed host:

```bash
python3 scripts/regress.py suite nightly --simulator vcs
python3 scripts/regress.py merge \
  --simulator vcs --results outputs/regression/vcs/results.json
```

Selected logs, simulation image, VDB paths, and waves are directed to the chosen output tree. VCS
may create additional site/version-specific auxiliary files in its working directory; review the
first real run and extend `.gitignore` or adapter flags if necessary.

The command structure is unit-tested and dry-run validated. A host without VCS cannot validate UVM
compilation, execution, waveform generation, or URG behavior.
