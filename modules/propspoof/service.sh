#!/system/bin/sh
# prop-spoof backup stage (services) — re-asserts the spoofs after boot
# in case the post-fs-data stage ran before init finished setting props.
LOG=/data/local/tmp/propspoof.log
{
echo "=== propspoof service $(date)"
KSUD=/data/adb/ksud
[ -x "$KSUD" ] || { echo "no ksud"; exit 0; }
"$KSUD" resetprop ro.debuggable 0
"$KSUD" resetprop ro.build.type user
"$KSUD" resetprop ro.build.tags release-keys
"$KSUD" resetprop ro.boot.verifiedbootstate green
"$KSUD" resetprop ro.boot.warranty_bit 0
"$KSUD" resetprop ro.warranty_bit 0
"$KSUD" resetprop ro.secureboot.lockstate locked
echo "=== done"
} >> "$LOG" 2>&1
exit 0
