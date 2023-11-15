module toy_codec_adapter(codec_if.dut bus);

  toy_codec dut (
    .clk                 (bus.clk),
    .reset_n             (bus.reset_n),
    .req_valid           (bus.req_valid),
    .req_ready           (bus.req_ready),
    .req_cmd             (bus.req_cmd),
    .req_profile         (bus.req_profile),
    .req_width           (bus.req_width),
    .req_height          (bus.req_height),
    .req_frame_type      (bus.req_frame_type),
    .req_bit_depth       (bus.req_bit_depth),
    .req_qp              (bus.req_qp),
    .req_payload         (bus.req_payload),
    .req_payload_bytes   (bus.req_payload_bytes),
    .req_control         (bus.req_control),
    .req_inject_error    (bus.req_inject_error),
    .latency_cycles      (bus.latency_cycles),
    .rsp_valid           (bus.rsp_valid),
    .rsp_ready           (bus.rsp_ready),
    .rsp_cmd             (bus.rsp_cmd),
    .rsp_status          (bus.rsp_status),
    .rsp_data            (bus.rsp_data),
    .rsp_sequence_id     (bus.rsp_sequence_id),
    .configured          (bus.configured)
  );

endmodule
