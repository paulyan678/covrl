typedef enum int unsigned {
  CODEC_OBS_REQUEST,
  CODEC_OBS_RESPONSE,
  CODEC_OBS_RESET
} codec_observation_e;

class codec_seq_item extends uvm_sequence_item;
  rand codec_cmd_e        cmd;
  rand codec_profile_e    profile;
  rand logic [12:0]       width;
  rand logic [12:0]       height;
  rand codec_frame_type_e frame_type;
  rand logic [3:0]        bit_depth;
  rand logic [5:0]        qp;
  rand logic [31:0]       payload;
  rand logic [2:0]        payload_bytes;
  rand codec_control_e    control;
  rand bit                inject_error;
  rand int unsigned       latency_cycles;
  rand int unsigned       response_stall_cycles;
  rand int unsigned       inter_transaction_gap;
  rand bit                reset_after_request;
  rand int unsigned       reset_cycles;
  rand bit                allow_illegal;

  codec_observation_e observation;
  codec_status_e      status;
  logic [31:0]        response_data;
  logic [15:0]        sequence_id;
  int unsigned        observed_latency;
  bit                 configured_state;

  constraint c_default_legal {
    soft allow_illegal == 0;
    if (!allow_illegal && cmd == CODEC_CMD_CONFIG) {
      profile != CODEC_PROFILE_RESERVED;
      width inside {[16:4096]};
      height inside {[16:4096]};
      bit_depth inside {8, 10, 12};
      qp inside {[0:51]};
    }
    if (!allow_illegal && cmd == CODEC_CMD_FRAME)
      frame_type != CODEC_FRAME_RESERVED;
    if (!allow_illegal && cmd == CODEC_CMD_DATA)
      payload_bytes inside {[1:4]};
  }

  constraint c_traffic_mix {
    soft cmd dist {
      CODEC_CMD_CONFIG := 10,
      CODEC_CMD_FRAME := 25,
      CODEC_CMD_DATA := 55,
      CODEC_CMD_CONTROL := 10
    };
    soft profile dist {
      CODEC_PROFILE_BASELINE := 3,
      CODEC_PROFILE_MAIN := 4,
      CODEC_PROFILE_HIGH := 3
    };
    soft frame_type dist {
      CODEC_FRAME_I := 2,
      CODEC_FRAME_P := 5,
      CODEC_FRAME_B := 3
    };
    soft latency_cycles inside {[0:7]};
    soft response_stall_cycles inside {[0:12]};
    soft inter_transaction_gap inside {[0:5]};
    soft reset_after_request == 0;
    soft reset_cycles inside {[2:8]};
    soft inject_error == 0;
  }

  `uvm_object_utils_begin(codec_seq_item)
    `uvm_field_enum(codec_cmd_e, cmd, UVM_DEFAULT)
    `uvm_field_enum(codec_profile_e, profile, UVM_DEFAULT)
    `uvm_field_int(width, UVM_DEFAULT)
    `uvm_field_int(height, UVM_DEFAULT)
    `uvm_field_enum(codec_frame_type_e, frame_type, UVM_DEFAULT)
    `uvm_field_int(bit_depth, UVM_DEFAULT)
    `uvm_field_int(qp, UVM_DEFAULT)
    `uvm_field_int(payload, UVM_HEX)
    `uvm_field_int(payload_bytes, UVM_DEFAULT)
    `uvm_field_enum(codec_control_e, control, UVM_DEFAULT)
    `uvm_field_int(inject_error, UVM_DEFAULT)
    `uvm_field_int(latency_cycles, UVM_DEFAULT)
    `uvm_field_int(response_stall_cycles, UVM_DEFAULT)
    `uvm_field_int(inter_transaction_gap, UVM_DEFAULT)
    `uvm_field_int(reset_after_request, UVM_DEFAULT)
    `uvm_field_int(reset_cycles, UVM_DEFAULT)
    `uvm_field_int(allow_illegal, UVM_DEFAULT)
    `uvm_field_enum(codec_observation_e, observation, UVM_DEFAULT)
    `uvm_field_enum(codec_status_e, status, UVM_DEFAULT)
    `uvm_field_int(response_data, UVM_HEX)
    `uvm_field_int(sequence_id, UVM_DEFAULT)
    `uvm_field_int(observed_latency, UVM_DEFAULT)
    `uvm_field_int(configured_state, UVM_DEFAULT)
  `uvm_object_utils_end

  function new(string name = "codec_seq_item");
    super.new(name);
    observation = CODEC_OBS_REQUEST;
    status = CODEC_STATUS_OK;
  endfunction

  function string convert2string();
    return $sformatf(
      "obs=%s cmd=%s profile=%s %0dx%0d depth=%0d qp=%0d frame=%s "
      "payload=%08x bytes=%0d status=%s seq=%0d latency=%0d",
      observation.name(), cmd.name(), profile.name(), width, height,
      bit_depth, qp, frame_type.name(), payload, payload_bytes,
      status.name(), sequence_id, observed_latency
    );
  endfunction

endclass
