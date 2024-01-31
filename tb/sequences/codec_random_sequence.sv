class codec_random_sequence extends codec_base_sequence;
  `uvm_object_utils(codec_random_sequence)

  function new(string name = "codec_random_sequence");
    super.new(name);
  endfunction

  function codec_profile_e choose_profile();
    codec_profile_e choices[$];
    if (cfg.enable_baseline_profile)
      choices.push_back(CODEC_PROFILE_BASELINE);
    if (cfg.enable_main_profile)
      choices.push_back(CODEC_PROFILE_MAIN);
    if (cfg.enable_high_profile)
      choices.push_back(CODEC_PROFILE_HIGH);
    return choices[$urandom_range(choices.size() - 1)];
  endfunction

  task send_random_config();
    codec_seq_item item;
    codec_profile_e selected_profile;
    selected_profile = choose_profile();
    item = codec_seq_item::type_id::create("random_config");
    start_item(item);
    if (!item.randomize() with {
      cmd == CODEC_CMD_CONFIG;
      profile == local::selected_profile;
      width dist {640 := 2, 1280 := 3, 1920 := 3, 3840 := 2};
      height dist {480 := 2, 720 := 3, 1080 := 3, 2160 := 2};
      latency_cycles inside {[0:7]};
      response_stall_cycles == 0;
      inject_error == 0;
    })
      `uvm_fatal("SEQ/RAND_CFG", "failed to randomize legal configuration")
    finish_item(item);
  endtask

  task body();
    codec_seq_item item;
    int unsigned max_stall;
    bit allow_b_frames;
    max_stall = cfg.enable_backpressure ? 8 : 0;
    allow_b_frames = cfg.enable_b_frames;
    send_random_config();

    repeat (cfg.transaction_count) begin
      item = codec_seq_item::type_id::create("random_traffic");
      start_item(item);
      if (!item.randomize() with {
        cmd dist {
          CODEC_CMD_FRAME := 30,
          CODEC_CMD_DATA := 60,
          CODEC_CMD_CONTROL := 10
        };
        if (cmd == CODEC_CMD_CONTROL)
          control inside {CODEC_CTRL_START, CODEC_CTRL_FLUSH, CODEC_CTRL_PING};
        if (!local::allow_b_frames)
          frame_type != CODEC_FRAME_B;
        inject_error == 0;
        response_stall_cycles inside {[0:local::max_stall]};
        inter_transaction_gap inside {[0:3]};
      })
        `uvm_fatal("SEQ/RANDOMIZE", "failed to randomize codec traffic")
      finish_item(item);
    end
  endtask

endclass
