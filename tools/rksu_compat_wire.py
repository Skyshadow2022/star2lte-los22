#!/usr/bin/env python3
"""Wire the susfs v1.5.5 fs-layer to the rsuntk susfs-rksu-master ABI.

1. Renames the v1.5.5 user-facing entry points that collide with the v2-style
   names rksu calls (they keep their v1.5.5 signatures and become the engine,
   called by tools/rksu_susfs_compat.c via the *_impl names):
       susfs_add_sus_path            -> susfs_add_sus_path_impl
       susfs_add_sus_mount           -> susfs_add_sus_mount_impl
       susfs_add_sus_kstat           -> susfs_add_sus_kstat_impl
       susfs_update_sus_kstat        -> susfs_update_sus_kstat_impl
       susfs_add_try_umount          -> susfs_add_try_umount_impl
       susfs_set_uname               -> susfs_set_uname_impl
       susfs_set_cmdline_or_bootconfig -> susfs_set_cmdline_or_bootconfig_impl
       susfs_add_open_redirect       -> susfs_add_open_redirect_impl
   (word-boundary rename in fs/susfs.c and include/linux/susfs.h only;
   susfs_try_umount / susfs_spoof_* / susfs_sus_ino_* / susfs_auto_add_* /
   susfs_init / susfs_set_log keep their names - signatures already match.)

2. Appends to include/linux/susfs_def.h the CMD ids and constants the modern
   line expects that v1.5.5 predates.

3. Appends to include/linux/susfs.h the declarations of the v2-style handlers
   implemented by drivers/kernelsu/rksu_susfs_compat.c.

4. Adds rksu_susfs_compat.o to drivers/kernelsu/Makefile (the .c file itself
   is copied there by the workflow).

Run from the kernel root after the susfs patch + v155 fix + KSU wiring:
  python3 tools/rksu_compat_wire.py
Idempotent: re-running is a no-op.
"""
import re
import sys

RENAMES = [
    "susfs_add_sus_path",
    "susfs_add_sus_mount",
    "susfs_add_sus_kstat",
    "susfs_update_sus_kstat",
    "susfs_add_try_umount",
    "susfs_set_uname",
    "susfs_set_cmdline_or_bootconfig",
    "susfs_add_open_redirect",
]

DEF_H_APPEND = """
/* ---- appended by tools/rksu_compat_wire.py (rksu susfs-rksu-master ABI) ---- */
#define CMD_SUSFS_ADD_SUS_PATH_LOOP 0x55553
#define CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING 0x60010
#define CMD_SUSFS_ADD_SUS_MAP 0x60020
#define TASK_STRUCT_PROC_UMOUNTED BIT(25)
#define SUSFS_MIN_USER_APP_UID 10000 /* v2-era user-app check: uid >= 10000 */
#define SUSFS_ENABLED_FEATURES_SIZE 8192
/* sucompat.c only includes susfs_def.h (not susfs.h), so the proc-umounted
 * API it calls must be declared here as well. */
bool susfs_is_current_proc_umounted(void);
void susfs_set_current_proc_umounted(void);
/* ---- end rksu ABI append ---- */
"""

SUSFS_H_APPEND = """
/* ---- appended by tools/rksu_compat_wire.py (rksu susfs-rksu-master ABI) ---- */
/* v2-style handlers, implemented in drivers/kernelsu/rksu_susfs_compat.c */
void susfs_add_sus_path(void __user **user_info);
void susfs_add_sus_path_loop(void __user **user_info);
void susfs_set_i_state_on_external_dir(void __user **user_info);
void susfs_set_hide_sus_mnts_for_all_procs(void __user **user_info);
void susfs_add_sus_kstat(void __user **user_info);
void susfs_update_sus_kstat(void __user **user_info);
void susfs_add_try_umount(void __user **user_info);
void susfs_try_umount_all(uid_t uid);
void susfs_set_uname(void __user **user_info);
void susfs_set_cmdline_or_bootconfig(void __user **user_info);
void susfs_enable_log(void __user **user_info);
void susfs_add_open_redirect(void __user **user_info);
void susfs_set_avc_log_spoofing(void __user **user_info);
void susfs_get_enabled_features(void __user **user_info);
void susfs_show_variant(void __user **user_info);
void susfs_show_version(void __user **user_info);
bool susfs_is_current_proc_umounted(void);
void susfs_set_current_proc_umounted(void);
void susfs_run_sus_path_loop(uid_t uid);
void susfs_reorder_mnt_id(void);
void susfs_set_sid(const char *secctx_name, u32 *out_sid);
/* ---- end rksu ABI append ---- */
"""

KSU_MAKEFILE_ANCHOR = "ksu_obj-y += file_wrapper.o\n"
KSU_MAKEFILE_LINE = "ksu_obj-y += rksu_susfs_compat.o\n"

# rksu's Kconfig lacks the AUTO_ADD trio (it comes from the deprecated/susfs-legacy
# line); the v1.5.5 fs-layer hooks gate on them, so re-create them in the
# "KernelSU - SUSFS" menu (before that menu's endmenu).
KCONFIG_ANCHOR_RE = re.compile(r"(config KSU_SUSFS_SUS_MAP\r?\n(?:.+\r?\n)*?\r?\n)(endmenu\r?\n)", re.M)
KCONFIG_BLOCK = (
    "config KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT\n"
    "    bool \"Auto add sus mount for KernelSU default mounts\"\n"
    "    depends on KSU_SUSFS_SUS_MOUNT\n"
    "    default y\n"
    "    help\n"
    "        - Automatically add the KernelSU default mounts to sus_mount.\n"
    "        - Menu entry (re)added by tools/rksu_compat_wire.py for the\n"
    "          v1.5.5 fs-layer, which gates its hooks on these symbols.\n"
    "\n"
    "config KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT\n"
    "    bool \"Auto add sus mount for KernelSU bind mounts\"\n"
    "    depends on KSU_SUSFS_SUS_MOUNT\n"
    "    default y\n"
    "\n"
    "config KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT\n"
    "    bool \"Auto add try_umount for KernelSU bind mounts\"\n"
    "    depends on KSU_SUSFS_SUS_MOUNT && KSU_SUSFS_TRY_UMOUNT\n"
    "    default y\n"
    "\n"
)

MARK_DEF = "appended by tools/rksu_compat_wire.py"
MARK_MAKEFILE = "rksu_susfs_compat.o"


def do_renames():
    # Idempotency marker: the engine's own definitions live in fs/susfs.c.
    probe = open("fs/susfs.c", newline="").read()
    if "_impl" in probe:
        print("rename: fs/susfs.c already converted")
        return
    for path in ("fs/susfs.c", "include/linux/susfs.h"):
        s = open(path, newline="").read()
        n = 0
        for name in RENAMES:
            s, k = re.subn(r"\b%s\b" % re.escape(name), name + "_impl", s)
            n += k
        if n:
            open(path, "w", newline="").write(s)
        print("renamed %d occurrences in %s" % (n, path))


def append_once(path, text):
    s = open(path, newline="").read()
    if MARK_DEF in s:
        print("append: %s already has the rksu ABI block" % path)
        return
    open(path, "w", newline="").write(s + text)
    print("append: %s <- rksu ABI block" % path)


def patch_ksu_makefile():
    path = "drivers/kernelsu/Makefile"
    s = open(path, newline="").read()
    if MARK_MAKEFILE in s:
        print("kernelsu Makefile: already wired")
        return
    # rksu ships this file with CRLF or LF depending on checkout; accept both.
    anchor_re = re.compile(r"ksu_obj-y \+= file_wrapper\.o\r?\n")
    matches = anchor_re.findall(s)
    if len(matches) != 1:
        sys.exit("kernelsu Makefile: anchor not found exactly once (%d)" % len(matches))
    line = KSU_MAKEFILE_LINE if "\r\n" not in s[:200] else KSU_MAKEFILE_LINE.replace("\n", "\r\n")
    s = anchor_re.sub(lambda m: m.group(0) + line, s, count=1)
    open(path, "w", newline="").write(s)
    print("kernelsu Makefile: added rksu_susfs_compat.o")


def patch_ksu_kconfig():
    path = "drivers/kernelsu/Kconfig"
    s = open(path, newline="").read()
    if "KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT" in s:
        print("kernelsu Kconfig: AUTO_ADD trio already present")
        return
    matches = KCONFIG_ANCHOR_RE.findall(s)
    if len(matches) != 1:
        sys.exit("kernelsu Kconfig: SUS_MAP..endmenu anchor not found exactly once (%d)"
                 % len(matches))
    block = KCONFIG_BLOCK
    if "\r\n" in s:
        block = block.replace("\n", "\r\n")
    s = KCONFIG_ANCHOR_RE.sub(lambda m: m.group(1) + block + m.group(2), s, count=1)
    open(path, "w", newline="").write(s)
    print("kernelsu Kconfig: added AUTO_ADD trio")


def main():
    do_renames()
    append_once("include/linux/susfs_def.h", DEF_H_APPEND)
    append_once("include/linux/susfs.h", SUSFS_H_APPEND)
    patch_ksu_kconfig()
    patch_ksu_makefile()
    print("rksu_compat_wire: done")


if __name__ == "__main__":
    main()
