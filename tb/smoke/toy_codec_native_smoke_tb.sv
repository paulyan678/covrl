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

  int expected_sequence = 0;
  int checked_responses = 0;

  task automatic reset_dut();
    @(negedge clk);
    reset_n = 0;
    req_valid = 0;
    rsp_ready = 0;
    repeat (3) @(negedge clk);
    if (rsp_valid !== 0 || configured !== 0)
      $fatal(1, "reset did not clear response and configuration");
    reset_n = 1;
    expected_sequence = 0;
  endtask

  task automatic transact(
    input logic [2:0] command,
    input logic [31:0] payload,
    input logic [2:0] bytes,
    input logic [2:0] expected_status,
    input logic [31:0] expected_data,
    input int stall_cycles = 0
  );
    int cycles;
    @(negedge clk);
    rsp_ready = 0;
    req_cmd = command;
    req_payload = payload;
    req_payload_bytes = bytes;
    req_valid = 1;
    cycles = 0;
    do begin
      @(posedge clk);
      cycles++;
      if (cycles > 32) $fatal(1, "request timeout");
    end while (!req_ready);
    @(negedge clk);
    req_valid = 0;
    cycles = 0;
    while (!rsp_valid) begin
      @(negedge clk);
      cycles++;
      if (cycles > 32) $fatal(1, "response timeout");
    end
    // Sample away from NBA updates; hold ready low to check every response.
    for (int i = 0; i <= stall_cycles; i++) begin
      if (rsp_valid !== 1 || rsp_status !== expected_status ||
          rsp_data !== expected_data || rsp_cmd !== command ||
          rsp_sequence_id !== expected_sequence[15:0] || req_ready !== 0)
        $fatal(1, "response %0d mismatch cmd=%0d status=%0d data=%08x seq=%0d",
               checked_responses, rsp_cmd, rsp_status, rsp_data, rsp_sequence_id);
      @(negedge clk);
    end
    rsp_ready = 1;
    @(negedge clk);
    if (rsp_valid !== 0) $fatal(1, "response not consumed");
    expected_sequence++;
    checked_responses++;
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
    reset_dut();
    transact(CODEC_CMD_DATA, 0, 4, CODEC_STATUS_NOT_CONFIGURED, 0);
    transact(CODEC_CMD_CONTROL, 0, 0, CODEC_STATUS_OK, 32'hc0de_c0de);
    transact(CODEC_CMD_CONFIG, 0, 0, CODEC_STATUS_OK, 0);
    if (configured !== 1) $fatal(1, "legal config was not applied");

    // Known answer for MAIN / 1920x1080 / 8-bit / QP23 / P-frame.
    // Exercise immediate and delayed responses, including maximum RTL latency.
    for (int delay = 0; delay <= 15; delay++) begin
      latency_cycles = delay[3:0];
      transact(CODEC_CMD_DATA, 32'h1234_5678, 4, CODEC_STATUS_OK,
               32'hb46e_2606, 3);
    end
    latency_cycles = 2;
    req_width = 0;
    transact(CODEC_CMD_CONFIG, 0, 0, CODEC_STATUS_BAD_CONFIG, 0);
    if (configured !== 1) $fatal(1, "invalid config destroyed prior state");
    req_width = 1920;
    transact(CODEC_CMD_DATA, 32'h1234_5678, 0, CODEC_STATUS_BAD_INPUT, 0);
    req_frame_type = CODEC_FRAME_RESERVED;
    transact(CODEC_CMD_FRAME, 0, 4, CODEC_STATUS_BAD_INPUT, 0);
    req_frame_type = CODEC_FRAME_P;
    req_inject_error = 1;
    transact(CODEC_CMD_DATA, 0, 4, CODEC_STATUS_INJECTED_ERROR, 0);
    req_inject_error = 0;
    req_control = 7;
    transact(CODEC_CMD_CONTROL, 0, 0, CODEC_STATUS_BAD_CONTROL, 0);
    req_control = CODEC_CTRL_FLUSH;
    transact(CODEC_CMD_CONTROL, 0, 0, CODEC_STATUS_OK, 32'hf1f1_f1f1);
    req_control = CODEC_CTRL_STOP;
    transact(CODEC_CMD_CONTROL, 0, 0, CODEC_STATUS_OK, 0);
    if (configured !== 0) $fatal(1, "STOP did not clear configuration");
    transact(CODEC_CMD_DATA, 0, 4, CODEC_STATUS_NOT_CONFIGURED, 0);

    // Reset must cancel an in-flight response, not emit it after recovery.
    latency_cycles = 15;
    @(negedge clk);
    req_cmd = CODEC_CMD_CONFIG;
    req_valid = 1;
    @(posedge clk);
    if (!req_ready) $fatal(1, "reset scenario request was not accepted");
    @(negedge clk);
    req_valid = 0;
    reset_dut();
    repeat (20) begin
      @(negedge clk);
      if (rsp_valid !== 0) $fatal(1, "stale response after reset");
    end
    latency_cycles = 0;
    req_control = CODEC_CTRL_PING;
    transact(CODEC_CMD_CONTROL, 0, 0, CODEC_STATUS_OK, 32'hc0de_c0de, 2);
    $display("TOY_CODEC_SMOKE_PASS responses=%0d", checked_responses);
    $finish;
  end

endmodule
