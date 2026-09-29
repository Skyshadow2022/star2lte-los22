// SPDX-License-Identifier: GPL-2.0
/*
 * ksu_susfs_v2 - userspace CLI for the susfs commands dispatched by the
 * modern rsuntk kernel line (sys_reboot supercall: magic1 0xDEADBEEF,
 * magic2 = SUSFS_MAGIC, cmd = CMD_SUSFS_*, arg = pointer-to-pointer).
 *
 * CLI-compatible with the sidex15 R28 module scripts (SUSFS_BIN invocations):
 *   show version | show enabled_features | show variant
 *   add_sus_path <path>
 *   add_sus_kstat_statically <path> <ino> <dev> <nlink> <size>
 *                            <atime> <atime_nsec> <mtime> <mtime_nsec>
 *                            <ctime> <ctime_nsec> <blocks> <blksize>
 *   update_sus_kstat <path>
 *   add_try_umount <path> <mode 0|1>
 *   set_uname <release> <build>
 *   enable_log <0|1>
 *   add_open_redirect <orig> <new> [uid_scheme]
 *   spoof_cmdline_or_bootconfig <file>
 *   add_sus_map / add_sus_path_loop / sus_su / set_avc_log_spoofing /
 *   hide_sus_mnts_for_all_procs <0|1>   (sent; kernel no-ops them)
 *
 * Struct layouts match tools/rksu_susfs_compat.c (v2-era ABI). The supercall
 * returns -EINVAL from the reboot fallthrough even on success - read the
 * struct's err field instead.
 *
 * Build (CI): aarch64-linux-gnu-gcc -static -O2 -o ksu_susfs ksu_susfs_v2.c
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <errno.h>
#include <sys/stat.h>
#include <sys/syscall.h>

#define KSU_INSTALL_MAGIC1 0xDEADBEEF
#define SUSFS_MAGIC 0xFAFAFAFA

#define CMD_SUSFS_ADD_SUS_PATH 0x55550
#define CMD_SUSFS_SET_ANDROID_DATA_ROOT_PATH 0x55551
#define CMD_SUSFS_SET_SDCARD_ROOT_PATH 0x55552
#define CMD_SUSFS_ADD_SUS_PATH_LOOP 0x55553
#define CMD_SUSFS_HIDE_SUS_MNTS_FOR_ALL_PROCS 0x55561
#define CMD_SUSFS_ADD_SUS_KSTAT 0x55570
#define CMD_SUSFS_UPDATE_SUS_KSTAT 0x55571
#define CMD_SUSFS_ADD_SUS_KSTAT_STATICALLY 0x55572
#define CMD_SUSFS_ADD_TRY_UMOUNT 0x55580
#define CMD_SUSFS_SET_UNAME 0x55590
#define CMD_SUSFS_ENABLE_LOG 0x555a0
#define CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG 0x555b0
#define CMD_SUSFS_ADD_OPEN_REDIRECT 0x555c0
#define CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING 0x60010
#define CMD_SUSFS_ADD_SUS_MAP 0x60020
#define CMD_SUSFS_SHOW_VERSION 0x555e1
#define CMD_SUSFS_SHOW_ENABLED_FEATURES 0x555e2
#define CMD_SUSFS_SHOW_VARIANT 0x555e3
#define CMD_SUSFS_SUS_SU 0x60000

#define SUSFS_MAX_LEN_PATHNAME 256
#define SUSFS_FAKE_CMDLINE_OR_BOOTCONFIG_SIZE 4096
#define SUSFS_ENABLED_FEATURES_SIZE 8192
#define __NEW_UTS_LEN 64

struct sus_path_arg {
	char target_pathname[SUSFS_MAX_LEN_PATHNAME];
	int err;
};

struct sus_kstat_arg {
	unsigned char is_statically;
	unsigned long target_ino;
	char target_pathname[SUSFS_MAX_LEN_PATHNAME];
	unsigned long spoofed_ino;
	unsigned long spoofed_dev;
	unsigned int spoofed_nlink;
	long long spoofed_size;
	long spoofed_atime_tv_sec;
	unsigned long spoofed_atime_tv_nsec;
	long spoofed_mtime_tv_sec;
	unsigned long spoofed_mtime_tv_nsec;
	long spoofed_ctime_tv_sec;
	unsigned long spoofed_ctime_tv_nsec;
	long long spoofed_blocks;
	long spoofed_blksize;
	int flags;
	int err;
};

struct uname_arg {
	char release[__NEW_UTS_LEN + 1];
	char version[__NEW_UTS_LEN + 1];
	int err;
};

struct try_umount_arg {
	char target_pathname[SUSFS_MAX_LEN_PATHNAME];
	int mnt_mode;
};

struct open_redirect_arg {
	char target_pathname[SUSFS_MAX_LEN_PATHNAME];
	char redirected_pathname[SUSFS_MAX_LEN_PATHNAME];
	int uid_scheme;
	int err;
};

struct cmdline_arg {
	char fake_cmdline_or_bootconfig[SUSFS_FAKE_CMDLINE_OR_BOOTCONFIG_SIZE];
	int err;
};

struct log_arg {
	unsigned char enabled;
	int err;
};

struct variant_arg {
	char susfs_variant[16];
	int err;
};

struct version_arg {
	char susfs_version[16];
	int err;
};

struct features_arg {
	char enabled_features[SUSFS_ENABLED_FEATURES_SIZE];
	int err;
};

/* Returns the reboot-syscall errno (always -EINVAL here on success paths);
 * callers must read the struct's err field for the real result. */
static long susfs_supercall(unsigned int cmd, void *struct_ptr)
{
	void *argp = struct_ptr;

	return syscall(__NR_reboot, KSU_INSTALL_MAGIC1, SUSFS_MAGIC, cmd, &argp);
}

static void copy_path(char *dst, const char *src)
{
	strncpy(dst, src, SUSFS_MAX_LEN_PATHNAME - 1);
	dst[SUSFS_MAX_LEN_PATHNAME - 1] = '\0';
}

static int cmd_add_sus_path(int argc, char **argv)
{
	struct sus_path_arg a = { 0 };

	if (argc < 1) {
		fprintf(stderr, "usage: ksu_susfs add_sus_path <path>\n");
		return 1;
	}
	copy_path(a.target_pathname, argv[0]);
	susfs_supercall(CMD_SUSFS_ADD_SUS_PATH, &a);
	if (a.err) {
		fprintf(stderr, "add_sus_path: err %d\n", a.err);
		return 1;
	}
	printf("sus_path added: %s\n", argv[0]);
	return 0;
}

static int do_add_sus_kstat(unsigned int cmd, int argc, char **argv,
			    int statically)
{
	struct sus_kstat_arg a = { 0 };
	struct stat st;

	if (argc < 1) {
		fprintf(stderr,
			"usage: ksu_susfs add_sus_kstat_statically <path> <ino> <dev> <nlink> "
			"<size> <atime> <atime_nsec> <mtime> <mtime_nsec> <ctime> <ctime_nsec> "
			"<blocks> <blksize>\n"
			"       ksu_susfs update_sus_kstat <path>\n");
		return 1;
	}

	copy_path(a.target_pathname, argv[0]);
	a.is_statically = statically ? 1 : 0;

	if (statically) {
		if (argc < 13) {
			fprintf(stderr, "add_sus_kstat_statically: need 13 args\n");
			return 1;
		}
		a.target_ino = strtoul(argv[1], NULL, 0);
		a.spoofed_ino = strtoul(argv[1], NULL, 0);
		a.spoofed_dev = strtoul(argv[2], NULL, 0);
		a.spoofed_nlink = strtoul(argv[3], NULL, 0);
		a.spoofed_size = atoll(argv[4]);
		a.spoofed_atime_tv_sec = atol(argv[5]);
		a.spoofed_atime_tv_nsec = strtoul(argv[6], NULL, 0);
		a.spoofed_mtime_tv_sec = atol(argv[7]);
		a.spoofed_mtime_tv_nsec = strtoul(argv[8], NULL, 0);
		a.spoofed_ctime_tv_sec = atol(argv[9]);
		a.spoofed_ctime_tv_nsec = strtoul(argv[10], NULL, 0);
		a.spoofed_blocks = atoll(argv[11]);
		a.spoofed_blksize = atol(argv[12]);
	} else {
		/* update_sus_kstat: refresh the spoofed kstat from the real file */
		if (stat(argv[0], &st)) {
			fprintf(stderr, "update_sus_kstat: stat(%s): %s\n",
				argv[0], strerror(errno));
			return 1;
		}
		a.target_ino = st.st_ino;
		a.spoofed_ino = st.st_ino;
		a.spoofed_dev = st.st_dev;
		a.spoofed_nlink = st.st_nlink;
		a.spoofed_size = st.st_size;
		a.spoofed_atime_tv_sec = st.st_atim.tv_sec;
		a.spoofed_atime_tv_nsec = st.st_atim.tv_nsec;
		a.spoofed_mtime_tv_sec = st.st_mtim.tv_sec;
		a.spoofed_mtime_tv_nsec = st.st_mtim.tv_nsec;
		a.spoofed_ctime_tv_sec = st.st_ctim.tv_sec;
		a.spoofed_ctime_tv_nsec = st.st_ctim.tv_nsec;
		a.spoofed_blocks = st.st_blocks;
		a.spoofed_blksize = st.st_blksize;
	}

	susfs_supercall(cmd, &a);
	if (a.err) {
		fprintf(stderr, "sus_kstat: err %d\n", a.err);
		return 1;
	}
	printf("sus_kstat %s: %s\n", statically ? "added" : "updated", argv[0]);
	return 0;
}

static int cmd_add_try_umount(int argc, char **argv)
{
	struct try_umount_arg a = { 0 };

	if (argc < 2) {
		fprintf(stderr, "usage: ksu_susfs add_try_umount <path> <mode 0|1>\n");
		return 1;
	}
	copy_path(a.target_pathname, argv[0]);
	a.mnt_mode = atoi(argv[1]);
	susfs_supercall(CMD_SUSFS_ADD_TRY_UMOUNT, &a);
	printf("try_umount added: %s (mode %d)\n", argv[0], a.mnt_mode);
	return 0;
}

static int cmd_set_uname(int argc, char **argv)
{
	struct uname_arg a = { 0 };

	if (argc < 2) {
		fprintf(stderr, "usage: ksu_susfs set_uname <release> <build>\n");
		return 1;
	}
	strncpy(a.release, argv[0], __NEW_UTS_LEN);
	strncpy(a.version, argv[1], __NEW_UTS_LEN);
	susfs_supercall(CMD_SUSFS_SET_UNAME, &a);
	if (a.err) {
		fprintf(stderr, "set_uname: err %d\n", a.err);
		return 1;
	}
	printf("uname spoofed: %s / %s\n", argv[0], argv[1]);
	return 0;
}

static int cmd_enable_log(int argc, char **argv)
{
	struct log_arg a = { 0 };

	if (argc < 1) {
		fprintf(stderr, "usage: ksu_susfs enable_log <0|1>\n");
		return 1;
	}
	a.enabled = atoi(argv[0]) ? 1 : 0;
	susfs_supercall(CMD_SUSFS_ENABLE_LOG, &a);
	printf("log %s\n", a.enabled ? "enabled" : "disabled");
	return 0;
}

static int cmd_add_open_redirect(int argc, char **argv)
{
	struct open_redirect_arg a = { 0 };

	if (argc < 2) {
		fprintf(stderr, "usage: ksu_susfs add_open_redirect <orig> <new> [uid_scheme]\n");
		return 1;
	}
	copy_path(a.target_pathname, argv[0]);
	copy_path(a.redirected_pathname, argv[1]);
	a.uid_scheme = argc >= 3 ? atoi(argv[2]) : 0;
	susfs_supercall(CMD_SUSFS_ADD_OPEN_REDIRECT, &a);
	if (a.err) {
		fprintf(stderr, "add_open_redirect: err %d\n", a.err);
		return 1;
	}
	printf("open_redirect: %s -> %s\n", argv[0], argv[1]);
	return 0;
}

static int cmd_spoof_cmdline(int argc, char **argv)
{
	struct cmdline_arg a = { 0 };
	int fd, n;

	if (argc < 1) {
		fprintf(stderr, "usage: ksu_susfs spoof_cmdline_or_bootconfig <file>\n");
		return 1;
	}
	fd = open(argv[0], O_RDONLY);
	if (fd < 0) {
		fprintf(stderr, "open(%s): %s\n", argv[0], strerror(errno));
		return 1;
	}
	n = read(fd, a.fake_cmdline_or_bootconfig,
		 SUSFS_FAKE_CMDLINE_OR_BOOTCONFIG_SIZE - 1);
	close(fd);
	if (n < 0) {
		fprintf(stderr, "read: %s\n", strerror(errno));
		return 1;
	}
	a.fake_cmdline_or_bootconfig[n] = '\0';
	susfs_supercall(CMD_SUSFS_SET_CMDLINE_OR_BOOTCONFIG, &a);
	printf("cmdline/bootconfig spoofed (%d bytes)\n", n);
	return 0;
}

static int cmd_noop(unsigned int cmd, const char *name)
{
	void *dummy = NULL;

	susfs_supercall(cmd, &dummy);
	printf("%s sent (kernel may no-op it)\n", name);
	return 0;
}

static int cmd_show_version(void)
{
	struct version_arg a = { 0 };

	susfs_supercall(CMD_SUSFS_SHOW_VERSION, &a);
	printf("%s\n", a.susfs_version);
	return 0;
}

static int cmd_show_variant(void)
{
	struct variant_arg a = { 0 };

	susfs_supercall(CMD_SUSFS_SHOW_VARIANT, &a);
	printf("%s\n", a.susfs_variant);
	return 0;
}

static int cmd_show_features(void)
{
	struct features_arg a = { 0 };

	susfs_supercall(CMD_SUSFS_SHOW_ENABLED_FEATURES, &a);
	if (a.err) {
		fprintf(stderr, "show_enabled_features: err %d\n", a.err);
		return 1;
	}
	printf("%s", a.enabled_features);
	return 0;
}

int main(int argc, char **argv)
{
	if (getuid() != 0) {
		fprintf(stderr, "must run as root\n");
		return 1;
	}
	if (argc < 2) {
		fprintf(stderr,
			"ksu_susfs v2 (modern reboot-syscall ABI)\n"
			"commands: show version | show variant | show enabled_features | "
			"add_sus_path | add_sus_kstat_statically | update_sus_kstat | "
			"add_try_umount | set_uname | enable_log | add_open_redirect | "
			"spoof_cmdline_or_bootconfig | add_sus_map | add_sus_path_loop | "
			"sus_su | set_avc_log_spoofing | hide_sus_mnts_for_all_procs\n");
		return 1;
	}

	const char *c = argv[1];
	int rest = argc - 2;
	char **restv = argv + 2;

	if (!strcmp(c, "show") && rest >= 1) {
		if (!strcmp(restv[0], "version"))
			return cmd_show_version();
		if (!strcmp(restv[0], "variant"))
			return cmd_show_variant();
		if (!strcmp(restv[0], "enabled_features"))
			return cmd_show_features();
		fprintf(stderr, "unknown: show %s\n", restv[0]);
		return 1;
	}
	if (!strcmp(c, "add_sus_path"))
		return cmd_add_sus_path(rest, restv);
	if (!strcmp(c, "add_sus_kstat_statically"))
		return do_add_sus_kstat(CMD_SUSFS_ADD_SUS_KSTAT_STATICALLY, rest, restv, 1);
	if (!strcmp(c, "add_sus_kstat"))
		return do_add_sus_kstat(CMD_SUSFS_ADD_SUS_KSTAT, rest, restv, 1);
	if (!strcmp(c, "update_sus_kstat"))
		return do_add_sus_kstat(CMD_SUSFS_UPDATE_SUS_KSTAT, rest, restv, 0);
	if (!strcmp(c, "add_try_umount"))
		return cmd_add_try_umount(rest, restv);
	if (!strcmp(c, "set_uname"))
		return cmd_set_uname(rest, restv);
	if (!strcmp(c, "enable_log"))
		return cmd_enable_log(rest, restv);
	if (!strcmp(c, "add_open_redirect"))
		return cmd_add_open_redirect(rest, restv);
	if (!strcmp(c, "spoof_cmdline_or_bootconfig"))
		return cmd_spoof_cmdline(rest, restv);
	if (!strcmp(c, "add_sus_map"))
		return cmd_noop(CMD_SUSFS_ADD_SUS_MAP, "add_sus_map");
	if (!strcmp(c, "add_sus_path_loop"))
		return cmd_noop(CMD_SUSFS_ADD_SUS_PATH_LOOP, "add_sus_path_loop");
	if (!strcmp(c, "sus_su"))
		return cmd_noop(CMD_SUSFS_SUS_SU, "sus_su");
	if (!strcmp(c, "set_avc_log_spoofing"))
		return cmd_noop(CMD_SUSFS_ENABLE_AVC_LOG_SPOOFING, "set_avc_log_spoofing");
	if (!strcmp(c, "hide_sus_mnts_for_all_procs"))
		return cmd_noop(CMD_SUSFS_HIDE_SUS_MNTS_FOR_ALL_PROCS,
				"hide_sus_mnts_for_all_procs");

	fprintf(stderr, "unknown command: %s\n", c);
	return 1;
}
