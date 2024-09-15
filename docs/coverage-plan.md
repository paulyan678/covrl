# Functional Coverage Plan

## Intent

The coverage model measures stimulus diversity and protocol outcomes rather
than line coverage in the behavioral DUT. It is codec-independent at the
transaction level: profiles, resolution classes, frame types, depth, quality,
input size, controls, protocol state, errors, stalls, latency, and reset events
are observable without knowing a proprietary bitstream syntax.

| Requirement | Model |
|:---|:---|
| Codec mode/profile | baseline, main, high, and reserved configuration bins |
| Resolution class | SD, HD, FHD, and UHD classification from width and height |
| Frame type | I, P, B, and reserved frame bins |
| Bit depth | 8, 10, 12, and unsupported values |
| Quality/quantization | lossless, high-quality, balanced, low-quality, and invalid QP ranges |
| Input size | zero, each legal byte count, and oversized inputs |
| Configuration legality | explicit legal and illegal outcome bins |
| Backpressure | none, light, moderate, and heavy response stalls |
| Latency | short through timeout-risk ranges |
| Reset | reset with and without an outstanding transaction |
| Errors | every protocol status and injected-error request flag |
| Controls | start, flush, stop, ping, and invalid encodings through status coverage |

## Sampling model

- Request coverage samples only accepted request handshakes.
- A valid configuration updates the collector's active profile, resolution,
  bit depth, and quality state. Frame/data crosses use this active state rather
  than ignored fields on the transport request.
- Response coverage samples only accepted response handshakes. A FIFO retains
  request context so status can be crossed with command and control operation.
- Backpressure counts cycles where response-valid is high and response-ready is
  low. Observed latency runs from request acceptance through response acceptance.
- Reset coverage records whether a prediction was outstanding and clears the
  collector's active configuration and request context.
- Expected negative tests use ordinary bins for invalid values. They are not
  modeled as coverage-tool errors.

## Focused crosses

Configuration crosses cover profile versus resolution, profile versus depth,
resolution versus depth, and profile versus quality. Traffic crosses cover
frame type versus active profile/depth/resolution and input size versus active
depth. Protocol crosses cover command versus configured state, status versus
command/latency, control versus status, and backpressure versus latency.

These focused crosses avoid a single combinatorial Cartesian product whose
size would obscure useful closure work. A real codec adapter may add targeted
crosses for features such as chroma format, tile structure, entropy mode, or
rate-control mode.

## Known unreachable or intentionally out-of-scope combinations

The following holes are expected and must be explained in any closure report:

- `BAD_CONFIG` is produced only by configuration commands.
- `BAD_INPUT` is produced only by frame/data commands in the toy protocol.
- `BAD_CONTROL` is produced only by control or unknown command encodings.
- `INJECTED_ERROR` requires the explicit injection flag and cannot coincide
  with a normal successful status for the same transaction.
- `NOT_CONFIGURED` cannot be returned for ping, because ping is intentionally
  legal before configuration.
- Successful stop clears configured state in the same accepted transaction;
  therefore success crossed with configured-after is false for stop.
- The supplied sequences bound DUT latency to 15 cycles and response stalls to
  12 cycles. Timeout-risk latency bins require a deliberately extended stress
  sequence or a different DUT adapter.
- `CODEC_STATUS_TIMEOUT` is reserved for a future timeout-reporting DUT adapter.
  The toy DUT is interrupted by the driver/SVA timeout path instead of emitting
  a normal response with this status, so its status bin is unreachable here.
- The behavioral DUT does not model compressed bitstream syntax, chroma
  subsampling, tiles/slices, reference-picture lists, entropy coding, or
  standard-specific level constraints. No bins for those concepts are claimed.
- Simulator code-coverage holes are not waived by this functional plan; they
  require a tool-generated report and separate design review.

When integrating real IP, copy this plan, identify configuration restrictions,
and mark each impossible cross with a reviewed rationale in the generated
coverage report rather than deleting the bin silently.
