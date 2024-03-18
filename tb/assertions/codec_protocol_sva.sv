module codec_protocol_sva #(
  parameter int unsigned MAX_REQUEST_WAIT = 64,
  parameter int unsigned MAX_RESPONSE_WAIT = 128
) (codec_if bus);
  import codec_protocol_pkg::*;

  int unsigned outstanding;
  logic [2:0] expected_cmd;
  logic [15:0] expected_sequence_id;

  default clocking cb @(posedge bus.clk); endclocking
  default disable iff (!bus.reset_n);

  property p_request_held_until_ready;
    bus.req_valid && !bus.req_ready |=> bus.req_valid;
  endproperty

  property p_request_stable_when_stalled;
    bus.req_valid && !bus.req_ready |=>
      $stable({bus.req_cmd, bus.req_profile, bus.req_width, bus.req_height,
               bus.req_frame_type, bus.req_bit_depth, bus.req_qp,
               bus.req_payload, bus.req_payload_bytes, bus.req_control,
               bus.req_inject_error});
  endproperty

  property p_response_held_until_ready;
    bus.rsp_valid && !bus.rsp_ready |=> bus.rsp_valid;
  endproperty

  property p_response_stable_when_backpressured;
    bus.rsp_valid && !bus.rsp_ready |=>
      $stable({bus.rsp_cmd, bus.rsp_status, bus.rsp_data,
               bus.rsp_sequence_id});
  endproperty

  property p_request_timeout;
    bus.req_valid |-> ##[0:MAX_REQUEST_WAIT] bus.req_ready;
  endproperty

  property p_response_timeout;
    bus.req_valid && bus.req_ready |-> ##[1:MAX_RESPONSE_WAIT] bus.rsp_valid;
  endproperty

  property p_response_has_request;
    bus.rsp_valid |-> outstanding > 0;
  endproperty

  property p_single_outstanding;
    outstanding <= 1;
  endproperty

  property p_response_order;
    bus.rsp_valid && bus.rsp_ready |->
      bus.rsp_cmd == expected_cmd &&
      bus.rsp_sequence_id == expected_sequence_id;
  endproperty

  property p_legal_config;
    bus.req_valid && bus.req_ready &&
    bus.req_cmd == CODEC_CMD_CONFIG &&
    !bus.tb_allow_illegal && !bus.req_inject_error |->
      codec_config_is_legal(codec_profile_e'(bus.req_profile),
                            bus.req_width, bus.req_height,
                            bus.req_bit_depth, bus.req_qp);
  endproperty

  property p_legal_command;
    bus.req_valid && bus.req_ready && !bus.tb_allow_illegal |->
      bus.req_cmd inside {
        CODEC_CMD_CONFIG, CODEC_CMD_FRAME, CODEC_CMD_DATA, CODEC_CMD_CONTROL
      };
  endproperty

  property p_data_size_valid;
    bus.req_valid && bus.req_ready && bus.req_cmd == CODEC_CMD_DATA &&
    !bus.tb_allow_illegal |-> bus.req_payload_bytes inside {[1:4]};
  endproperty

  property p_frame_type_valid;
    bus.req_valid && bus.req_ready && bus.req_cmd == CODEC_CMD_FRAME &&
    !bus.tb_allow_illegal |-> bus.req_frame_type != CODEC_FRAME_RESERVED;
  endproperty

  property p_config_before_traffic;
    bus.req_valid && bus.req_ready &&
    bus.req_cmd inside {CODEC_CMD_FRAME, CODEC_CMD_DATA} &&
    !bus.tb_allow_illegal |-> bus.configured;
  endproperty

  property p_config_before_stateful_control;
    bus.req_valid && bus.req_ready && bus.req_cmd == CODEC_CMD_CONTROL &&
    bus.req_control != CODEC_CTRL_PING && !bus.tb_allow_illegal |->
      bus.configured;
  endproperty

  property p_no_request_during_reset;
    @(posedge bus.clk) disable iff (1'b0)
      !bus.reset_n |-> !bus.req_valid;
  endproperty

  property p_reset_clears_outputs;
    @(posedge bus.clk) disable iff (1'b0)
      !bus.reset_n |-> !bus.rsp_valid && !bus.configured;
  endproperty

  assert property (p_request_held_until_ready)
    else $error("request valid dropped before handshake");
  assert property (p_request_stable_when_stalled)
    else $error("request changed while stalled");
  assert property (p_response_held_until_ready)
    else $error("response valid dropped under backpressure");
  assert property (p_response_stable_when_backpressured)
    else $error("response changed under backpressure");
  assert property (p_request_timeout)
    else $error("request handshake timeout");
  assert property (p_response_timeout)
    else $error("response timeout");
  assert property (p_response_has_request)
    else $error("response observed without an outstanding request");
  assert property (p_single_outstanding)
    else $error("more than one request is outstanding");
  assert property (p_response_order)
    else $error("response command or sequence is out of order");
  assert property (p_legal_config)
    else $error("configuration fields are illegal");
  assert property (p_legal_command)
    else $error("invalid command transition");
  assert property (p_data_size_valid)
    else $error("data transaction has invalid byte count");
  assert property (p_frame_type_valid)
    else $error("frame transaction uses a reserved frame type");
  assert property (p_config_before_traffic)
    else $error("frame or data transaction preceded legal configuration");
  assert property (p_config_before_stateful_control)
    else $error("stateful control preceded legal configuration");
  assert property (p_no_request_during_reset)
    else $error("request valid asserted during reset");
  assert property (p_reset_clears_outputs)
    else $error("reset did not clear response or configuration state");

  always_ff @(posedge bus.clk or negedge bus.reset_n) begin
    if (!bus.reset_n) begin
      outstanding <= 0;
      expected_cmd <= CODEC_CMD_CONFIG;
      expected_sequence_id <= 0;
    end else begin
      case ({bus.req_valid && bus.req_ready, bus.rsp_valid && bus.rsp_ready})
        2'b10: outstanding <= outstanding + 1;
        2'b01: outstanding <= outstanding - 1;
        default: outstanding <= outstanding;
      endcase
      if (bus.req_valid && bus.req_ready)
        expected_cmd <= bus.req_cmd;
      if (bus.rsp_valid && bus.rsp_ready)
        expected_sequence_id <= expected_sequence_id + 16'd1;
    end
  end

endmodule
