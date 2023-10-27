module toy_codec (
  input  logic        clk,
  input  logic        reset_n,

  input  logic        req_valid,
  output logic        req_ready,
  input  logic [2:0]  req_cmd,
  input  logic [1:0]  req_profile,
  input  logic [12:0] req_width,
  input  logic [12:0] req_height,
  input  logic [1:0]  req_frame_type,
  input  logic [3:0]  req_bit_depth,
  input  logic [5:0]  req_qp,
  input  logic [31:0] req_payload,
  input  logic [2:0]  req_payload_bytes,
  input  logic [2:0]  req_control,
  input  logic        req_inject_error,
  input  logic [3:0]  latency_cycles,

  output logic        rsp_valid,
  input  logic        rsp_ready,
  output logic [2:0]  rsp_cmd,
  output logic [2:0]  rsp_status,
  output logic [31:0] rsp_data,
  output logic [15:0] rsp_sequence_id,
  output logic        configured
);
  import codec_protocol_pkg::*;

  codec_profile_e configured_profile;
  logic [12:0]    configured_width;
  logic [12:0]    configured_height;
  logic [3:0]     configured_bit_depth;
  logic [5:0]     configured_qp;
  logic [15:0]    next_sequence_id;

  function automatic logic [31:0] transform_payload(
    input logic [31:0] value,
    input logic [1:0] frame_type
  );
    logic [31:0] codec_key;
    codec_key = {
      configured_width[7:0], configured_height[7:0], configured_qp,
      configured_bit_depth, configured_profile, frame_type, 2'b0
    };
    return {value[23:0], value[31:24]} ^ codec_key;
  endfunction

  // The one-entry response register is intentionally simple. Later commits add
  // bounded processing latency without changing this external contract.
  assign req_ready = !rsp_valid || rsp_ready;

  always_ff @(posedge clk or negedge reset_n) begin
    if (!reset_n) begin
      configured          <= 1'b0;
      configured_profile  <= CODEC_PROFILE_BASELINE;
      configured_width    <= '0;
      configured_height   <= '0;
      configured_bit_depth <= 4'd8;
      configured_qp       <= '0;
      next_sequence_id    <= '0;
      rsp_valid           <= 1'b0;
      rsp_cmd             <= CODEC_CMD_CONFIG;
      rsp_status          <= CODEC_STATUS_OK;
      rsp_data            <= '0;
      rsp_sequence_id     <= '0;
    end else begin
      if (rsp_valid && rsp_ready)
        rsp_valid <= 1'b0;

      if (req_valid && req_ready) begin
        rsp_valid       <= 1'b1;
        rsp_cmd         <= req_cmd;
        rsp_data        <= '0;
        rsp_sequence_id <= next_sequence_id;
        next_sequence_id <= next_sequence_id + 16'd1;

        if (req_cmd == CODEC_CMD_CONFIG) begin
          if (codec_config_is_legal(
            codec_profile_e'(req_profile), req_width, req_height,
            req_bit_depth, req_qp
          )) begin
            configured           <= 1'b1;
            configured_profile   <= codec_profile_e'(req_profile);
            configured_width     <= req_width;
            configured_height    <= req_height;
            configured_bit_depth <= req_bit_depth;
            configured_qp        <= req_qp;
            rsp_status           <= CODEC_STATUS_OK;
          end else begin
            configured <= 1'b0;
            rsp_status <= CODEC_STATUS_BAD_CONFIG;
          end
        end else if (req_cmd inside {CODEC_CMD_FRAME, CODEC_CMD_DATA}) begin
          if (configured) begin
            rsp_status <= CODEC_STATUS_OK;
            rsp_data   <= transform_payload(req_payload, req_frame_type);
          end else begin
            rsp_status <= CODEC_STATUS_NOT_CONFIGURED;
          end
        end else begin
          rsp_status <= CODEC_STATUS_BAD_CONTROL;
        end
      end
    end
  end

  // Reserved until later behavioral features are enabled.
  logic _unused;
  assign _unused = ^{req_payload_bytes, req_control, req_inject_error,
                     latency_cycles};

endmodule
