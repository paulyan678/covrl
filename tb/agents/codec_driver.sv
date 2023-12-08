class codec_driver extends uvm_driver #(codec_seq_item);
  codec_env_cfg cfg;
  virtual codec_if vif;

  `uvm_component_utils(codec_driver)

  function new(string name = "codec_driver", uvm_component parent = null);
    super.new(name, parent);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(codec_env_cfg)::get(this, "", "cfg", cfg))
      `uvm_fatal("DRV/CFG", "codec_env_cfg was not provided to driver")
    vif = cfg.vif;
  endfunction

  task run_phase(uvm_phase phase);
    codec_seq_item req;
    initialize_bus();
    apply_reset(5);
    forever begin
      seq_item_port.get_next_item(req);
      drive_item(req);
      seq_item_port.item_done();
    end
  endtask

  task initialize_bus();
    vif.reset_n                  <= 1'b0;
    vif.drv_cb.req_valid         <= 1'b0;
    vif.drv_cb.req_cmd           <= CODEC_CMD_CONFIG;
    vif.drv_cb.req_profile       <= CODEC_PROFILE_BASELINE;
    vif.drv_cb.req_width         <= 13'd640;
    vif.drv_cb.req_height        <= 13'd480;
    vif.drv_cb.req_frame_type    <= CODEC_FRAME_I;
    vif.drv_cb.req_bit_depth     <= 4'd8;
    vif.drv_cb.req_qp            <= 6'd26;
    vif.drv_cb.req_payload       <= '0;
    vif.drv_cb.req_payload_bytes <= 3'd4;
    vif.drv_cb.req_control       <= CODEC_CTRL_PING;
    vif.drv_cb.req_inject_error  <= 1'b0;
    vif.drv_cb.latency_cycles    <= cfg.default_latency_cycles[3:0];
    vif.drv_cb.rsp_ready         <= 1'b1;
  endtask

  task apply_reset(int unsigned cycles);
    vif.reset_n <= 1'b0;
    repeat (cycles) @(vif.drv_cb);
    vif.reset_n <= 1'b1;
    @(vif.drv_cb);
  endtask

  task drive_item(codec_seq_item req);
    int unsigned cycles;

    repeat (req.inter_transaction_gap) @(vif.drv_cb);
    vif.drv_cb.req_cmd           <= req.cmd;
    vif.drv_cb.req_profile       <= req.profile;
    vif.drv_cb.req_width         <= req.width;
    vif.drv_cb.req_height        <= req.height;
    vif.drv_cb.req_frame_type    <= req.frame_type;
    vif.drv_cb.req_bit_depth     <= req.bit_depth;
    vif.drv_cb.req_qp            <= req.qp;
    vif.drv_cb.req_payload       <= req.payload;
    vif.drv_cb.req_payload_bytes <= req.payload_bytes;
    vif.drv_cb.req_control       <= req.control;
    vif.drv_cb.req_inject_error  <= req.inject_error && cfg.enable_error_injection;
    vif.drv_cb.latency_cycles    <= req.latency_cycles[3:0];
    vif.drv_cb.req_valid         <= 1'b1;

    cycles = 0;
    do begin
      @(vif.drv_cb);
      cycles++;
      if (cycles > cfg.driver_timeout_cycles)
        `uvm_fatal("DRV/REQ_TIMEOUT", $sformatf(
          "request did not handshake after %0d cycles: %s", cycles,
          req.convert2string()))
    end while (!vif.drv_cb.req_ready);
    vif.drv_cb.req_valid <= 1'b0;

    if (cfg.enable_backpressure && req.response_stall_cycles > 0) begin
      vif.drv_cb.rsp_ready <= 1'b0;
      repeat (req.response_stall_cycles) @(vif.drv_cb);
    end
    vif.drv_cb.rsp_ready <= 1'b1;

    cycles = 0;
    while (!vif.drv_cb.rsp_valid) begin
      @(vif.drv_cb);
      cycles++;
      if (cycles > cfg.driver_timeout_cycles)
        `uvm_fatal("DRV/RSP_TIMEOUT", $sformatf(
          "response did not arrive after %0d cycles: %s", cycles,
          req.convert2string()))
    end
    req.status        = codec_status_e'(vif.drv_cb.rsp_status);
    req.response_data = vif.drv_cb.rsp_data;
    req.sequence_id   = vif.drv_cb.rsp_sequence_id;
    @(vif.drv_cb);
  endtask

endclass
