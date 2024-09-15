class codec_reset_recovery_test extends codec_base_test;
  `uvm_component_utils(codec_reset_recovery_test)

  function new(string name = "codec_reset_recovery_test",
               uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function codec_base_sequence create_main_sequence();
    return codec_reset_sequence::type_id::create("reset_recovery_sequence");
  endfunction

endclass
