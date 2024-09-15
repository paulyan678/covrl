package codec_protocol_pkg;

  typedef enum logic [2:0] {
    CODEC_CMD_CONFIG  = 3'd0,
    CODEC_CMD_FRAME   = 3'd1,
    CODEC_CMD_DATA    = 3'd2,
    CODEC_CMD_CONTROL = 3'd3
  } codec_cmd_e;

  typedef enum logic [1:0] {
    CODEC_PROFILE_BASELINE = 2'd0,
    CODEC_PROFILE_MAIN     = 2'd1,
    CODEC_PROFILE_HIGH     = 2'd2,
    CODEC_PROFILE_RESERVED = 2'd3
  } codec_profile_e;

  typedef enum logic [1:0] {
    CODEC_FRAME_I        = 2'd0,
    CODEC_FRAME_P        = 2'd1,
    CODEC_FRAME_B        = 2'd2,
    CODEC_FRAME_RESERVED = 2'd3
  } codec_frame_type_e;

  typedef enum logic [2:0] {
    CODEC_CTRL_START = 3'd0,
    CODEC_CTRL_FLUSH = 3'd1,
    CODEC_CTRL_STOP  = 3'd2,
    CODEC_CTRL_PING  = 3'd3
  } codec_control_e;

  typedef enum logic [2:0] {
    CODEC_STATUS_OK             = 3'd0,
    CODEC_STATUS_BAD_CONFIG     = 3'd1,
    CODEC_STATUS_NOT_CONFIGURED = 3'd2,
    CODEC_STATUS_BAD_INPUT      = 3'd3,
    CODEC_STATUS_BAD_CONTROL    = 3'd4,
    CODEC_STATUS_INJECTED_ERROR = 3'd5,
    CODEC_STATUS_TIMEOUT        = 3'd6
  } codec_status_e;

  typedef enum logic [1:0] {
    CODEC_RES_SD  = 2'd0,
    CODEC_RES_HD  = 2'd1,
    CODEC_RES_FHD = 2'd2,
    CODEC_RES_UHD = 2'd3
  } codec_resolution_e;

  typedef struct packed {
    codec_cmd_e        cmd;
    codec_profile_e    profile;
    logic [12:0]       width;
    logic [12:0]       height;
    codec_frame_type_e frame_type;
    logic [3:0]        bit_depth;
    logic [5:0]        qp;
    logic [31:0]       payload;
    logic [2:0]        payload_bytes;
    codec_control_e    control;
    logic              inject_error;
  } codec_request_t;

  typedef struct packed {
    codec_cmd_e   cmd;
    codec_status_e status;
    logic [31:0]  data;
    logic [15:0]  sequence_id;
  } codec_response_t;

  function automatic logic codec_config_is_legal(
    codec_profile_e profile,
    logic [12:0] width,
    logic [12:0] height,
    logic [3:0] bit_depth,
    logic [5:0] qp
  );
    return profile != CODEC_PROFILE_RESERVED &&
           width >= 13'd16 && width <= 13'd4096 &&
           height >= 13'd16 && height <= 13'd4096 &&
           (bit_depth == 4'd8 || bit_depth == 4'd10 ||
            bit_depth == 4'd12) &&
           qp <= 6'd51;
  endfunction

  function automatic codec_resolution_e codec_resolution_class(
    logic [12:0] width,
    logic [12:0] height
  );
    if (width <= 13'd720 && height <= 13'd576)
      return CODEC_RES_SD;
    if (width <= 13'd1280 && height <= 13'd720)
      return CODEC_RES_HD;
    if (width <= 13'd1920 && height <= 13'd1080)
      return CODEC_RES_FHD;
    return CODEC_RES_UHD;
  endfunction

endpackage
