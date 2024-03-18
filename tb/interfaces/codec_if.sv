interface codec_if(input logic clk);
  import codec_protocol_pkg::*;

  logic        reset_n;
  logic        req_valid;
  logic        req_ready;
  logic [2:0]  req_cmd;
  logic [1:0]  req_profile;
  logic [12:0] req_width;
  logic [12:0] req_height;
  logic [1:0]  req_frame_type;
  logic [3:0]  req_bit_depth;
  logic [5:0]  req_qp;
  logic [31:0] req_payload;
  logic [2:0]  req_payload_bytes;
  logic [2:0]  req_control;
  logic        req_inject_error;
  logic        tb_allow_illegal;
  logic [3:0]  latency_cycles;

  logic        rsp_valid;
  logic        rsp_ready;
  logic [2:0]  rsp_cmd;
  logic [2:0]  rsp_status;
  logic [31:0] rsp_data;
  logic [15:0] rsp_sequence_id;
  logic        configured;

  clocking drv_cb @(posedge clk);
    default input #1step output #0;
    output req_valid, req_cmd, req_profile, req_width, req_height;
    output req_frame_type, req_bit_depth, req_qp, req_payload;
    output req_payload_bytes, req_control, req_inject_error;
    output tb_allow_illegal;
    output rsp_ready, latency_cycles;
    input  req_ready, rsp_valid, rsp_cmd, rsp_status, rsp_data;
    input  rsp_sequence_id, configured;
  endclocking

  clocking mon_cb @(posedge clk);
    default input #1step;
    input reset_n, req_valid, req_ready, req_cmd, req_profile;
    input req_width, req_height, req_frame_type, req_bit_depth, req_qp;
    input req_payload, req_payload_bytes, req_control, req_inject_error;
    input tb_allow_illegal;
    input latency_cycles, rsp_valid, rsp_ready, rsp_cmd, rsp_status;
    input rsp_data, rsp_sequence_id, configured;
  endclocking

  modport driver(clocking drv_cb, output reset_n);
  modport monitor(clocking mon_cb);
  modport dut(
    input clk, reset_n, req_valid, req_cmd, req_profile, req_width, req_height,
    input req_frame_type, req_bit_depth, req_qp, req_payload,
    input req_payload_bytes, req_control, req_inject_error, latency_cycles,
    input rsp_ready,
    output req_ready, rsp_valid, rsp_cmd, rsp_status, rsp_data,
    output rsp_sequence_id, configured
  );

endinterface
