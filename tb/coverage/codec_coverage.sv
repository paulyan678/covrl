class codec_coverage extends uvm_subscriber #(codec_seq_item);
  codec_cmd_e sampled_cmd;
  codec_profile_e sampled_profile;
  codec_resolution_e sampled_resolution;
  codec_frame_type_e sampled_frame_type;
  codec_control_e sampled_control;
  codec_status_e sampled_status;
  logic [3:0] sampled_bit_depth;
  logic [5:0] sampled_qp;
  logic [2:0] sampled_payload_bytes;
  int unsigned sampled_latency;
  bit sampled_legal_config;
  bit sampled_injected_error;
  bit sampled_configured;
  bit sampled_reset_with_pending;
  int unsigned outstanding;

  covergroup request_cg;
    option.per_instance = 1;

    command: coverpoint sampled_cmd;
    profile: coverpoint sampled_profile iff (sampled_cmd == CODEC_CMD_CONFIG) {
      bins baseline = {CODEC_PROFILE_BASELINE};
      bins main = {CODEC_PROFILE_MAIN};
      bins high = {CODEC_PROFILE_HIGH};
      illegal_bins reserved = {CODEC_PROFILE_RESERVED};
    }
    resolution: coverpoint sampled_resolution iff (sampled_cmd == CODEC_CMD_CONFIG);
    frame_type: coverpoint sampled_frame_type iff (sampled_cmd == CODEC_CMD_FRAME) {
      bins i = {CODEC_FRAME_I};
      bins p = {CODEC_FRAME_P};
      bins b = {CODEC_FRAME_B};
      illegal_bins reserved = {CODEC_FRAME_RESERVED};
    }
    bit_depth: coverpoint sampled_bit_depth iff (sampled_cmd == CODEC_CMD_CONFIG) {
      bins supported[] = {8, 10, 12};
      illegal_bins unsupported = default;
    }
    quality: coverpoint sampled_qp iff (sampled_cmd == CODEC_CMD_CONFIG) {
      bins lossless = {0};
      bins high_quality = {[1:17]};
      bins balanced = {[18:35]};
      bins low_quality = {[36:51]};
      illegal_bins invalid = {[52:63]};
    }
    input_size: coverpoint sampled_payload_bytes iff (sampled_cmd == CODEC_CMD_DATA) {
      bins empty = {0};
      bins legal[] = {[1:4]};
      bins oversized = {[5:7]};
    }
    legal_config: coverpoint sampled_legal_config iff (sampled_cmd == CODEC_CMD_CONFIG);
    control: coverpoint sampled_control iff (sampled_cmd == CODEC_CMD_CONTROL);
    configured_before: coverpoint sampled_configured;
    injected_error: coverpoint sampled_injected_error;

    profile_x_resolution: cross profile, resolution;
    frame_x_depth: cross frame_type, bit_depth;
  endgroup

  covergroup response_cg;
    option.per_instance = 1;
    status: coverpoint sampled_status;
    latency: coverpoint sampled_latency {
      bins zero_to_two = {[0:2]};
      bins short = {[3:7]};
      bins medium = {[8:20]};
      bins long = {[21:100]};
      bins timeout_risk = {[101:$]};
    }
    configured_after: coverpoint sampled_configured;
    status_x_latency: cross status, latency;
  endgroup

  covergroup reset_cg;
    option.per_instance = 1;
    pending_at_reset: coverpoint sampled_reset_with_pending;
  endgroup

  `uvm_component_utils(codec_coverage)

  function new(string name = "codec_coverage", uvm_component parent = null);
    super.new(name, parent);
    request_cg = new();
    response_cg = new();
    reset_cg = new();
  endfunction

  function void write(codec_seq_item item);
    sampled_cmd = item.cmd;
    sampled_configured = item.configured_state;
    case (item.observation)
      CODEC_OBS_REQUEST: begin
        sampled_profile = item.profile;
        sampled_resolution = codec_resolution_class(item.width, item.height);
        sampled_frame_type = item.frame_type;
        sampled_control = item.control;
        sampled_bit_depth = item.bit_depth;
        sampled_qp = item.qp;
        sampled_payload_bytes = item.payload_bytes;
        sampled_injected_error = item.inject_error;
        sampled_legal_config = codec_config_is_legal(
          item.profile, item.width, item.height, item.bit_depth, item.qp);
        outstanding++;
        request_cg.sample();
      end

      CODEC_OBS_RESPONSE: begin
        sampled_status = item.status;
        sampled_latency = item.observed_latency;
        if (outstanding > 0)
          outstanding--;
        response_cg.sample();
      end

      CODEC_OBS_RESET: begin
        sampled_reset_with_pending = outstanding > 0;
        outstanding = 0;
        reset_cg.sample();
      end
    endcase
  endfunction

  function void report_phase(uvm_phase phase);
    super.report_phase(phase);
    `uvm_info("COV/SUMMARY", $sformatf(
      "request=%0.2f%% response=%0.2f%% reset=%0.2f%%",
      request_cg.get_inst_coverage(), response_cg.get_inst_coverage(),
      reset_cg.get_inst_coverage()), UVM_LOW)
  endfunction

endclass
