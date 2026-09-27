#!/usr/bin/env python3
"""Fix the one susfs 50_ hunk that fuzzy-patch misplaces on lineage-22.2.

The AUTO_ADD_SUS_KSU_DEFAULT_MOUNT usage block belongs inside do_mount(),
right before `dput_out:`. Because ExyHyperBrick's do_mount() is RKP-restructured,
`patch --fuzz` drops the block at file scope (after copy_mount_string), which is
a syntax error ("expected identifier or '('"). Move it to the correct spot.

Run from the kernel root after applying 50_add_susfs_in_kernel-4.9.patch:
  python3 tools/susfs_namespace_fix.py fs/namespace.c
Idempotent and a no-op if the block is already correctly placed.
"""
import sys

BLOCK = """#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT
	// For both Legacy and Magic Mount KernelSU
	if (!retval && susfs_is_auto_add_sus_ksu_default_mount_enabled &&
			(!(flags & (MS_REMOUNT | MS_BIND | MS_SHARED | MS_PRIVATE | MS_SLAVE | MS_UNBINDABLE)))) {
		if (susfs_is_current_ksu_domain()) {
			susfs_auto_add_sus_ksu_default_mount(dir_name);
		}
	}
#endif
"""

# The misplaced copy sits right after copy_mount_string(); remove it there.
MISPLACED_ANCHOR = "	return data ? strndup_user(data, PAGE_SIZE) : NULL;\n}\n\n"
# Correct spot: just before do_mount()'s dput_out cleanup.
DPUT = "dput_out:\n\tpath_put(&path);\n\treturn retval;\n}"


def main(path):
    s = open(path, newline="").read()
    # already correctly placed? (block immediately precedes dput_out)
    if (BLOCK + DPUT) in s:
        print("namespace.c: AUTO_ADD block already correct; nothing to do")
        return
    # 1) remove the misplaced block after copy_mount_string
    misplaced = MISPLACED_ANCHOR + BLOCK
    if misplaced in s:
        s = s.replace(misplaced, MISPLACED_ANCHOR)
        print("namespace.c: removed misplaced AUTO_ADD block")
    else:
        print("namespace.c: misplaced block not found (patch layout changed?)")
    # 2) insert it before dput_out inside do_mount
    if s.count(DPUT) != 1:
        sys.exit("namespace.c: expected exactly one dput_out cleanup, found %d" % s.count(DPUT))
    s = s.replace(DPUT, BLOCK + DPUT)
    open(path, "w", newline="").write(s)
    print("namespace.c: inserted AUTO_ADD block before dput_out in do_mount")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
