class codec_backpressure_test extends codec_base_test;
  `uvm_component_utils(codec_backpressure_test)

  function new(string name = "codec_backpressure_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    cfg.enable_backpressure = 1;
  endfunction

  function uvm_sequence_base create_main_sequence();
    return codec_backpressure_sequence::type_id::create("backpressure_sequence");
  endfunction

endclass
