class codec_normal_test extends codec_base_test;
  `uvm_component_utils(codec_normal_test)

  function new(string name = "codec_normal_test", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  task run_phase(uvm_phase phase);
    phase.raise_objection(this, "checking late request aging");
    // Requests begin after an entire timeout interval has already elapsed.
    // A predictor that drops observed_cycle causes a false timeout here.
    repeat (cfg.scoreboard_timeout_cycles + 10) @(cfg.vif.mon_cb);
    super.run_phase(phase);
    phase.drop_objection(this, "late request aging checked");
  endtask

  function codec_base_sequence create_main_sequence();
    return codec_directed_sequence::type_id::create("normal_sequence");
  endfunction

endclass
