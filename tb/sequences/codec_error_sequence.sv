class codec_error_sequence extends codec_base_sequence;
  `uvm_object_utils(codec_error_sequence)

  function new(string name = "codec_error_sequence");
    super.new(name);
  endfunction

  task send_injected_error();
    codec_seq_item item;
    item = codec_seq_item::type_id::create("injected_error");
    start_item(item);
    item.cmd = CODEC_CMD_DATA;
    item.profile = CODEC_PROFILE_MAIN;
    item.width = 1280;
    item.height = 720;
    item.frame_type = CODEC_FRAME_P;
    item.bit_depth = 10;
    item.qp = 24;
    item.payload = 32'hbad0_cafe;
    item.payload_bytes = 4;
    item.control = CODEC_CTRL_PING;
    item.inject_error = 1;
    item.latency_cycles = 1;
    item.response_stall_cycles = 0;
    item.inter_transaction_gap = 0;
    item.allow_illegal = 1;
    finish_item(item);
  endtask

  task body();
    // Requests before configuration must be rejected without corrupting state.
    send_data(32'h0000_0001, 4, CODEC_FRAME_P, 1);
    send_control(CODEC_CTRL_START, 1);

    send_config(CODEC_PROFILE_RESERVED, 1280, 720, 8, 20, 1);
    send_config(CODEC_PROFILE_MAIN, 0, 720, 8, 20, 1);
    send_config(CODEC_PROFILE_MAIN, 1280, 720, 9, 20, 1);
    send_config(CODEC_PROFILE_MAIN, 1280, 720, 10, 52, 1);

    send_config(CODEC_PROFILE_MAIN, 1280, 720, 10, 24);
    send_frame(CODEC_FRAME_RESERVED, 32'h0000_0002);
    send_data(32'h0000_0003, 0, CODEC_FRAME_P);
    send_data(32'h0000_0004, 7, CODEC_FRAME_P);
    send_control(codec_control_e'(3'd7));
    send_injected_error();
    send_control(CODEC_CTRL_STOP);
    send_data(32'h0000_0005, 4, CODEC_FRAME_P, 1);
  endtask

endclass
