class codec_corner_sequence extends codec_base_sequence;
  `uvm_object_utils(codec_corner_sequence)

  function new(string name = "codec_corner_sequence");
    super.new(name);
  endfunction

  task body();
    send_config(CODEC_PROFILE_BASELINE, 16, 16, 8, 0);
    send_frame(CODEC_FRAME_I, 32'h0000_0000);
    send_data(32'h0000_00ff, 1, CODEC_FRAME_I);

    send_config(CODEC_PROFILE_MAIN, 720, 576, 10, 17);
    send_frame(CODEC_FRAME_P, 32'hffff_ffff);
    send_data(32'h0000_ffff, 2, CODEC_FRAME_P);

    send_config(CODEC_PROFILE_HIGH, 1280, 720, 12, 18);
    send_frame(CODEC_FRAME_B, 32'h8000_0000);
    send_data(32'h00ff_ffff, 3, CODEC_FRAME_B);

    send_config(CODEC_PROFILE_MAIN, 1920, 1080, 8, 35);
    send_frame(CODEC_FRAME_P, 32'h7fff_ffff);

    send_config(CODEC_PROFILE_HIGH, 4096, 4096, 12, 51);
    send_data(32'hffff_ffff, 4, CODEC_FRAME_I);
    send_control(CODEC_CTRL_PING);
    send_control(CODEC_CTRL_FLUSH);
  endtask

endclass
