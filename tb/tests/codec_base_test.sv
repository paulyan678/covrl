class codec_base_test extends uvm_test;
  codec_env_cfg cfg;
  codec_env env;

  `uvm_component_utils(codec_base_test)

  function new(string name = "codec_base_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    cfg = codec_env_cfg::type_id::create("cfg");
    if (!uvm_config_db #(virtual codec_if)::get(this, "", "vif", cfg.vif))
      `uvm_fatal("TEST/VIF", "virtual codec interface was not configured")
    apply_plusargs();
    uvm_config_db #(codec_env_cfg)::set(this, "env", "cfg", cfg);
    env = codec_env::type_id::create("env", this);
  endfunction

  function void apply_plusargs();
    string verbosity_name;
    if ($value$plusargs("CODEC_SEED=%d", cfg.seed))
      cfg.override_sequence_seed = 1;
    void'($value$plusargs("TXN_COUNT=%d", cfg.transaction_count));
    void'($value$plusargs("TIMEOUT=%d", cfg.driver_timeout_cycles));
    void'($value$plusargs("SB_TIMEOUT=%d", cfg.scoreboard_timeout_cycles));
    void'($value$plusargs("LATENCY=%d", cfg.default_latency_cycles));
    void'($value$plusargs("RSP_STALL=%d", cfg.default_response_stall_cycles));
    void'($value$plusargs("ENABLE_B_FRAMES=%d", cfg.enable_b_frames));
    void'($value$plusargs("ENABLE_HIGH_PROFILE=%d", cfg.enable_high_profile));
    void'($value$plusargs("ERROR_INJECTION=%d", cfg.enable_error_injection));
    void'($value$plusargs("BACKPRESSURE=%d", cfg.enable_backpressure));
    void'($value$plusargs("COVERAGE=%d", cfg.enable_coverage));
    void'($value$plusargs("WAVES=%d", cfg.enable_waveforms));
    void'($value$plusargs("WAVEFORM_FILE=%s", cfg.waveform_file));
    if ($value$plusargs("UVM_VERBOSITY=%s", verbosity_name)) begin
      case (verbosity_name)
        "UVM_NONE":   cfg.verbosity = UVM_NONE;
        "UVM_LOW":    cfg.verbosity = UVM_LOW;
        "UVM_MEDIUM": cfg.verbosity = UVM_MEDIUM;
        "UVM_HIGH":   cfg.verbosity = UVM_HIGH;
        "UVM_FULL":   cfg.verbosity = UVM_FULL;
        "UVM_DEBUG":  cfg.verbosity = UVM_DEBUG;
        default: `uvm_warning("TEST/VERBOSITY", $sformatf(
          "unknown UVM_VERBOSITY '%s'; using UVM_MEDIUM", verbosity_name))
      endcase
    end
  endfunction

  function void end_of_elaboration_phase(uvm_phase phase);
    super.end_of_elaboration_phase(phase);
    uvm_top.set_report_verbosity_level_hier(cfg.verbosity);
    uvm_top.print_topology();
  endfunction

  virtual function codec_base_sequence create_main_sequence();
    return codec_base_sequence::type_id::create("sequence");
  endfunction

  task run_phase(uvm_phase phase);
    codec_base_sequence main_sequence;
    phase.raise_objection(this, "running codec base sequence");
    main_sequence = create_main_sequence();
    if (cfg.override_sequence_seed)
      main_sequence.set_deterministic_seed(cfg.seed);
    main_sequence.start(env.agent.sequencer);
    phase.drop_objection(this, "codec base sequence completed");
  endtask

endclass
