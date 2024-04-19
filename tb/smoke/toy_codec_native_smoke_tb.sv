`timescale 1ns/1ps

module toy_codec_native_smoke_tb;
  import codec_protocol_pkg::*;

  logic clk = 1'b0;
  logic reset_n;
  logic req_valid;
  logic req_ready;
  logic [2:0] req_cmd;
  logic [1:0] req_profile;
  logic [12:0] req_width;
  logic [12:0] req_height;
  logic [1:0] req_frame_type;
  logic [3:0] req_bit_depth;
  logic [5:0] req_qp;
  logic [31:0] req_payload;
  logic [2:0] req_payload_bytes;
  logic [2:0] req_control;
  logic req_inject_error;
  logic [3:0] latency_cycles;
  logic rsp_valid;
  logic rsp_ready;
  logic [2:0] rsp_cmd;
  logic [2:0] rsp_status;
  logic [31:0] rsp_data;
  logic [15:0] rsp_sequence_id;
  logic configured;

  always #5 clk = ~clk;

  toy_codec dut (
    .clk, .reset_n, .req_valid, .req_ready, .req_cmd, .req_profile,
    .req_width, .req_height, .req_frame_type, .req_bit_depth, .req_qp,
    .req_payload, .req_payload_bytes, .req_control, .req_inject_error,
    .latency_cycles, .rsp_valid, .rsp_ready, .rsp_cmd, .rsp_status,
    .rsp_data, .rsp_sequence_id, .configured
  );

  function automatic logic [31:0] expected_transform(logic [31:0] value);
    logic [31:0] key;
    key = {8'h80, 8'h38, 6'd23, 4'd8, CODEC_PROFILE_MAIN,
           CODEC_FRAME_P, 2'b0};
    return {value[23:0], value[31:24]} ^ key;
  endfunction

  task automatic transact(
    input logic [2:0] command,
    input logic [31:0] payload,
    input logic [2:0] bytes,
    input logic [2:0] expected_status,
    input logic [31:0] expected_data
  );
    int cycles;
    @(negedge clk);
    req_cmd = command;
    req_payload = payload;
    req_payload_bytes = bytes;
    req_valid = 1'b1;
    cycles = 0;
    do begin
      @(posedge clk);
      cycles++;
      if (cycles > 20)
        $fatal(1, "request timeout");
    end while (!req_ready);
    @(negedge clk);
    req_valid = 1'b0;
    cycles = 0;
    while (!rsp_valid) begin
      @(posedge clk);
      cycles++;
      if (cycles > 20)
        $fatal(1, "response timeout");
    end
    if (rsp_status !== expected_status || rsp_data !== expected_data)
      $fatal(1, "response mismatch status=%0d data=%08x", rsp_status, rsp_data);
    @(posedge clk);
  endtask

  initial begin
    int waves_enabled;
    string waveform_file;
    waves_enabled = 0;
    waveform_file = "waves.vcd";
    void'($value$plusargs("WAVES=%d", waves_enabled));
    void'($value$plusargs("WAVEFORM_FILE=%s", waveform_file));
    if (waves_enabled) begin
      $dumpfile(waveform_file);
      $dumpvars(0, toy_codec_native_smoke_tb);
    end
  end

  initial begin
    reset_n = 0;
    req_valid = 0;
    req_cmd = CODEC_CMD_CONFIG;
    req_profile = CODEC_PROFILE_MAIN;
    req_width = 1920;
    req_height = 1080;
    req_frame_type = CODEC_FRAME_P;
    req_bit_depth = 8;
    req_qp = 23;
    req_payload = 0;
    req_payload_bytes = 4;
    req_control = CODEC_CTRL_PING;
    req_inject_error = 0;
    latency_cycles = 2;
    rsp_ready = 1;
    repeat (3) @(posedge clk);
    @(negedge clk);
    reset_n = 1;

    transact(CODEC_CMD_CONFIG, 0, 0, CODEC_STATUS_OK, 0);
    transact(CODEC_CMD_DATA, 32'h1234_5678, 4, CODEC_STATUS_OK,
             expected_transform(32'h1234_5678));
    req_width = 0;
    transact(CODEC_CMD_CONFIG, 0, 0, CODEC_STATUS_BAD_CONFIG, 0);
    $display("TOY_CODEC_SMOKE_PASS");
    $finish;
  end

endmodule
