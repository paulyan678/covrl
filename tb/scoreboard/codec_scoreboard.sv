`uvm_analysis_imp_decl(_expected)
`uvm_analysis_imp_decl(_actual)
`uvm_analysis_imp_decl(_reset)

class codec_scoreboard extends uvm_scoreboard;
  uvm_analysis_imp_expected #(codec_seq_item, codec_scoreboard) expected_imp;
  uvm_analysis_imp_actual #(codec_seq_item, codec_scoreboard) actual_imp;
  uvm_analysis_imp_reset #(codec_seq_item, codec_scoreboard) reset_imp;

  codec_seq_item expected_q[$];
  int unsigned matches;
  int unsigned mismatches;
  int unsigned unexpected;
  int unsigned resets;

  `uvm_component_utils(codec_scoreboard)

  function new(string name = "codec_scoreboard", uvm_component parent = null);
    super.new(name, parent);
    expected_imp = new("expected_imp", this);
    actual_imp = new("actual_imp", this);
    reset_imp = new("reset_imp", this);
  endfunction

  function void write_expected(codec_seq_item item);
    codec_seq_item copy;
    $cast(copy, item.clone());
    expected_q.push_back(copy);
  endfunction

  function void write_actual(codec_seq_item actual);
    codec_seq_item expected;
    bit matched;

    if (expected_q.size() == 0) begin
      unexpected++;
      `uvm_error("SB/UNEXPECTED", $sformatf(
        "unexpected response with no prediction: %s", actual.convert2string()))
      return;
    end

    expected = expected_q.pop_front();
    matched = 1;
    if (actual.sequence_id !== expected.sequence_id) begin
      matched = 0;
      `uvm_error("SB/ORDER", $sformatf(
        "sequence mismatch expected=%0d actual=%0d",
        expected.sequence_id, actual.sequence_id))
    end
    if (actual.cmd !== expected.cmd) begin
      matched = 0;
      `uvm_error("SB/CMD", $sformatf(
        "command mismatch expected=%s actual=%s",
        expected.cmd.name(), actual.cmd.name()))
    end
    if (actual.status !== expected.status) begin
      matched = 0;
      `uvm_error("SB/STATUS", $sformatf(
        "status mismatch expected=%s actual=%s",
        expected.status.name(), actual.status.name()))
    end
    if (actual.response_data !== expected.response_data) begin
      matched = 0;
      `uvm_error("SB/DATA", $sformatf(
        "data mismatch expected=%08x actual=%08x",
        expected.response_data, actual.response_data))
    end
    if (actual.configured_state !== expected.configured_state) begin
      matched = 0;
      `uvm_error("SB/STATE", $sformatf(
        "configured-state mismatch expected=%0b actual=%0b",
        expected.configured_state, actual.configured_state))
    end

    if (matched) begin
      matches++;
      `uvm_info("SB/MATCH", actual.convert2string(), UVM_HIGH)
    end else begin
      mismatches++;
    end
  endfunction

  function void write_reset(codec_seq_item item);
    int unsigned discarded;
    discarded = expected_q.size();
    expected_q.delete();
    resets++;
    if (discarded > 0)
      `uvm_info("SB/RESET", $sformatf(
        "reset discarded %0d pending predictions", discarded), UVM_MEDIUM)
  endfunction

  function void check_phase(uvm_phase phase);
    super.check_phase(phase);
    if (expected_q.size() != 0) begin
      mismatches += expected_q.size();
      `uvm_error("SB/MISSING", $sformatf(
        "%0d expected responses were never observed", expected_q.size()))
    end
  endfunction

  function void report_phase(uvm_phase phase);
    super.report_phase(phase);
    `uvm_info("SB/SUMMARY", $sformatf(
      "matches=%0d mismatches=%0d unexpected=%0d resets=%0d",
      matches, mismatches, unexpected, resets), UVM_LOW)
  endfunction

endclass
