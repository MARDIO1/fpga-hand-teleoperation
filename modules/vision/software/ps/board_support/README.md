# Existing board-image reset support

Sources retained from the working ACZ7015 Linux setup. They are not installed or
enabled by this migration. The display helper expects the already installed
`acz7015-usb-host.service` to recover the board's shared USB/HDMI reset path after
PL loading. Restarting it can interrupt USB devices.

On the original Linux image, the C utility was built for the board's ARM CPU as
`/usr/local/sbin/acz7015-usb-ps-init`; the shell script was installed as
`/usr/local/sbin/acz7015-usb-host-recover`; and the unit as
`/etc/systemd/system/acz7015-usb-host.service`. A native board build uses:

```sh
cc -O2 -Wall -Wextra usb_ps_runtime_init.c -o acz7015-usb-ps-init
```

Do not automatically install these on a different image. They assume specific
PS MIO/GPIO registers, ChipIdea driver names and Linux sysfs bindings. Confirm the
board schematic and reserved memory/device tree before using the display runner.
