class codec_reference_model extends uvm_subscriber #(codec_seq_item);
  uvm_analysis_port #(codec_seq_item) expected_ap;

  `uvm_component_utils(codec_reference_model)

  function new(string name = "codec_reference_model", uvm_component parent = null);
    super.new(name, parent);
    expected_ap = new("expected_ap", this);
  endfunction

  virtual function void write(codec_seq_item item);
    `uvm_fatal("REF/ADAPTER", $sformatf(
      "no DUT-specific reference model is registered for %s",
      item.convert2string()))
  endfunction

endclass
