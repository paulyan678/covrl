class codec_normal_test extends codec_base_test;
  `uvm_component_utils(codec_normal_test)

  function new(string name = "codec_normal_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function uvm_sequence_base create_main_sequence();
    return codec_directed_sequence::type_id::create("normal_sequence");
  endfunction

endclass
