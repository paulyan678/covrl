class codec_sequencer extends uvm_sequencer #(codec_seq_item);
  codec_env_cfg cfg;

  `uvm_component_utils(codec_sequencer)

  function new(string name = "codec_sequencer", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(codec_env_cfg)::get(this, "", "cfg", cfg))
      `uvm_fatal("SEQ/CFG", "codec_env_cfg was not provided to sequencer")
  endfunction

endclass
