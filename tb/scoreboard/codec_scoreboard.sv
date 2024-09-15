`uvm_analysis_imp_decl(_expected)
`uvm_analysis_imp_decl(_actual)
`uvm_analysis_imp_decl(_reset)

class codec_scoreboard extends uvm_scoreboard;
  codec_env_cfg cfg;
  uvm_analysis_imp_expected #(codec_seq_item, codec_scoreboard) expected_imp;
  uvm_analysis_imp_actual #(codec_seq_item, codec_scoreboard) actual_imp;
  uvm_analysis_imp_reset #(codec_seq_item, codec_scoreboard) reset_imp;

  codec_seq_item expected_q[$];
  longint unsigned expected_cycle_q[$];
  longint unsigned cycle_count;
  int unsigned match_count;
  int unsigned mismatches;
  int unsigned unexpected;
  int unsigned resets;
  int unsigned timeouts;

  `uvm_component_utils(codec_scoreboard)

  function new(string name = "codec_scoreboard", uvm_component parent = null);
    super.new(name, parent);
    expected_imp = new("expected_imp", this);
    actual_imp = new("actual_imp", this);
    reset_imp = new("reset_imp", this);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(codec_env_cfg)::get(this, "", "cfg", cfg))
      `uvm_fatal("SB/CFG", "codec_env_cfg was not provided to scoreboard")
  endfunction

  task run_phase(uvm_phase phase);
    codec_seq_item timed_out_item;
    cycle_count = 0;
    forever begin
      @(cfg.vif.mon_cb);
      cycle_count++;
      if (!cfg.vif.mon_cb.reset_n)
        continue;
      // The monitor owns the response handshake at this edge. Do not let
      // scheduler ordering expire it before write_actual consumes it.
      if (cfg.vif.mon_cb.rsp_valid && cfg.vif.mon_cb.rsp_ready)
        continue;
      while (expected_q.size() > 0 && expected_cycle_q.size() > 0 &&
             cycle_count - expected_cycle_q[0] > cfg.scoreboard_timeout_cycles) begin
        timed_out_item = expected_q.pop_front();
        void'(expected_cycle_q.pop_front());
        mismatches++;
        timeouts++;
        `uvm_error("SB/TIMEOUT", $sformatf(
          "expected response exceeded %0d cycles: %s",
          cfg.scoreboard_timeout_cycles, timed_out_item.convert2string()))
      end
    end
  endtask

  function void write_expected(codec_seq_item item);
    codec_seq_item copy;
    $cast(copy, item.clone());
    expected_q.push_back(copy);
    expected_cycle_q.push_back(item.observed_cycle);
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
    if (expected_cycle_q.size() == 0)
      `uvm_fatal("SB/AGE", "expected response age queue is inconsistent")
    void'(expected_cycle_q.pop_front());
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
      match_count++;
      `uvm_info("SB/MATCH", actual.convert2string(), UVM_HIGH)
    end else begin
      mismatches++;
    end
  endfunction

  function void write_reset(codec_seq_item item);
    int unsigned discarded;
    discarded = expected_q.size();
    expected_q.delete();
    expected_cycle_q.delete();
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
      "matches=%0d mismatches=%0d unexpected=%0d resets=%0d timeouts=%0d",
      match_count, mismatches, unexpected, resets, timeouts), UVM_LOW)
  endfunction

endclass
