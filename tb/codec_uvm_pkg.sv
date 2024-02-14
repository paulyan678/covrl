package codec_uvm_pkg;
  import uvm_pkg::*;
  import codec_protocol_pkg::*;
  `include "uvm_macros.svh"

  `include "agents/codec_seq_item.sv"
  `include "env/codec_env_cfg.sv"
  `include "agents/codec_sequencer.sv"
  `include "agents/codec_driver.sv"
  `include "agents/codec_monitor.sv"
  `include "agents/codec_agent.sv"
  `include "env/codec_reference_model.sv"
  `include "scoreboard/codec_scoreboard.sv"
  `include "coverage/codec_coverage.sv"
  `include "env/codec_env.sv"
  `include "sequences/codec_base_sequence.sv"
  `include "sequences/codec_directed_sequence.sv"
  `include "sequences/codec_random_sequence.sv"
  `include "sequences/codec_backpressure_sequence.sv"
  `include "sequences/codec_reset_sequence.sv"
  `include "sequences/codec_error_sequence.sv"
  `include "tests/codec_base_test.sv"

endpackage
