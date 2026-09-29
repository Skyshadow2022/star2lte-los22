#!/usr/bin/env python3
"""Backport the v3.2.2 manager's new ioctl ABI into the susfs-rksu-master kernel.

The v3.2.2-10-legacy manager (versionCode 32490, min kernel 32377) speaks a
slightly newer ioctl ABI than the susfs-rksu-master branch (KSU_VERSION 32359):
  - NEW_GET_ALLOW_LIST / NEW_GET_DENY_LIST (nr 6/7, variable-length
    ksu_new_get_allow_list_cmd {u16 count, u16 total_count, u32 uids[]})
  - SET_INIT_PGRP (_IO('K', 19))
  - GET_SULOG_FD  (_IOW('K', 20, struct ksu_get_sulog_fd_cmd))

Without them the manager's Superuser / Modules screens stay empty. This adds
the four commands to the kernel dispatcher:
  - the new allow/deny handlers wrap a new bounded allowlist iterator
    (the branch's ksu_get_allow_list() has no capacity argument and would
    overflow the flexible-array buffer),
  - SET_INIT_PGRP is ported verbatim from the xxksu line (4.9 path),
  - GET_SULOG_FD returns -EOPNOTSUPP (the branch has no sulog fd infra; the
    manager shows sulog as unsupported - cosmetic only),
and bumps KSU_VERSION to 32490 so the manager's min-version gate passes.

Run from the kernel root after the other wiring steps:
  python3 tools/rksu_abi_backport.py
Idempotent: re-running is a no-op.
"""
import re
import sys

MARK = "rksu abi backport"

ALLOWLIST_C_APPEND = """

/* ---- appended by tools/rksu_abi_backport.py ---- */
/* Size-aware variant of ksu_get_allow_list() for the v3.2.2 manager ABI:
 * fills at most `capacity` entries and reports the real total. */
bool ksu_get_allow_list_bounded(int *array, int capacity, int *count_out,
				int *total_out, bool allow)
{
	struct perm_data *p = NULL;
	struct list_head *pos = NULL;
	int i = 0;
	int total = 0;

	mutex_lock(&allowlist_mutex);
	list_for_each (pos, &allow_list) {
		p = list_entry(pos, struct perm_data, list);
		if (p->profile.allow_su == allow) {
			if (i < capacity)
				array[i] = p->profile.current_uid;
			i++;
		}
		total++;
	}
	mutex_unlock(&allowlist_mutex);

	if (count_out)
		*count_out = (i < capacity) ? i : capacity;
	if (total_out)
		*total_out = total;
	return true;
}
/* ---- end rksu abi backport ---- */
"""

SUPERCALLS_H_APPEND = """
/* ---- appended by tools/rksu_abi_backport.py (v3.2.2 manager ABI) ---- */
struct ksu_new_get_allow_list_cmd {
	__u16 count; /* Input / Output: number of UIDs in array */
	__u16 total_count; /* Output: total number of UIDs in requested list */
	__u32 uids[0]; /* Output: array of allowed/denied UIDs */
};

struct ksu_get_sulog_fd_cmd {
	__u32 flags; /* Input: reserved, must be 0 */
};

#define KSU_IOCTL_NEW_GET_ALLOW_LIST _IOWR('K', 6, struct ksu_new_get_allow_list_cmd)
#define KSU_IOCTL_NEW_GET_DENY_LIST _IOWR('K', 7, struct ksu_new_get_allow_list_cmd)
#define KSU_IOCTL_SET_INIT_PGRP _IO('K', 19)
#define KSU_IOCTL_GET_SULOG_FD _IOW('K', 20, struct ksu_get_sulog_fd_cmd)
/* ---- end """ + MARK + """ ---- */
"""

SUPERCALLS_C_HANDLERS = """
/* ---- appended by tools/rksu_abi_backport.py (v3.2.2 manager ABI) ---- */
#ifdef CONFIG_KSU
extern bool ksu_get_allow_list_bounded(int *array, int capacity, int *count_out,
				       int *total_out, bool allow);
#endif

static int do_new_get_allow_list_common(void __user *arg, bool allow)
{
	struct ksu_new_get_allow_list_cmd cmd;
	int *arr = NULL;
	int cnt = 0, total = 0;
	int err = 0;

	if (copy_from_user(&cmd, arg, sizeof(cmd)))
		return -EFAULT;

	cnt = cmd.count;
	if (cnt) {
		arr = kmalloc(sizeof(int) * cnt, GFP_KERNEL);
		if (!arr)
			return -ENOMEM;
	}

	if (!ksu_get_allow_list_bounded(arr, cnt, &cnt, &total, allow)) {
		err = -EFAULT;
		goto out;
	}

	cmd.count = (typeof(cmd.count))cnt;
	cmd.total_count = (typeof(cmd.total_count))total;

	if (copy_to_user(arg, &cmd, sizeof(cmd))) {
		err = -EFAULT;
		goto out;
	}

	if (cnt && copy_to_user(
			&((struct ksu_new_get_allow_list_cmd __user *)arg)->uids,
			arr, sizeof(int) * cnt)) {
		err = -EFAULT;
	}

out:
	kfree(arr);
	return err;
}

static int do_new_get_allow_list(void __user *arg)
{
	return do_new_get_allow_list_common(arg, true);
}

static int do_new_get_deny_list(void __user *arg)
{
	return do_new_get_allow_list_common(arg, false);
}

static int do_set_init_pgrp(void __user *arg)
{
	int err;

	write_lock_irq(&tasklist_lock);
	{
		struct task_struct *p = current->group_leader;
		struct pid *init_group = task_pgrp(&init_task);

		err = -EPERM;
		if (task_session(p) != task_session(&init_task))
			goto out;

		err = 0;
		if (task_pgrp(p) != init_group)
			change_pid(p, PIDTYPE_PGID, init_group);
	}
out:
	write_unlock_irq(&tasklist_lock);
	return err;
}

static int do_get_sulog_fd(void __user *arg)
{
	/* The susfs branch has no sulog fd infrastructure; report unsupported
	 * so the manager shows sulog as off instead of a dead ioctl. */
	return -EOPNOTSUPP;
}
/* ---- end """ + MARK + """ ---- */
"""

SUPERCALLS_C_TABLE = """\t{ .cmd = KSU_IOCTL_NEW_GET_ALLOW_LIST, .name = \"NEW_GET_ALLOW_LIST\", .handler = do_new_get_allow_list, .perm_check = manager_or_root },
\t{ .cmd = KSU_IOCTL_NEW_GET_DENY_LIST, .name = \"NEW_GET_DENY_LIST\", .handler = do_new_get_deny_list, .perm_check = manager_or_root },
\t{ .cmd = KSU_IOCTL_SET_INIT_PGRP, .name = \"SET_INIT_PGRP\", .handler = do_set_init_pgrp, .perm_check = manager_or_root },
\t{ .cmd = KSU_IOCTL_GET_SULOG_FD, .name = \"GET_SULOG_FD\", .handler = do_get_sulog_fd, .perm_check = manager_or_root },
"""

TABLE_RE = re.compile(
    r"\t// Sentinel\r?\n"
    r"\t\{ \.cmd = 0, \.name = NULL, \.handler = NULL, \.perm_check = NULL \}\r?\n")


def append_file(path, text, done):
    s = open(path, newline="").read()
    if done in s:
        print("%s: already patched" % path)
        return
    open(path, "a", newline="").write(text)
    print("%s: appended" % path)


def main():
    # 1) bounded allowlist iterator
    s = open("drivers/kernelsu/allowlist.c", newline="").read()
    if "ksu_get_allow_list_bounded" in s:
        print("allowlist.c: already patched")
    else:
        open("drivers/kernelsu/allowlist.c", "a", newline="").write(
            ALLOWLIST_C_APPEND)
        print("allowlist.c: bounded iterator added")

    # declaration into allowlist.h (before its final #endif if guarded)
    h = "drivers/kernelsu/allowlist.h"
    s = open(h, newline="").read()
    if "ksu_get_allow_list_bounded" in s:
        print("allowlist.h: already patched")
    else:
        decl = ("/* ---- appended by tools/rksu_abi_backport.py ---- */\n"
                "bool ksu_get_allow_list_bounded(int *array, int capacity,\n"
                "				int *count_out, int *total_out,\n"
                "				bool allow);\n")
        idx = s.rstrip().rfind("#endif")
        if idx != -1:
            s = s[:idx] + decl + s[idx:]
        else:
            s = s + decl
        open(h, "w", newline="").write(s)
        print("allowlist.h: declaration added")

    # 2) ioctl defines + structs
    append_file("drivers/kernelsu/supercalls.h", SUPERCALLS_H_APPEND, MARK)

    # 3) handlers + table entries
    s = open("drivers/kernelsu/supercalls.c", newline="").read()
    if MARK not in s:
        # handlers must be defined BEFORE the ioctl table that references them
        table_re = re.compile(
            r"[ \t]*// IOCTL handlers mapping table\r?\n"
            r"static const struct ksu_ioctl_cmd_map ksu_ioctl_handlers\[\] = \{")
        if len(table_re.findall(s)) != 1:
            sys.exit("supercalls.c: table-def anchor not found exactly once (%d)"
                     % len(table_re.findall(s)))
        s = table_re.sub(lambda m: SUPERCALLS_C_HANDLERS + "\n\n" + m.group(0),
                         s, count=1)
        if len(TABLE_RE.findall(s)) != 1:
            sys.exit("supercalls.c: table anchor not found exactly once (%d)"
                     % len(TABLE_RE.findall(s)))
        s = TABLE_RE.sub(lambda m: SUPERCALLS_C_TABLE + m.group(0), s, count=1)
        open("drivers/kernelsu/supercalls.c", "w", newline="").write(s)
        print("supercalls.c: handlers + table entries added")
    else:
        print("supercalls.c: already patched")

    # 4) version bump so the manager's min-version gate (>= 32377) passes
    mk = "drivers/kernelsu/Makefile"
    s = open(mk, newline="").read()
    if "KSU_VERSION=32490" in s:
        print("Makefile: version already bumped")
    else:
        s, n = re.subn(r"KSU_VERSION=\d+", "KSU_VERSION=32490", s, count=1)
        if n != 1:
            sys.exit("Makefile: KSU_VERSION not found")
        open(mk, "w", newline="").write(s)
        print("Makefile: KSU_VERSION bumped to 32490")

    print("rksu_abi_backport: done")


if __name__ == "__main__":
    main()
