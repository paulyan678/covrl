class codec_env_cfg extends uvm_object;
  virtual codec_if vif;
  uvm_active_passive_enum is_active = UVM_ACTIVE;

  int unsigned seed = 1;
  int unsigned transaction_count = 100;
  int unsigned driver_timeout_cycles = 100;
  int unsigned scoreboard_timeout_cycles = 500;
  int unsigned max_outstanding = 1;
  int unsigned default_latency_cycles = 2;
  int unsigned default_response_stall_cycles = 0;
  uvm_verbosity verbosity = UVM_MEDIUM;

  bit enable_baseline_profile = 1;
  bit enable_main_profile = 1;
  bit enable_high_profile = 1;
  bit enable_b_frames = 1;
  bit enable_error_injection = 0;
  bit enable_backpressure = 1;
  bit enable_coverage = 1;
  bit enable_waveforms = 0;
  string waveform_file = "outputs/waves/codec.vcd";

  `uvm_object_utils_begin(codec_env_cfg)
    `uvm_field_enum(uvm_active_passive_enum, is_active, UVM_DEFAULT)
    `uvm_field_int(seed, UVM_DEFAULT)
    `uvm_field_int(transaction_count, UVM_DEFAULT)
    `uvm_field_int(driver_timeout_cycles, UVM_DEFAULT)
    `uvm_field_int(scoreboard_timeout_cycles, UVM_DEFAULT)
    `uvm_field_int(max_outstanding, UVM_DEFAULT)
    `uvm_field_int(default_latency_cycles, UVM_DEFAULT)
    `uvm_field_int(default_response_stall_cycles, UVM_DEFAULT)
    `uvm_field_enum(uvm_verbosity, verbosity, UVM_DEFAULT)
    `uvm_field_int(enable_baseline_profile, UVM_DEFAULT)
    `uvm_field_int(enable_main_profile, UVM_DEFAULT)
    `uvm_field_int(enable_high_profile, UVM_DEFAULT)
    `uvm_field_int(enable_b_frames, UVM_DEFAULT)
    `uvm_field_int(enable_error_injection, UVM_DEFAULT)
    `uvm_field_int(enable_backpressure, UVM_DEFAULT)
    `uvm_field_int(enable_coverage, UVM_DEFAULT)
    `uvm_field_int(enable_waveforms, UVM_DEFAULT)
    `uvm_field_string(waveform_file, UVM_DEFAULT)
  `uvm_object_utils_end

  function new(string name = "codec_env_cfg");
    super.new(name);
  endfunction

  function void validate();
    if (vif == null)
      `uvm_fatal("CFG/VIF", "codec_env_cfg.vif must be configured")
    if (transaction_count == 0)
      `uvm_fatal("CFG/COUNT", "transaction_count must be greater than zero")
    if (driver_timeout_cycles == 0 || scoreboard_timeout_cycles == 0)
      `uvm_fatal("CFG/TIMEOUT", "timeouts must be greater than zero")
    if (default_latency_cycles > 15)
      `uvm_fatal("CFG/LATENCY", "toy adapter latency must be between 0 and 15")
    if (!(enable_baseline_profile || enable_main_profile || enable_high_profile))
      `uvm_fatal("CFG/PROFILE", "at least one codec profile must be enabled")
  endfunction

endclass
