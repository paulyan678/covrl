class codec_invalid_test extends codec_base_test;
  `uvm_component_utils(codec_invalid_test)

  function new(string name = "codec_invalid_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    cfg.enable_error_injection = 1;
  endfunction

  function codec_base_sequence create_main_sequence();
    return codec_error_sequence::type_id::create("invalid_sequence");
  endfunction

endclass
