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
  logic           processing;
  logic [3:0]     delay_count;
  logic [2:0]     pending_cmd;
  logic [2:0]     pending_status;
  logic [31:0]    pending_data;
  logic [15:0]    pending_sequence_id;
  logic [2:0]     evaluated_status;
  logic [31:0]    evaluated_data;

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

  always_comb begin
    evaluated_status = CODEC_STATUS_BAD_CONTROL;
    evaluated_data   = '0;
    if (req_inject_error) begin
      evaluated_status = CODEC_STATUS_INJECTED_ERROR;
    end else if (req_cmd == CODEC_CMD_CONFIG) begin
      evaluated_status = codec_config_is_legal(
        codec_profile_e'(req_profile), req_width, req_height,
        req_bit_depth, req_qp
      ) ? CODEC_STATUS_OK : CODEC_STATUS_BAD_CONFIG;
    end else if (req_cmd == CODEC_CMD_FRAME) begin
      if (!configured)
        evaluated_status = CODEC_STATUS_NOT_CONFIGURED;
      else if (req_frame_type == CODEC_FRAME_RESERVED)
        evaluated_status = CODEC_STATUS_BAD_INPUT;
      else begin
        evaluated_status = CODEC_STATUS_OK;
        evaluated_data = transform_payload(req_payload, req_frame_type);
      end
    end else if (req_cmd == CODEC_CMD_DATA) begin
      if (!configured)
        evaluated_status = CODEC_STATUS_NOT_CONFIGURED;
      else if (!(req_payload_bytes == 3'd1 || req_payload_bytes == 3'd2 ||
                 req_payload_bytes == 3'd3 || req_payload_bytes == 3'd4))
        evaluated_status = CODEC_STATUS_BAD_INPUT;
      else begin
        evaluated_status = CODEC_STATUS_OK;
        evaluated_data = transform_payload(req_payload, req_frame_type);
      end
    end else if (req_cmd == CODEC_CMD_CONTROL) begin
      if (req_control == CODEC_CTRL_PING) begin
        evaluated_status = CODEC_STATUS_OK;
        evaluated_data = 32'hc0de_c0de;
      end else if (!(req_control == CODEC_CTRL_START ||
                     req_control == CODEC_CTRL_FLUSH ||
                     req_control == CODEC_CTRL_STOP)) begin
        evaluated_status = CODEC_STATUS_BAD_CONTROL;
      end else if (!configured) begin
        evaluated_status = CODEC_STATUS_NOT_CONFIGURED;
      end else begin
        evaluated_status = CODEC_STATUS_OK;
        if (req_control == CODEC_CTRL_FLUSH)
          evaluated_data = 32'hf1f1_f1f1;
      end
    end
  end

  // A request is accepted only when both the processing slot and held response
  // slot are empty. Once valid, a response remains stable through backpressure.
  assign req_ready = !processing && !rsp_valid;

  always_ff @(posedge clk or negedge reset_n) begin
    if (!reset_n) begin
      configured          <= 1'b0;
      configured_profile  <= CODEC_PROFILE_BASELINE;
      configured_width    <= '0;
      configured_height   <= '0;
      configured_bit_depth <= 4'd8;
      configured_qp       <= '0;
      next_sequence_id    <= '0;
      processing          <= 1'b0;
      delay_count         <= '0;
      pending_cmd         <= CODEC_CMD_CONFIG;
      pending_status      <= CODEC_STATUS_OK;
      pending_data        <= '0;
      pending_sequence_id <= '0;
      rsp_valid           <= 1'b0;
      rsp_cmd             <= CODEC_CMD_CONFIG;
      rsp_status          <= CODEC_STATUS_OK;
      rsp_data            <= '0;
      rsp_sequence_id     <= '0;
    end else begin
      if (rsp_valid && rsp_ready)
        rsp_valid <= 1'b0;

      if (processing) begin
        if (delay_count == 0) begin
          rsp_valid       <= 1'b1;
          rsp_cmd         <= pending_cmd;
          rsp_status      <= pending_status;
          rsp_data        <= pending_data;
          rsp_sequence_id <= pending_sequence_id;
          processing      <= 1'b0;
        end else begin
          delay_count <= delay_count - 4'd1;
        end
      end

      if (req_valid && req_ready) begin
        next_sequence_id <= next_sequence_id + 16'd1;

        if (!req_inject_error && req_cmd == CODEC_CMD_CONFIG) begin
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
          end
        end else if (!req_inject_error &&
                     req_cmd == CODEC_CMD_CONTROL &&
                     req_control == CODEC_CTRL_STOP &&
                     evaluated_status == CODEC_STATUS_OK) begin
          configured <= 1'b0;
        end

        if (latency_cycles == 0) begin
          rsp_valid       <= 1'b1;
          rsp_cmd         <= req_cmd;
          rsp_status      <= evaluated_status;
          rsp_data        <= evaluated_data;
          rsp_sequence_id <= next_sequence_id;
        end else begin
          processing          <= 1'b1;
          delay_count         <= latency_cycles - 4'd1;
          pending_cmd         <= req_cmd;
          pending_status      <= evaluated_status;
          pending_data        <= evaluated_data;
          pending_sequence_id <= next_sequence_id;
        end
      end
    end
  end

endmodule
