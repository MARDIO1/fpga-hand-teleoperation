# Board integration

This area owns the only combined ACZ7015 design. It will connect the vision, strain and fusion packaged IP, perform timestamp alignment and expose PS configuration/status plus UDP debugging.

Module test bitstreams are never nested or linked here. The final Vivado build consumes module IP and emits its own `.bit`, `.hwh` and `.xsa` under `export/bitstream/`.
