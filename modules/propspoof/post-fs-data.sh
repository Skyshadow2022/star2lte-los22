#!/system/bin/sh
# prop-spoof: banking apps (Bale, Hamrah-e-Man, Blu, ...) detect
# userdebug/test-keys/orange/unlocked builds. Runs early (post-fs-data).
LOG=/data/local/tmp/propspoof.log
{
echo "=== propspoof post-fs-data $(date)"
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
