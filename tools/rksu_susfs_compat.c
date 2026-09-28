// SPDX-License-Identifier: GPL-2.0
/*
 * rksu_susfs_compat.c - ABI adapter between rsuntk KernelSU (susfs-rksu-master,
 * which speaks the susfs v2-era interface: handlers take `void __user **` and
 * structs carry an `err` field) and the susfs v1.5.5 fs-layer that actually
 * works on this 4.9 ExyHyperBrick tree.
 *
 * The kernel-side hiding engine (susfs.c, fs/ hooks) is untouched v1.5.5.
 * This file only:
 *   - translates v2 command structs to the v1.5.5 structs (kern_path() where
 *     v2 dropped target_ino),
 *   - feeds the renamed v1.5.5 entry points (susfs_*_impl, see
 *     tools/rksu_compat_wire.py) through set_fs(KERNEL_DS) so they can copy
 *     from kernel-built structs,
 *   - reports the v2 manager ABI (enabled features / variant / version),
 *   - stubs the v2-only features that the v1.5.5 engine has no fs hooks for
 *     (sus_path_loop, sus_map, mnt-id reorder) as graceful no-ops.
 *
 * Built as part of the kernelsu module (wired into drivers/kernelsu/Makefile).
 */

#include <linux/version.h>
#include <linux/module.h>
#include <linux/kernel.h>
#include <linux/sched.h>
#include <linux/cred.h>
#include <linux/slab.h>
#include <linux/stddef.h>
#include <linux/string.h>
#include <linux/security.h>
#include <linux/path.h>
#include <linux/namei.h>
#include <linux/uaccess.h>
#include <asm/uaccess.h>
#include <linux/susfs.h>
#include <linux/susfs_def.h>

#define PROC_UMOUNTED_BIT TASK_STRUCT_PROC_UMOUNTED

/*
 * v2-era user structs (layouts per susfs v2.3.0 headers; SUSFS_MAX_LEN_PATHNAME
 * is 256 in both v1.5.5 and v2). Only these are copied from user; the v1.5.5
 * structs are built in kernel space and passed to the *_impl functions with
 * KERNEL_DS set.
 */
struct st_susfs_sus_path_v2 {
	char                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
	int                     err;
};

struct st_susfs_sus_kstat_v2 {
	bool                    is_statically;
	unsigned long           target_ino;
	char                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
	unsigned long           spoofed_ino;
	unsigned long           spoofed_dev;
	unsigned int            spoofed_nlink;
	long long               spoofed_size;
	long                    spoofed_atime_tv_sec;
	unsigned long           spoofed_atime_tv_nsec;
	long                    spoofed_mtime_tv_sec;
	unsigned long           spoofed_mtime_tv_nsec;
	long                    spoofed_ctime_tv_sec;
	unsigned long           spoofed_ctime_tv_nsec;
	long long               spoofed_blocks;
	long                    spoofed_blksize;
	int                     flags;
	int                     err;
};

struct st_susfs_uname_v2 {
	char                    release[__NEW_UTS_LEN + 1];
	char                    version[__NEW_UTS_LEN + 1];
	int                     err;
};

struct st_susfs_try_umount_v2 {
	char                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
	int                     mnt_mode;
};

struct st_susfs_open_redirect_v2 {
	char                    target_pathname[SUSFS_MAX_LEN_PATHNAME];
	char                    redirected_pathname[SUSFS_MAX_LEN_PATHNAME];
	int                     uid_scheme;
	int                     err;
};

struct st_susfs_cmdline_v2 {
	char                    fake_cmdline_or_bootconfig[SUSFS_FAKE_CMDLINE_OR_BOOTCONFIG_SIZE];
	int                     err;
};

struct st_susfs_log_v2 {
	bool                    enabled;
	int                     err;
};

struct st_susfs_enabled_features_v2 {
	char                    enabled_features[SUSFS_ENABLED_FEATURES_SIZE];
	int                     err;
};

struct st_susfs_variant_v2 {
	char                    susfs_variant[16];
	int                     err;
};

struct st_susfs_version_v2 {
	char                    susfs_version[16];
	int                     err;
};

/* v1.5.5 kernel-side structs we fill for the *_impl calls */
static int kern_path_ino_of(const char *kpath, unsigned long *ino)
{
	struct path path;
	int err;

	err = kern_path(kpath, 0, &path);
	if (err)
		return err;
	*ino = path.dentry->d_inode->i_ino;
	path_put(&path);
	return 0;
}

/* Run an *_impl entry point with a kernel-built struct as its user pointer. */
#define IMPL_WITH_KERNEL_DS(call)                                      \
	do {                                                           \
		mm_segment_t oldfs__ = get_fs();                       \
		set_fs(KERNEL_DS);                                     \
		(call);                                                \
		set_fs(oldfs__);                                       \
	} while (0)

/* ---------------- sus_path ---------------- */

void susfs_add_sus_path(void __user **user_info)
{
	struct st_susfs_sus_path_v2 v2;
	struct st_susfs_sus_path v155;
	unsigned long ino = 0;
	int err;

	if (!user_info || IS_ERR(*user_info))
		return;
	if (copy_from_user(&v2, (void __user *)*user_info, sizeof(v2)))
		return;

	memset(&v155, 0, sizeof(v155));
	v2.target_pathname[SUSFS_MAX_LEN_PATHNAME - 1] = '\0';
	err = kern_path_ino_of(v2.target_pathname, &ino);
	if (err) {
		pr_info("susfs_compat: add_sus_path: kern_path failed: %d\n", err);
		return;
	}
	v155.target_ino = ino;
	memcpy(v155.target_pathname, v2.target_pathname, SUSFS_MAX_LEN_PATHNAME);

	IMPL_WITH_KERNEL_DS(
		susfs_add_sus_path_impl((struct st_susfs_sus_path __user *)&v155));
	pr_info("susfs_compat: add_sus_path done (kern_path err=%d)\n", err);
}

/*
 * v2-only: async sus_path loop for /sdcard/Android/data leak mitigation.
 * No fs hooks for it in the v1.5.5 layer - report gracefully.
 */
void susfs_add_sus_path_loop(void __user **user_info)
{
	pr_info("susfs_compat: CMD_SUSFS_ADD_SUS_PATH_LOOP not supported (v1.5.5 fs layer)\n");
}

void susfs_set_i_state_on_external_dir(void __user **user_info)
{
	pr_info("susfs_compat: SET_ANDROID_DATA/SDCARD_ROOT_PATH not supported (v1.5.5 fs layer)\n");
}

/* ---------------- sus_mount ---------------- */

/*
 * v1.5.5 hides sus mounts for every reader unconditionally, so the v2 toggle
 * is accepted and ignored.
 */
void susfs_set_hide_sus_mnts_for_all_procs(void __user **user_info)
{
	pr_info("susfs_compat: hide_sus_mnts_for_all_procs: always-on in v1.5.5 layer\n");
}

/* ---------------- sus_kstat ---------------- */

void susfs_add_sus_kstat(void __user **user_info)
{
	struct st_susfs_sus_kstat_v2 v2;
	struct st_susfs_sus_kstat v155;

	if (!user_info || IS_ERR(*user_info))
		return;
	if (copy_from_user(&v2, (void __user *)*user_info, sizeof(v2)))
		return;

	memset(&v155, 0, sizeof(v155));
	v155.is_statically = v2.is_statically ? 1 : 0;
	v155.target_ino = v2.target_ino;
	memcpy(v155.target_pathname, v2.target_pathname, SUSFS_MAX_LEN_PATHNAME);
	v155.spoofed_ino = v2.spoofed_ino;
	v155.spoofed_dev = v2.spoofed_dev;
	v155.spoofed_nlink = v2.spoofed_nlink;
	v155.spoofed_size = v2.spoofed_size;
	v155.spoofed_atime_tv_sec = v2.spoofed_atime_tv_sec;
	v155.spoofed_atime_tv_nsec = v2.spoofed_atime_tv_nsec;
	v155.spoofed_mtime_tv_sec = v2.spoofed_mtime_tv_sec;
	v155.spoofed_mtime_tv_nsec = v2.spoofed_mtime_tv_nsec;
	v155.spoofed_ctime_tv_sec = v2.spoofed_ctime_tv_sec;
	v155.spoofed_ctime_tv_nsec = v2.spoofed_ctime_tv_nsec;
	v155.spoofed_blksize = v2.spoofed_blksize;
	v155.spoofed_blocks = v2.spoofed_blocks;

	IMPL_WITH_KERNEL_DS(
		susfs_add_sus_kstat_impl((struct st_susfs_sus_kstat __user *)&v155));
}

void susfs_update_sus_kstat(void __user **user_info)
{
	struct st_susfs_sus_kstat_v2 v2;
	struct st_susfs_sus_kstat v155;

	if (!user_info || IS_ERR(*user_info))
		return;
	if (copy_from_user(&v2, (void __user *)*user_info, sizeof(v2)))
		return;

	memset(&v155, 0, sizeof(v155));
	v155.is_statically = v2.is_statically ? 1 : 0;
	v155.target_ino = v2.target_ino;
	memcpy(v155.target_pathname, v2.target_pathname, SUSFS_MAX_LEN_PATHNAME);
	v155.spoofed_ino = v2.spoofed_ino;
	v155.spoofed_dev = v2.spoofed_dev;
	v155.spoofed_nlink = v2.spoofed_nlink;
	v155.spoofed_size = v2.spoofed_size;
	v155.spoofed_atime_tv_sec = v2.spoofed_atime_tv_sec;
	v155.spoofed_atime_tv_nsec = v2.spoofed_atime_tv_nsec;
	v155.spoofed_mtime_tv_sec = v2.spoofed_mtime_tv_sec;
	v155.spoofed_mtime_tv_nsec = v2.spoofed_mtime_tv_nsec;
	v155.spoofed_ctime_tv_sec = v2.spoofed_ctime_tv_sec;
	v155.spoofed_ctime_tv_nsec = v2.spoofed_ctime_tv_nsec;
	v155.spoofed_blksize = v2.spoofed_blksize;
	v155.spoofed_blocks = v2.spoofed_blocks;

	IMPL_WITH_KERNEL_DS(
		susfs_update_sus_kstat_impl((struct st_susfs_sus_kstat __user *)&v155));
}

/* ---------------- try_umount ---------------- */

void susfs_add_try_umount(void __user **user_info)
{
	struct st_susfs_try_umount_v2 v2;
	struct st_susfs_try_umount v155;

	if (!user_info || IS_ERR(*user_info))
		return;
	/* v1.5.5 layout {path, mode} is a prefix of any v2-era variant. */
	if (copy_from_user(&v2, (void __user *)*user_info, sizeof(v2)))
		return;

	memset(&v155, 0, sizeof(v155));
	memcpy(v155.target_pathname, v2.target_pathname, SUSFS_MAX_LEN_PATHNAME);
	v155.mnt_mode = v2.mnt_mode;

	IMPL_WITH_KERNEL_DS(
		susfs_add_try_umount_impl((struct st_susfs_try_umount __user *)&v155));
}

/* v2 name for what v1.5.5 calls susfs_try_umount(); namespace.c calls it. */
void susfs_try_umount_all(uid_t uid)
{
	susfs_try_umount(uid);
}

/* ---------------- spoof_uname / cmdline ---------------- */

void susfs_set_uname(void __user **user_info)
{
	struct st_susfs_uname_v2 v2;
	struct st_susfs_uname v155;

	if (!user_info || IS_ERR(*user_info))
		return;
	if (copy_from_user(&v2, (void __user *)*user_info, sizeof(v2)))
		return;

	memcpy(v155.release, v2.release, sizeof(v155.release));
	memcpy(v155.version, v2.version, sizeof(v155.version));

	IMPL_WITH_KERNEL_DS(
		susfs_set_uname_impl((struct st_susfs_uname __user *)&v155));
}

void susfs_set_cmdline_or_bootconfig(void __user **user_info)
{
	char __user *uptr;

	if (!user_info || IS_ERR(*user_info))
		return;
	/*
	 * v1.5.5 copies the raw string itself, so hand it the user pointer of
	 * the v2 struct's buffer field (prefix of the v2 8192 buffer).
	 */
	uptr = (char __user *)*user_info +
	       offsetof(struct st_susfs_cmdline_v2, fake_cmdline_or_bootconfig);
	IMPL_WITH_KERNEL_DS(susfs_set_cmdline_or_bootconfig_impl(uptr));
}

/* ---------------- enable_log ---------------- */

void susfs_enable_log(void __user **user_info)
{
	struct st_susfs_log_v2 v2;

	if (!user_info || IS_ERR(*user_info))
		return;
	if (copy_from_user(&v2, (void __user *)*user_info, sizeof(v2)))
		return;
	susfs_set_log(v2.enabled ? true : false);
}

/* ---------------- open_redirect ---------------- */

void susfs_add_open_redirect(void __user **user_info)
{
	struct st_susfs_open_redirect_v2 v2;
	struct st_susfs_open_redirect v155;
	unsigned long ino = 0;
	int err;

	if (!user_info || IS_ERR(*user_info))
		return;
	if (copy_from_user(&v2, (void __user *)*user_info, sizeof(v2)))
		return;

	memset(&v155, 0, sizeof(v155));
	v2.target_pathname[SUSFS_MAX_LEN_PATHNAME - 1] = '\0';
	err = kern_path_ino_of(v2.target_pathname, &ino);
	if (err) {
		pr_info("susfs_compat: add_open_redirect: kern_path failed: %d\n", err);
		return;
	}
	v155.target_ino = ino;
	memcpy(v155.target_pathname, v2.target_pathname, SUSFS_MAX_LEN_PATHNAME);
	memcpy(v155.redirected_pathname, v2.redirected_pathname, SUSFS_MAX_LEN_PATHNAME);

	IMPL_WITH_KERNEL_DS(
		susfs_add_open_redirect_impl((struct st_susfs_open_redirect __user *)&v155));
}

/* ---------------- v2-only toggles, graceful no-ops ---------------- */

void susfs_set_avc_log_spoofing(void __user **user_info)
{
	pr_info("susfs_compat: avc_log_spoofing not supported (v1.5.5 fs layer)\n");
}

/*
 * SUS_MAP has no 4.9 fs hook (its hiding lives in v2's task_mmu.c hunks), so
 * the config is disabled in defconfig; this no-op keeps the kernel linkable
 * if someone flips it back on.
 */
void susfs_add_sus_map(void __user **user_info)
{
	pr_info("susfs_compat: CMD_SUSFS_ADD_SUS_MAP not supported (v1.5.5 fs layer)\n");
}

/* ---------------- manager ABI: features / variant / version ---------------- */

static int copy_config_to_buf(const char *config_string, char *buf_ptr,
			      size_t *copied_size)
{
	size_t tmp_size = strlen(config_string);

	*copied_size += tmp_size;
	if (*copied_size >= SUSFS_ENABLED_FEATURES_SIZE)
		return -EINVAL;
	strncpy(buf_ptr, config_string, tmp_size);
	return 0;
}

void susfs_get_enabled_features(void __user **user_info)
{
	struct st_susfs_enabled_features_v2 *info;
	char *buf_ptr = NULL;
	size_t copied_size = 0;
	int err = 0;

	if (!user_info || IS_ERR(*user_info))
		return;
	info = kzalloc(sizeof(*info), GFP_KERNEL);
	if (!info)
		return;

	if (copy_from_user(info, (void __user *)*user_info, sizeof(*info))) {
		kfree(info);
		return;
	}

	buf_ptr = info->enabled_features;
#ifdef CONFIG_KSU_SUSFS_SUS_PATH
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_SUS_PATH\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_MOUNT
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_SUS_MOUNT\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_AUTO_ADD_SUS_KSU_DEFAULT_MOUNT\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_AUTO_ADD_SUS_BIND_MOUNT\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_AUTO_ADD_TRY_UMOUNT_FOR_BIND_MOUNT\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_SUS_KSTAT
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_SUS_KSTAT\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_UNAME
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_SPOOF_UNAME\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_ENABLE_LOG
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_ENABLE_LOG\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_HIDE_KSU_SUSFS_SYMBOLS\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_SPOOF_CMDLINE_OR_BOOTCONFIG\n", buf_ptr, &copied_size);
	if (err) goto out;
	buf_ptr = info->enabled_features + copied_size;
#endif
#ifdef CONFIG_KSU_SUSFS_OPEN_REDIRECT
	err = copy_config_to_buf("CONFIG_KSU_SUSFS_OPEN_REDIRECT\n", buf_ptr, &copied_size);
	if (err) goto out;
#endif
	info->err = 0;
out:
	if (copy_to_user((void __user *)*user_info, info, sizeof(*info)))
		pr_err("susfs_compat: get_enabled_features: copy_to_user failed\n");
	kfree(info);
}

#if LINUX_VERSION_CODE < KERNEL_VERSION(5, 0, 0)
#define COMPAT_SUSFS_VARIANT "NON-GKI"
#else
#define COMPAT_SUSFS_VARIANT "GKI"
#endif

void susfs_show_variant(void __user **user_info)
{
	struct st_susfs_variant_v2 info;

	if (!user_info || IS_ERR(*user_info))
		return;
	memset(&info, 0, sizeof(info));
	if (copy_from_user(&info, (void __user *)*user_info, sizeof(info))) {
		info.err = -EFAULT;
		goto out;
	}
	strncpy(info.susfs_variant, COMPAT_SUSFS_VARIANT,
		sizeof(info.susfs_variant) - 1);
	info.err = 0;
out:
	if (copy_to_user((void __user *)*user_info, &info, sizeof(info)))
		pr_err("susfs_compat: show_variant: copy_to_user failed\n");
}

void susfs_show_version(void __user **user_info)
{
	struct st_susfs_version_v2 info;

	if (!user_info || IS_ERR(*user_info))
		return;
	memset(&info, 0, sizeof(info));
	if (copy_from_user(&info, (void __user *)*user_info, sizeof(info))) {
		info.err = -EFAULT;
		goto out;
	}
	strncpy(info.susfs_version, SUSFS_VERSION, sizeof(info.susfs_version) - 1);
	info.err = 0;
out:
	if (copy_to_user((void __user *)*user_info, &info, sizeof(info)))
		pr_err("susfs_compat: show_version: copy_to_user failed\n");
}

/* ---------------- proc umounted state (v2 feature, real flag here) ------- */

bool susfs_is_current_proc_umounted(void)
{
	return (current->susfs_task_state & PROC_UMOUNTED_BIT) != 0;
}

void susfs_set_current_proc_umounted(void)
{
	current->susfs_task_state |= PROC_UMOUNTED_BIT;
}

/* ---------------- v2-only setuid-hook calls, no-ops ---------------- */

void susfs_run_sus_path_loop(uid_t uid)
{
	/* sus_path_loop needs fsnotify hooks the v1.5.5 layer lacks. */
}

void susfs_reorder_mnt_id(void)
{
	/*
	 * Cosmetic in v2 (keeps sus mnt_ids contiguous after setuid); hiding
	 * itself is driven by mnt_id >= DEFAULT_SUS_MNT_ID and works without.
	 */
}

/* ---------------- SELinux sid resolution (dropped from modern rksu) ----- */

/*
 * rksu's selinux.c resolves the su/init/zygote/priv_app contexts through this
 * helper; the legacy branch carried it as a static inline, the modern branch
 * expects the fs layer to provide it. Same implementation as the legacy one.
 */
void susfs_set_sid(const char *secctx_name, u32 *out_sid)
{
	int err;

	if (!secctx_name || !out_sid) {
		pr_err("susfs_compat: secctx_name || out_sid is NULL\n");
		return;
	}

	err = security_secctx_to_secid(secctx_name, strlen(secctx_name), out_sid);
	if (err) {
		pr_err("susfs_compat: failed setting sid for '%s', err: %d\n",
		       secctx_name, err);
		return;
	}
	pr_info("susfs_compat: sid '%u' is set for secctx '%s'\n",
		*out_sid, secctx_name);
}
