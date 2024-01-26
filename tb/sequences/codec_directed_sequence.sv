class codec_directed_sequence extends codec_base_sequence;
  `uvm_object_utils(codec_directed_sequence)

  function new(string name = "codec_directed_sequence");
    super.new(name);
  endfunction

  task body();
    send_config(CODEC_PROFILE_MAIN, 1920, 1080, 10, 22);
    send_control(CODEC_CTRL_START);
    send_frame(CODEC_FRAME_I, 32'h0000_0001);
    send_data(32'h0011_2233, 4, CODEC_FRAME_I);
    send_data(32'h4455_6677, 4, CODEC_FRAME_I);
    send_frame(CODEC_FRAME_P, 32'h0000_0002);
    send_data(32'h89ab_cdef, 4, CODEC_FRAME_P);
    send_control(CODEC_CTRL_FLUSH);
    send_control(CODEC_CTRL_STOP);
    send_control(CODEC_CTRL_PING);
  endtask

endclass
