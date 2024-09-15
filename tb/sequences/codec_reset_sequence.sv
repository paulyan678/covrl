class codec_reset_sequence extends codec_base_sequence;
  `uvm_object_utils(codec_reset_sequence)

  function new(string name = "codec_reset_sequence");
    super.new(name);
  endfunction

  task body();
    codec_seq_item interrupted;

    send_config(CODEC_PROFILE_MAIN, 1280, 720, 10, 24);
    send_frame(CODEC_FRAME_I, 32'h1000_0001);
    send_data(32'haaaa_5555, 4, CODEC_FRAME_I);

    interrupted = codec_seq_item::type_id::create("interrupted_data");
    seed_random_item(interrupted);
    start_item(interrupted);
    if (!interrupted.randomize() with {
      cmd == CODEC_CMD_DATA;
      payload == 32'hdeaf_beef;
      payload_bytes == 4;
      latency_cycles == 10;
      response_stall_cycles == 0;
      reset_after_request == 1;
      reset_cycles == 4;
      inject_error == 0;
    })
      `uvm_fatal("SEQ/RESET", "failed to create reset-interrupted transaction")
    finish_item(interrupted);

    // The first request after reset proves that configuration state was lost.
    send_data(32'h1111_2222, 4, CODEC_FRAME_P, 1);
    send_config(CODEC_PROFILE_HIGH, 1920, 1080, 12, 18);
    send_frame(CODEC_FRAME_I, 32'h2000_0001);
    send_data(32'h3333_4444, 4, CODEC_FRAME_I);
    send_control(CODEC_CTRL_FLUSH);
  endtask

endclass
