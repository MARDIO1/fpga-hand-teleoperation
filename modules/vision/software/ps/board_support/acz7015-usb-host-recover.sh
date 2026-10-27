#!/bin/sh
set -eu

driver=/sys/bus/platform/drivers/chipidea-usb2
device=e0002000.usb

for attempt in 1 2 3; do
    if [ -L "$driver/$device" ]; then
        printf '%s' "$device" > "$driver/unbind"
    fi

    /usr/local/sbin/acz7015-usb-ps-init
    printf '%s' "$device" > "$driver/bind"

    # A successful parent bind is not enough: ci_hdrc may still fail its PHY
    # probe. Require the EHCI root hub before accepting the attempt.
    count=0
    while [ "$count" -lt 20 ]; do
        [ -d /sys/bus/usb/devices/usb1 ] && break 2
        count=$((count + 1))
        sleep 0.1
    done
    logger -t acz7015-usb-host "attempt $attempt did not create USB root hub"
    sleep 0.5
done

[ -d /sys/bus/usb/devices/usb1 ] || {
    echo 'ACZ7015 USB host recovery failed: root hub usb1 was not created' >&2
    exit 1
}

# Let any already connected camera finish enumeration.
sleep 1
modprobe uvcvideo 2>/dev/null || true
udevadm settle --timeout=10 2>/dev/null || true
