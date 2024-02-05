class codec_monitor extends uvm_monitor;
  codec_env_cfg cfg;
  virtual codec_if vif;
  uvm_analysis_port #(codec_seq_item) request_ap;
  uvm_analysis_port #(codec_seq_item) response_ap;
  uvm_analysis_port #(codec_seq_item) reset_ap;

  longint unsigned cycle_count;
  longint unsigned request_cycles[$];
  int unsigned response_stall_count;
  bit last_reset_n;

  `uvm_component_utils(codec_monitor)

  function new(string name = "codec_monitor", uvm_component parent = null);
    super.new(name, parent);
    request_ap = new("request_ap", this);
    response_ap = new("response_ap", this);
    reset_ap = new("reset_ap", this);
  endfunction

  function void build_phase(uvm_phase phase);
    super.build_phase(phase);
    if (!uvm_config_db #(codec_env_cfg)::get(this, "", "cfg", cfg))
      `uvm_fatal("MON/CFG", "codec_env_cfg was not provided to monitor")
    vif = cfg.vif;
  endfunction

  task run_phase(uvm_phase phase);
    codec_seq_item item;
    cycle_count = 0;
    response_stall_count = 0;
    last_reset_n = 0;
    forever begin
      @(vif.mon_cb);
      cycle_count++;

      if (!vif.mon_cb.reset_n) begin
        if (last_reset_n) begin
          item = codec_seq_item::type_id::create("observed_reset");
          item.observation = CODEC_OBS_RESET;
          item.configured_state = 0;
          reset_ap.write(item);
        end
        request_cycles.delete();
        response_stall_count = 0;
      end else begin
        if (vif.mon_cb.req_valid && vif.mon_cb.req_ready) begin
          item = capture_request();
          request_cycles.push_back(cycle_count);
          response_stall_count = 0;
          request_ap.write(item);
          `uvm_info("MON/REQ", item.convert2string(), UVM_HIGH)
        end

        if (vif.mon_cb.rsp_valid && !vif.mon_cb.rsp_ready)
          response_stall_count++;

        if (vif.mon_cb.rsp_valid && vif.mon_cb.rsp_ready) begin
          item = capture_response();
          item.response_stall_cycles = response_stall_count;
          if (request_cycles.size() == 0) begin
            `uvm_error("MON/ORDER", "response observed without a pending request")
          end else begin
            item.observed_latency = cycle_count - request_cycles.pop_front();
          end
          response_ap.write(item);
          response_stall_count = 0;
          `uvm_info("MON/RSP", item.convert2string(), UVM_HIGH)
        end
      end
      last_reset_n = vif.mon_cb.reset_n;
    end
  endtask

  function codec_seq_item capture_request();
    codec_seq_item item;
    item = codec_seq_item::type_id::create("observed_request");
    item.observation          = CODEC_OBS_REQUEST;
    item.cmd                  = codec_cmd_e'(vif.mon_cb.req_cmd);
    item.profile              = codec_profile_e'(vif.mon_cb.req_profile);
    item.width                = vif.mon_cb.req_width;
    item.height               = vif.mon_cb.req_height;
    item.frame_type           = codec_frame_type_e'(vif.mon_cb.req_frame_type);
    item.bit_depth            = vif.mon_cb.req_bit_depth;
    item.qp                   = vif.mon_cb.req_qp;
    item.payload              = vif.mon_cb.req_payload;
    item.payload_bytes        = vif.mon_cb.req_payload_bytes;
    item.control              = codec_control_e'(vif.mon_cb.req_control);
    item.inject_error         = vif.mon_cb.req_inject_error;
    item.latency_cycles       = vif.mon_cb.latency_cycles;
    item.configured_state     = vif.mon_cb.configured;
    return item;
  endfunction

  function codec_seq_item capture_response();
    codec_seq_item item;
    item = codec_seq_item::type_id::create("observed_response");
    item.observation      = CODEC_OBS_RESPONSE;
    item.cmd              = codec_cmd_e'(vif.mon_cb.rsp_cmd);
    item.status           = codec_status_e'(vif.mon_cb.rsp_status);
    item.response_data    = vif.mon_cb.rsp_data;
    item.sequence_id      = vif.mon_cb.rsp_sequence_id;
    item.configured_state = vif.mon_cb.configured;
    return item;
  endfunction

endclass
