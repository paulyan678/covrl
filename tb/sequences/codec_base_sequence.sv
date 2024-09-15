class codec_base_sequence extends uvm_sequence #(codec_seq_item);
  codec_env_cfg cfg;
  bit deterministic_seed_enabled;
  int unsigned deterministic_seed_state;
  `uvm_object_utils(codec_base_sequence)
  `uvm_declare_p_sequencer(codec_sequencer)

  function new(string name = "codec_base_sequence");
    super.new(name);
  endfunction

  function void set_deterministic_seed(int unsigned seed);
    deterministic_seed_enabled = 1;
    deterministic_seed_state = seed;
    srandom(seed);
  endfunction

  function void advance_deterministic_seed();
    deterministic_seed_state =
      deterministic_seed_state * 32'd1664525 + 32'd1013904223;
  endfunction

  function void seed_random_item(codec_seq_item item);
    if (deterministic_seed_enabled) begin
      item.srandom(deterministic_seed_state);
      advance_deterministic_seed();
    end
  endfunction

  function int unsigned choose_index(int unsigned maximum_index);
    int unsigned choice;
    if (!deterministic_seed_enabled)
      return $urandom_range(maximum_index);
    choice = deterministic_seed_state % (maximum_index + 1);
    advance_deterministic_seed();
    return choice;
  endfunction

  task pre_body();
    super.pre_body();
    cfg = p_sequencer.cfg;
  endtask

  task body();
    send_config(CODEC_PROFILE_MAIN, 640, 480, 8, 26);
    send_data(32'h0123_4567, 4, CODEC_FRAME_I);
  endtask

  task send_config(
    codec_profile_e profile,
    int unsigned width,
    int unsigned height,
    int unsigned bit_depth,
    int unsigned qp,
    bit allow_illegal = 0
  );
    codec_seq_item item;
    item = codec_seq_item::type_id::create("config_item");
    start_item(item);
    item.cmd = CODEC_CMD_CONFIG;
    item.profile = profile;
    item.width = width[12:0];
    item.height = height[12:0];
    item.bit_depth = bit_depth[3:0];
    item.qp = qp[5:0];
    item.frame_type = CODEC_FRAME_I;
    item.payload = '0;
    item.payload_bytes = 0;
    item.control = CODEC_CTRL_PING;
    item.inject_error = 0;
    item.latency_cycles = cfg.default_latency_cycles;
    item.response_stall_cycles = cfg.default_response_stall_cycles;
    item.inter_transaction_gap = 0;
    item.allow_illegal = allow_illegal;
    finish_item(item);
  endtask

  task send_frame(codec_frame_type_e frame_type, logic [31:0] metadata);
    codec_seq_item item;
    item = codec_seq_item::type_id::create("frame_item");
    start_item(item);
    item.cmd = CODEC_CMD_FRAME;
    item.frame_type = frame_type;
    item.payload = metadata;
    item.payload_bytes = 4;
    item.profile = CODEC_PROFILE_BASELINE;
    item.width = 640;
    item.height = 480;
    item.bit_depth = 8;
    item.qp = 26;
    item.control = CODEC_CTRL_PING;
    item.inject_error = 0;
    item.latency_cycles = cfg.default_latency_cycles;
    item.response_stall_cycles = cfg.default_response_stall_cycles;
    item.inter_transaction_gap = 0;
    item.allow_illegal = frame_type == CODEC_FRAME_RESERVED;
    finish_item(item);
  endtask

  task send_data(logic [31:0] payload, int unsigned bytes,
                 codec_frame_type_e frame_type = CODEC_FRAME_P,
                 bit allow_state_illegal = 0);
    codec_seq_item item;
    item = codec_seq_item::type_id::create("data_item");
    start_item(item);
    item.cmd = CODEC_CMD_DATA;
    item.frame_type = frame_type;
    item.payload = payload;
    item.payload_bytes = bytes[2:0];
    item.profile = CODEC_PROFILE_BASELINE;
    item.width = 640;
    item.height = 480;
    item.bit_depth = 8;
    item.qp = 26;
    item.control = CODEC_CTRL_PING;
    item.inject_error = 0;
    item.latency_cycles = cfg.default_latency_cycles;
    item.response_stall_cycles = cfg.default_response_stall_cycles;
    item.inter_transaction_gap = 0;
    item.allow_illegal = allow_state_illegal || !(bytes inside {[1:4]});
    finish_item(item);
  endtask

  task send_control(codec_control_e control, bit allow_state_illegal = 0);
    codec_seq_item item;
    item = codec_seq_item::type_id::create("control_item");
    start_item(item);
    item.cmd = CODEC_CMD_CONTROL;
    item.control = control;
    item.profile = CODEC_PROFILE_BASELINE;
    item.width = 640;
    item.height = 480;
    item.frame_type = CODEC_FRAME_I;
    item.bit_depth = 8;
    item.qp = 26;
    item.payload = '0;
    item.payload_bytes = 0;
    item.inject_error = 0;
    item.latency_cycles = cfg.default_latency_cycles;
    item.response_stall_cycles = cfg.default_response_stall_cycles;
    item.inter_transaction_gap = 0;
    item.allow_illegal = allow_state_illegal || !(control inside {
      CODEC_CTRL_START, CODEC_CTRL_FLUSH, CODEC_CTRL_STOP, CODEC_CTRL_PING
    });
    finish_item(item);
  endtask

endclass
