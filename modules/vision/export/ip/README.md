# Vision IP export status

No versioned, separately packaged vision interface IP is released yet. This
migration provides RTL and standalone Vivado build scripts. Board display IP used
by those test projects lives under `vivado/ip_repo/` with original source notices.

Do not treat the standalone HDMI bitstream as the vision MarkerFrame IP. Integration
must eventually consume packaged IP with the agreed marker interface, not this
module's `.bit` file. Redistribution status is recorded in `docs/third_party.md`.
