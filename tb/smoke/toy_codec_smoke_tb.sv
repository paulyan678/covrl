`timescale 1ns/1ps

module toy_codec_smoke_tb;
  import codec_protocol_pkg::*;

  logic clk = 1'b0;
  always #5ns clk = ~clk;

  codec_if codec_bus(clk);
  toy_codec_adapter adapter(codec_bus);

  function automatic logic [31:0] expected_transform(
    logic [31:0] value,
    logic [1:0] frame_type
  );
    logic [31:0] key;
    key = {8'h80, 8'h38, 6'd23, 4'd8, CODEC_PROFILE_MAIN,
           frame_type, 2'b0};
    return {value[23:0], value[31:24]} ^ key;
  endfunction

  task automatic drive_request(
    input logic [2:0] cmd,
    input logic [31:0] payload,
    input logic [2:0] bytes,
    input logic [2:0] expected_status,
    input logic [31:0] expected_data
  );
    int unsigned cycles;
    @(negedge clk);
    codec_bus.req_cmd           = cmd;
    codec_bus.req_payload       = payload;
    codec_bus.req_payload_bytes = bytes;
    codec_bus.req_valid         = 1'b1;
    cycles = 0;
    do begin
      @(posedge clk);
      cycles++;
      if (cycles > 20)
        $fatal(1, "request handshake timed out");
    end while (!codec_bus.req_ready);
    @(negedge clk);
    codec_bus.req_valid = 1'b0;

    cycles = 0;
    while (!codec_bus.rsp_valid) begin
      @(posedge clk);
      cycles++;
      if (cycles > 20)
        $fatal(1, "response timed out");
    end
    if (codec_bus.rsp_status !== expected_status)
      $fatal(1, "status mismatch: expected %0d got %0d",
             expected_status, codec_bus.rsp_status);
    if (codec_bus.rsp_data !== expected_data)
      $fatal(1, "data mismatch: expected %08x got %08x",
             expected_data, codec_bus.rsp_data);
    @(posedge clk);
  endtask

  initial begin
    codec_bus.reset_n          = 1'b0;
    codec_bus.req_valid        = 1'b0;
    codec_bus.req_cmd          = CODEC_CMD_CONFIG;
    codec_bus.req_profile      = CODEC_PROFILE_MAIN;
    codec_bus.req_width        = 13'd1920;
    codec_bus.req_height       = 13'd1080;
    codec_bus.req_frame_type   = CODEC_FRAME_P;
    codec_bus.req_bit_depth    = 4'd8;
    codec_bus.req_qp           = 6'd23;
    codec_bus.req_payload      = '0;
    codec_bus.req_payload_bytes = 3'd4;
    codec_bus.req_control      = CODEC_CTRL_PING;
    codec_bus.req_inject_error = 1'b0;
    codec_bus.latency_cycles   = 4'd2;
    codec_bus.rsp_ready        = 1'b1;

    repeat (3) @(posedge clk);
    @(negedge clk);
    codec_bus.reset_n = 1'b1;

    drive_request(CODEC_CMD_CONFIG, 32'h0, 3'd0,
                  CODEC_STATUS_OK, 32'h0);
    drive_request(CODEC_CMD_DATA, 32'h1234_5678, 3'd4,
                  CODEC_STATUS_OK,
                  expected_transform(32'h1234_5678, CODEC_FRAME_P));

    codec_bus.req_width = 13'd0;
    drive_request(CODEC_CMD_CONFIG, 32'h0, 3'd0,
                  CODEC_STATUS_BAD_CONFIG, 32'h0);

    $display("TOY_CODEC_SMOKE_PASS");
    $finish;
  end

endmodule
