class codec_agent extends uvm_agent;
  codec_env_cfg cfg;
  codec_sequencer sequencer;
  codec_driver driver;
  codec_monitor monitor;

  uvm_analysis_port #(codec_seq_item) request_ap;
  uvm_analysis_port #(codec_seq_item) response_ap;
  uvm_analysis_port #(codec_seq_item) reset_ap;

  `uvm_component_utils(codec_agent)

  function new(string name = "codec_agent", uvm_component parent = null);
    super.new(name, parent);
    request_ap = new("request_ap", this);
    response_ap = new("response_ap", this);
    reset_ap = new("reset_ap", this);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(codec_env_cfg)::get(this, "", "cfg", cfg))
      `uvm_fatal("AGT/CFG", "codec_env_cfg was not provided to agent")

    is_active = cfg.is_active;
    uvm_config_db #(codec_env_cfg)::set(this, "*", "cfg", cfg);
    monitor = codec_monitor::type_id::create("monitor", this);
    if (is_active == UVM_ACTIVE) begin
      sequencer = codec_sequencer::type_id::create("sequencer", this);
      driver = codec_driver::type_id::create("driver", this);
    end
  endfunction

  function void connect_phase(uvm_phase phase);
    super.connect_phase(phase);
    monitor.request_ap.connect(request_ap);
    monitor.response_ap.connect(response_ap);
    monitor.reset_ap.connect(reset_ap);
    if (is_active == UVM_ACTIVE)
      driver.seq_item_port.connect(sequencer.seq_item_export);
  endfunction

endclass
