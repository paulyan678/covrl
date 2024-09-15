class toy_codec_reference_model extends codec_reference_model;
  bit configured;
  codec_profile_e profile;
  logic [12:0] width;
  logic [12:0] height;
  logic [3:0] bit_depth;
  logic [5:0] qp;
  logic [15:0] next_sequence_id;

  `uvm_component_utils(toy_codec_reference_model)

  function new(string name = "toy_codec_reference_model", uvm_component parent = null);
    super.new(name, parent);
    reset_state();
  endfunction

  function void reset_state();
    configured = 0;
    profile = CODEC_PROFILE_BASELINE;
    width = '0;
    height = '0;
    bit_depth = 4'd8;
    qp = '0;
    next_sequence_id = '0;
  endfunction

  function logic [31:0] transform(logic [31:0] value,
                                   codec_frame_type_e frame_type);
    logic [31:0] key;
    key = {width[7:0], height[7:0], qp, bit_depth, profile,
           frame_type, 2'b0};
    return {value[23:0], value[31:24]} ^ key;
  endfunction

  virtual function void write(codec_seq_item request);
    codec_seq_item expected;
    if (request.observation == CODEC_OBS_RESET) begin
      reset_state();
      return;
    end
    if (request.observation != CODEC_OBS_REQUEST)
      return;

    expected = codec_seq_item::type_id::create("expected_response");
    expected.observation = CODEC_OBS_RESPONSE;
    expected.cmd = request.cmd;
    expected.sequence_id = next_sequence_id++;
    expected.status = CODEC_STATUS_BAD_CONTROL;
    expected.response_data = '0;

    if (request.inject_error) begin
      expected.status = CODEC_STATUS_INJECTED_ERROR;
    end else begin
      case (request.cmd)
        CODEC_CMD_CONFIG: begin
          if (codec_config_is_legal(request.profile, request.width,
                                    request.height, request.bit_depth,
                                    request.qp)) begin
            configured = 1;
            profile = request.profile;
            width = request.width;
            height = request.height;
            bit_depth = request.bit_depth;
            qp = request.qp;
            expected.status = CODEC_STATUS_OK;
          end else begin
            expected.status = CODEC_STATUS_BAD_CONFIG;
          end
        end

        CODEC_CMD_FRAME: begin
          if (!configured)
            expected.status = CODEC_STATUS_NOT_CONFIGURED;
          else if (request.frame_type == CODEC_FRAME_RESERVED)
            expected.status = CODEC_STATUS_BAD_INPUT;
          else begin
            expected.status = CODEC_STATUS_OK;
            expected.response_data = transform(request.payload, request.frame_type);
          end
        end

        CODEC_CMD_DATA: begin
          if (!configured)
            expected.status = CODEC_STATUS_NOT_CONFIGURED;
          else if (!(request.payload_bytes inside {[1:4]}))
            expected.status = CODEC_STATUS_BAD_INPUT;
          else begin
            expected.status = CODEC_STATUS_OK;
            expected.response_data = transform(request.payload, request.frame_type);
          end
        end

        CODEC_CMD_CONTROL: begin
          if (request.control == CODEC_CTRL_PING) begin
            expected.status = CODEC_STATUS_OK;
            expected.response_data = 32'hc0de_c0de;
          end else if (!(request.control inside {
            CODEC_CTRL_START, CODEC_CTRL_FLUSH, CODEC_CTRL_STOP
          })) begin
            expected.status = CODEC_STATUS_BAD_CONTROL;
          end else if (!configured) begin
            expected.status = CODEC_STATUS_NOT_CONFIGURED;
          end else begin
            case (request.control)
              CODEC_CTRL_START: expected.status = CODEC_STATUS_OK;
              CODEC_CTRL_FLUSH: begin
                expected.status = CODEC_STATUS_OK;
                expected.response_data = 32'hf1f1_f1f1;
              end
              CODEC_CTRL_STOP: begin
                expected.status = CODEC_STATUS_OK;
                configured = 0;
              end
              default: expected.status = CODEC_STATUS_BAD_CONTROL;
            endcase
          end
        end

        default: expected.status = CODEC_STATUS_BAD_CONTROL;
      endcase
    end

    expected.configured_state = configured;
    expected_ap.write(expected);
    `uvm_info("REF/PREDICT", expected.convert2string(), UVM_HIGH)
  endfunction

endclass
