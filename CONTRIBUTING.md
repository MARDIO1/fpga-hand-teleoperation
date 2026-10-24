# Contributing

Work inside the module you own. Do not commit Vivado run directories, caches, virtual environments, raw datasets or temporary reports.

Before proposing an integration change:

1. Run the module's standalone simulation.
2. Rebuild its packaged IP from source.
3. Update the matching document in `contracts/` if the packet or register interface changed.
4. Record the tool version, target part and artifact checksum with any published test bitstream.

The integration project references module IP; it never combines module `.bit` files.
