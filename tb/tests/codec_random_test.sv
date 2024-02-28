class codec_random_test extends codec_base_test;
  `uvm_component_utils(codec_random_test)

  function new(string name = "codec_random_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function uvm_sequence_base create_main_sequence();
    return codec_random_sequence::type_id::create("random_sequence");
  endfunction

endclass
