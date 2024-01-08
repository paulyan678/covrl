class codec_env extends uvm_env;
  codec_env_cfg cfg;
  codec_agent agent;
  codec_reference_model reference_model;
  codec_scoreboard scoreboard;
  codec_coverage coverage;

  `uvm_component_utils(codec_env)

  function new(string name = "codec_env", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(codec_env_cfg)::get(this, "", "cfg", cfg))
      `uvm_fatal("ENV/CFG", "codec_env_cfg was not provided to environment")
    cfg.validate();

    uvm_config_db #(codec_env_cfg)::set(this, "agent", "cfg", cfg);
    agent = codec_agent::type_id::create("agent", this);
    reference_model = codec_reference_model::type_id::create("reference_model", this);
    scoreboard = codec_scoreboard::type_id::create("scoreboard", this);
    if (cfg.enable_coverage)
      coverage = codec_coverage::type_id::create("coverage", this);
  endfunction

  function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    agent.request_ap.connect(reference_model.analysis_export);
    agent.reset_ap.connect(reference_model.analysis_export);
    reference_model.expected_ap.connect(scoreboard.expected_imp);
    agent.response_ap.connect(scoreboard.actual_imp);
    agent.reset_ap.connect(scoreboard.reset_imp);

    if (coverage != null) begin
      agent.request_ap.connect(coverage.analysis_export);
      agent.response_ap.connect(coverage.analysis_export);
      agent.reset_ap.connect(coverage.analysis_export);
    end
  endfunction

endclass
