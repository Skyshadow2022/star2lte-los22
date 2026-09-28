#!/usr/bin/env python3
"""Merge the two susfs v1.5.5 rejects that don't apply on ExyHyperBrick's
lineage-22.2 tree (fs/stat.c, fs/notify/fdinfo.c).

Both hunks are additive and #ifdef-guarded, so they are inserted verbatim
except for one adaptation: the upstream v1.5.5 code gates the spoof on
  current->susfs_task_state & TASK_STRUCT_NON_ROOT_USER_APP_PROC
but no KSU in the modern (susfs-rksu-master) line ever sets that bit. The
v2-era equivalent check is uid >= 10000 (user apps), which is what susfs
upstream switched to, so we use SUSFS_MIN_USER_APP_UID (added to
susfs_def.h by tools/rksu_compat_wire.py).

Run from the kernel root after applying 50_add_susfs_in_kernel-4.9.patch:
  python3 tools/susfs_v155_fix.py
Idempotent: re-running is a no-op.
"""
import sys

MIN_UID = "SUSFS_MIN_USER_APP_UID"

STAT_INCLUDE_ANCHOR = "#include <linux/pagemap.h>\n"
STAT_INCLUDE_BLOCK = (
    "#include <linux/cred.h>\n"
    "#if defined(CONFIG_KSU_SUSFS_SUS_KSTAT) || defined(CONFIG_KSU_SUSFS_SUS_MOUNT)\n"
    "#include <linux/susfs_def.h>\n"
    "#endif\n"
)
STAT_EXTERN_ANCHOR = "#include <asm/unistd.h>\n"
STAT_EXTERN_BLOCK = (
    "#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n"
    "extern void susfs_sus_ino_for_generic_fillattr(unsigned long ino, struct kstat *stat);\n"
    "#endif\n"
)
STAT_FILLATTR_ANCHOR = (
    "void generic_fillattr(struct inode *inode, struct kstat *stat)\n"
    "{\n"
)
STAT_FILLATTR_BLOCK = (
    "#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT\n"
    "\tif (likely(current_uid().val >= " + MIN_UID + ") &&\n"
    "\t\t\tunlikely(inode->i_state & INODE_STATE_SUS_KSTAT)) {\n"
    "\t\tsusfs_sus_ino_for_generic_fillattr(inode->i_ino, stat);\n"
    "\t\tstat->mode = inode->i_mode;\n"
    "\t\tstat->rdev = inode->i_rdev;\n"
    "\t\tstat->uid = inode->i_uid;\n"
    "\t\tstat->gid = inode->i_gid;\n"
    "\t\treturn;\n"
    "\t}\n"
    "#endif\n"
)

FDINFO_ANCHOR = (
    "\tif (inode) {\n"
    "\t\tseq_printf(m, \"inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 \",\n"
    "\t\t\t   inode_mark->wd, inode->i_ino, inode->i_sb->s_dev,\n"
    "\t\t\t   inotify_mark_user_mask(mark));\n"
)
FDINFO_BLOCK = (
    "\tif (inode) {\n"
    "#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT\n"
    "\t\tif (likely(current_uid().val >= " + MIN_UID + ") &&\n"
    "\t\t\t\tunlikely(inode->i_state & INODE_STATE_SUS_KSTAT)) {\n"
    "\t\t\tstruct path path;\n"
    "\t\t\tchar *pathname = kmalloc(PAGE_SIZE, GFP_KERNEL);\n"
    "\t\t\tchar *dpath;\n"
    "\t\t\tif (!pathname) {\n"
    "\t\t\t\tgoto out_seq_printf;\n"
    "\t\t\t}\n"
    "\t\t\tdpath = d_path(&file->f_path, pathname, PAGE_SIZE);\n"
    "\t\t\tif (!dpath) {\n"
    "\t\t\t\tgoto out_free_pathname;\n"
    "\t\t\t}\n"
    "\t\t\tif (kern_path(dpath, 0, &path)) {\n"
    "\t\t\t\tgoto out_free_pathname;\n"
    "\t\t\t}\n"
    "\t\t\tseq_printf(m, \"inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 \",\n"
    "\t\t\t   inode_mark->wd, path.dentry->d_inode->i_ino,\n"
    "\t\t\t   path.dentry->d_inode->i_sb->s_dev,\n"
    "\t\t\t   inotify_mark_user_mask(mark));\n"
    "\t\t\tshow_mark_fhandle(m, path.dentry->d_inode);\n"
    "\t\t\tseq_putc(m, '\\n');\n"
    "\t\t\tiput(inode);\n"
    "\t\t\tpath_put(&path);\n"
    "\t\t\tkfree(pathname);\n"
    "\t\t\treturn;\n"
    "out_free_pathname:\n"
    "\t\t\tkfree(pathname);\n"
    "\t\t}\n"
    "out_seq_printf:\n"
    "#endif\n"
    "\t\tseq_printf(m, \"inotify wd:%x ino:%lx sdev:%x mask:%x ignored_mask:0 \",\n"
    "\t\t\t   inode_mark->wd, inode->i_ino, inode->i_sb->s_dev,\n"
    "\t\t\t   inotify_mark_user_mask(mark));\n"
)


def patch(path, replacements):
    s = open(path, newline="").read()
    changed = False
    for anchor, block, done_marker in replacements:
        if done_marker in s:
            print("%s: already patched (%s)" % (path, done_marker.splitlines()[0]))
            continue
        if s.count(anchor) != 1:
            sys.exit("%s: expected exactly one anchor, found %d:\n%r"
                     % (path, s.count(anchor), anchor[:80]))
        s = s.replace(anchor, block)
        changed = True
        print("%s: applied %r" % (path, anchor.splitlines()[0]))
    if changed:
        open(path, "w", newline="").write(s)


def main():
    patch("fs/stat.c", [
        (STAT_INCLUDE_ANCHOR, STAT_INCLUDE_ANCHOR + STAT_INCLUDE_BLOCK,
         "#include <linux/susfs_def.h>"),
        (STAT_EXTERN_ANCHOR, STAT_EXTERN_ANCHOR + STAT_EXTERN_BLOCK,
         "extern void susfs_sus_ino_for_generic_fillattr"),
        (STAT_FILLATTR_ANCHOR, STAT_FILLATTR_ANCHOR + STAT_FILLATTR_BLOCK,
         "susfs_sus_ino_for_generic_fillattr(inode->i_ino, stat);"),
    ])
    patch("fs/notify/fdinfo.c", [
        # cred.h for current_uid(); susfs_def.h include already landed via the patch
        ("#include <linux/susfs_def.h>\n",
         "#include <linux/susfs_def.h>\n#include <linux/cred.h>\n",
         "#include <linux/cred.h>"),
        (FDINFO_ANCHOR, FDINFO_BLOCK,
         "d_path(&file->f_path, pathname, PAGE_SIZE)"),
    ])
    print("susfs_v155_fix: done")


if __name__ == "__main__":
    main()
