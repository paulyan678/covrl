`timescale 1ns/1ps

module tb_top;
  import uvm_pkg::*;
  import codec_protocol_pkg::*;
  import codec_uvm_pkg::*;

  logic clk = 1'b0;
  always #5ns clk = ~clk;

  codec_if codec_bus(clk);
  toy_codec_adapter adapter(codec_bus);
  codec_protocol_sva assertions(codec_bus);

  initial begin
    uvm_config_db #(virtual codec_if)::set(
      null, "uvm_test_top", "vif", codec_bus
    );
    run_test();
  end

  initial begin
    int waves_enabled;
    string waveform_file;
    waves_enabled = 0;
    waveform_file = "outputs/waves/codec.vcd";
    void'($value$plusargs("WAVES=%d", waves_enabled));
    void'($value$plusargs("WAVEFORM_FILE=%s", waveform_file));
    if (waves_enabled) begin
      $dumpfile(waveform_file);
      $dumpvars(0, tb_top);
    end
  end

endmodule
