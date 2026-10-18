#!/usr/bin/env python3
"""Make rksu's boot-time sepolicy rules actually take effect (UPDATE 15b).

Symptom on device: init runs the injected `exec u:r:su:s0 /data/adb/ksud
post-fs-data` but execv() fails with EACCES, so no KernelSU module stage ever
runs at boot, and root (u:r:su:s0) is denied on adb_data_file / syslog.
apply_kernelsu_rules() is called at /system/bin/init second_stage, but unlike
the runtime SET_SEPOLICY path (handle_sepolicy) it never flushes the AVC, so
decisions cached before the rules were added keep being enforced. After a
manual `ksud post-fs-data` (which goes through SET_SEPOLICY -> reset_avc_cache)
root's syslog access started working, which points at the missing flush.

This patch:
  1. forward-declares reset_avc_cache() and calls it at the end of
     apply_kernelsu_rules() (the fix);
  2. logs the return values of the core rules (permissive su, allow su *,
     allow init su) so the next boot's dmesg shows whether they were inserted.

Run from the kernel tree root (drivers/kernelsu -> KernelSU/kernel).
"""
import sys

PATH = "drivers/kernelsu/selinux/rules.c"
TAG = "/* rksu_boot_sepolicy_fix */"


def sub_once(src, old, new, what):
    n = src.count(old)
    if n != 1:
        sys.exit(f"rksu_boot_sepolicy_fix: expected 1 match for {what}, found {n}")
    return src.replace(old, new, 1)


src = open(PATH, encoding="utf-8").read()
if TAG in src:
    print("rksu_boot_sepolicy_fix: already applied")
    sys.exit(0)

src = sub_once(
    src,
    "static DEFINE_MUTEX(ksu_rules);\n",
    f"{TAG}\nstatic void reset_avc_cache(void);\n\nstatic DEFINE_MUTEX(ksu_rules);\n",
    "DEFINE_MUTEX(ksu_rules)",
)

# PROBE + FIX: on this Samsung 4.9 the rules reported success but su stayed
# enforcing. Log whether the policydb rksu edits is the SAME object the kernel's
# enforcement reads (the global `policydb`), the policy version, and enforcing.
# `extern struct policydb policydb;` comes from ss/services.h (already included).
src = sub_once(
    src,
    "\tdb = get_policydb();\n\n\tksu_permissive(db, KERNEL_SU_DOMAIN);\n",
    "\tdb = get_policydb();\n"
    "\t{\n"
    "\t\textern int selinux_enforcing;\n"
    "\t\tpr_info(\"KSU-PROBE: get_policydb=%p &policydb=%p same=%d policyvers=%u enforcing=%d\\n\",\n"
    "\t\t\tdb, &policydb, (db == &policydb), db->policyvers, selinux_enforcing);\n"
    "\t}\n\n\tksu_permissive(db, KERNEL_SU_DOMAIN);\n",
    "KSU-PROBE get_policydb",
)

src = sub_once(
    src,
    "\tksu_permissive(db, KERNEL_SU_DOMAIN);\n",
    "\tpr_info(\"apply_kernelsu_rules: permissive %s = %d\\n\", KERNEL_SU_DOMAIN,\n"
    "\t\tksu_permissive(db, KERNEL_SU_DOMAIN));\n",
    "ksu_permissive(su)",
)

src = sub_once(
    src,
    "\tksu_allow(db, KERNEL_SU_DOMAIN, ALL, ALL, ALL);\n",
    "\tpr_info(\"apply_kernelsu_rules: allow %s * * * = %d\\n\", KERNEL_SU_DOMAIN,\n"
    "\t\tksu_allow(db, KERNEL_SU_DOMAIN, ALL, ALL, ALL));\n",
    "ksu_allow(su, ALL, ALL, ALL)",
)

src = sub_once(
    src,
    "\tksu_allow(db, \"init\", KERNEL_SU_DOMAIN, ALL, ALL);\n",
    "\tpr_info(\"apply_kernelsu_rules: allow init %s * * = %d\\n\", KERNEL_SU_DOMAIN,\n"
    "\t\tksu_allow(db, \"init\", KERNEL_SU_DOMAIN, ALL, ALL));\n",
    "ksu_allow(init, su, ALL, ALL)",
)

src = sub_once(
    src,
    "\tsusfs_set_zygote_sid();\n\n\tmutex_unlock(&ksu_rules);\n}\n",
    "\tsusfs_set_zygote_sid();\n\n"
    "\t/* boot path never flushed the AVC; runtime SET_SEPOLICY does */\n"
    "\treset_avc_cache();\n"
    "\tpr_info(\"apply_kernelsu_rules: done, avc reset (policyvers %u)\\n\",\n"
    "\t\tdb->policyvers);\n\n"
    "\tmutex_unlock(&ksu_rules);\n}\n",
    "end of apply_kernelsu_rules",
)

open(PATH, "w", encoding="utf-8").write(src)
print("rksu_boot_sepolicy_fix: applied")
