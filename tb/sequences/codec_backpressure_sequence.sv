class codec_backpressure_sequence extends codec_base_sequence;
  `uvm_object_utils(codec_backpressure_sequence)

  function new(string name = "codec_backpressure_sequence");
    super.new(name);
  endfunction

  task body();
    codec_seq_item item;
    send_config(CODEC_PROFILE_HIGH, 3840, 2160, 12, 40);
    repeat (cfg.transaction_count) begin
      item = codec_seq_item::type_id::create("backpressure_item");
      start_item(item);
      if (!item.randomize() with {
        cmd == CODEC_CMD_DATA;
        payload_bytes == 4;
        frame_type inside {CODEC_FRAME_I, CODEC_FRAME_P, CODEC_FRAME_B};
        latency_cycles inside {[0:7]};
        response_stall_cycles dist {
          [1:2] := 2,
          [3:7] := 5,
          [8:12] := 3
        };
        inter_transaction_gap inside {[0:1]};
        inject_error == 0;
      })
        `uvm_fatal("SEQ/BACKPRESSURE", "failed to randomize stalled transaction")
      finish_item(item);
    end
  endtask

endclass
