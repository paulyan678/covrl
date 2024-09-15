module toy_codec_state_sva (codec_if bus);
  import codec_protocol_pkg::*;

  default clocking cb @(posedge bus.clk); endclocking
  default disable iff (!bus.reset_n);

  // The toy adapter updates configured state one sampled cycle after the
  // accepted request. Real-IP adapters may replace this timing-specific module.
  property p_configured_rise_has_legal_config;
    $rose(bus.configured) |-> $past(
      bus.req_valid && bus.req_ready &&
      bus.req_cmd == CODEC_CMD_CONFIG && !bus.req_inject_error &&
      codec_config_is_legal(codec_profile_e'(bus.req_profile),
                            bus.req_width, bus.req_height,
                            bus.req_bit_depth, bus.req_qp));
  endproperty

  property p_configured_fall_has_stop;
    $fell(bus.configured) |-> $past(
      bus.req_valid && bus.req_ready &&
      bus.req_cmd == CODEC_CMD_CONTROL &&
      bus.req_control == CODEC_CTRL_STOP && !bus.req_inject_error);
  endproperty

  assert property (p_configured_rise_has_legal_config)
    else $error("toy configured state rose without a legal configuration");
  assert property (p_configured_fall_has_stop)
    else $error("toy configured state fell without an accepted stop");

endmodule
