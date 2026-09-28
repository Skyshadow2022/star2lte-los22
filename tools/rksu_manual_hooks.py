#!/usr/bin/env python3
"""Add the manual-hook call sites the modern rksu (susfs-rksu-master) expects.

Unlike the legacy line (which self-registered kprobes), the modern branch only
defines ksu_handle_* handlers and expects the KERNEL TREE to call them
(manual-hook mode; same contract as KernelSU-Next's CONFIG_KSU_MANUAL_HOOK).
Without these call sites:
  - the manager cannot install its [ksu_driver] ioctl fd (sys_reboot hook) ->
    manager shows "Unsupported"
  - init never sees the injected ksud.rc (vfs_read hook on atrace.rc) -> the
    root ksud daemon never starts
  - exec of /system/bin/su is not redirected to /data/adb/ksud (execve hook)
    -> no kernel su
  - su path stat/access are not redirected (stat/faccessat hooks)

All inserted calls are gated on CONFIG_KSU and use block-scope extern
declarations, so this file is the only place that knows the signatures.

Run from the kernel root AFTER the KSU wiring steps:
  python3 tools/rksu_manual_hooks.py
Idempotent: re-running is a no-op.
"""
import sys

MARK = "rksu manual hook"


def patch(path, anchor, block, done_marker):
    s = open(path, newline="").read()
    if done_marker in s:
        print("%s: already patched" % path)
        return
    if s.count(anchor) != 1:
        sys.exit("%s: anchor not found exactly once (%d):\n%r"
                 % (path, s.count(anchor), anchor[:120]))
    s = s.replace(anchor, block)
    open(path, "w", newline="").write(s)
    print("%s: hook added" % path)


def main():
    # 1) kernel/reboot.c - fd install + susfs command dispatch
    patch(
        "kernel/reboot.c",
        "\tchar buffer[256];\n\tint ret = 0;\n\n\t/* We only trust the superuser with rebooting the system. */\n",
        "\tchar buffer[256];\n\tint ret = 0;\n\n"
        "#ifdef CONFIG_KSU /* " + MARK + " */\n"
        "\textern int ksu_handle_sys_reboot(int magic1, int magic2, unsigned int cmd, void __user **arg);\n"
        "\tksu_handle_sys_reboot(magic1, magic2, cmd, &arg);\n"
        "#endif\n\n"
        "\t/* We only trust the superuser with rebooting the system. */\n",
        MARK + " */",
    )

    # 2) fs/read_write.c - ksud.rc injection into init's atrace.rc read
    patch(
        "fs/read_write.c",
        "ssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos)\n{\n\tssize_t ret;\n\n\tif (!(file->f_mode & FMODE_READ))\n",
        "ssize_t vfs_read(struct file *file, char __user *buf, size_t count, loff_t *pos)\n{\n\tssize_t ret;\n\n"
        "#ifdef CONFIG_KSU /* " + MARK + " */\n"
        "\textern int ksu_handle_vfs_read(struct file **file_ptr, char __user **buf_ptr, size_t *count_ptr, loff_t **pos);\n"
        "\tksu_handle_vfs_read(&file, &buf, &count, &pos);\n"
        "#endif\n\n"
        "\tif (!(file->f_mode & FMODE_READ))\n",
        MARK + " */",
    )

    # 3) fs/exec.c - su exec redirect + ksud exec tracking
    patch(
        "fs/exec.c",
        "\tstruct files_struct *displaced;\n\tint retval;\n\n\tif (IS_ERR(filename))\n\t\treturn PTR_ERR(filename);\n",
        "\tstruct files_struct *displaced;\n\tint retval;\n\n"
        "#ifdef CONFIG_KSU /* " + MARK + " */\n"
        "\textern int ksu_handle_execveat(int *fd, struct filename **filename_ptr, void *argv, void *envp, int *flags);\n"
        "\tksu_handle_execveat((int *)&fd, &filename, &argv, &envp, &flags);\n"
        "#endif\n\n"
        "\tif (IS_ERR(filename))\n\t\treturn PTR_ERR(filename);\n",
        MARK + " */",
    )

    # 4) fs/open.c - faccessat su hiding
    patch(
        "fs/open.c",
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n\n\tif (mode & ~S_IRWXO)\t/* where's F_OK, X_OK, W_OK, R_OK? */\n\t\treturn -EINVAL;\n",
        "\tunsigned int lookup_flags = LOOKUP_FOLLOW;\n\n"
        "#ifdef CONFIG_KSU /* " + MARK + " */\n"
        "\textern int ksu_handle_faccessat(int *dfd, const char __user **filename_user, int *mode, int *__unused_flags);\n"
        "\tksu_handle_faccessat((int *)&dfd, &filename, &mode, NULL);\n"
        "#endif\n\n"
        "\tif (mode & ~S_IRWXO)\t/* where's F_OK, X_OK, W_OK, R_OK? */\n\t\treturn -EINVAL;\n",
        MARK + " */",
    )

    # 5) fs/stat.c - newfstatat/vfs_statx su hiding
    patch(
        "fs/stat.c",
        "\tstruct path path;\n\tint error = -EINVAL;\n\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;\n",
        "\tstruct path path;\n\tint error = -EINVAL;\n\tunsigned int lookup_flags = LOOKUP_FOLLOW | LOOKUP_AUTOMOUNT;\n\n"
        "#ifdef CONFIG_KSU /* " + MARK + " */\n"
        "\textern int ksu_handle_stat(int *dfd, const char __user **filename_user, int *flags);\n"
        "\tksu_handle_stat((int *)&dfd, &filename, &flags);\n"
        "#endif\n",
        MARK + " */",
    )

    print("rksu_manual_hooks: done")


if __name__ == "__main__":
    main()
