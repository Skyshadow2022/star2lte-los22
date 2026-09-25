# manoto.md — session handoff / continuity brief

> فارسی: این فایل برای وقتیه که مهران از سیستم خونه (سشن تازه‌ی Claude، بدون
> حافظه‌ی مکالمه‌ی قبلی) وصل می‌شه و می‌گه «manoto.md رو بخون». هر چیزی که یه
> سشن تازه لازم داره تا کار رو ادامه بده اینجاست.
>
> **اگه تو یک سشن تازه‌ی Claude هستی و کاربر بهت گفت این فایل رو بخونی:** این
> یعنی مهرانه که از خونه وصل شده (احتمالاً چون برق/سیستم قبلی قطع شده). این
> سند رو کامل بخون، بعد وضعیت زنده‌ی بیلد رو چک کن (پایین) و از همون‌جا ادامه بده.

## 🔐 Session vault (moving to another machine)

Private repo **`Skyshadow2022/star2lte-session-vault`** holds an AES-256
encrypted 7z (`star2lte-session.7z.001`…) with the Claude session transcript,
project memory and the Hetzner SSH key. Password is known to Mehran only — it is
NOT written in any repo. Restore steps are in that repo's README.
(Claude cannot build/decrypt this archive itself — Claude Code's safety
classifier blocks touching SSH keys / session secrets; Mehran runs the 7z step.)
Without the vault you can still continue from this file alone, but you need the
SSH key to reach the build server.

## ✅ CURRENT STATE — 2026-09-26 (read this first)

**Build #2 is on the phone and FULLY WORKING** (tested by Mehran on 2026-09-26):
LineageOS 22.2 boots · **camera works** · **KernelSU-Next = Working** (root) ·
**MindTheGapps 15 + Google Play work**. Details and lessons: "UPDATE 4" at the bottom.

**Open items, in order:**
1. 💸 **DELETE the Hetzner server now** — no longer needed (SUSFS will be a
   kernel-only build, see below). console.hetzner.cloud → project → server
   **`star2lte-build`** (`5.161.80.56`, label `purpose=los22-build`) → **Delete**.
   Or, from a session that has the Hetzner MCP: `server_delete`.
2. 🔐 Revoke the old GitHub PAT (it is inside the old session transcript).
3. 📱 Restore data from `D:\star2lte-backup\2026-09-23\` (WORK PC only).
4. 🛡️ **SUSFS** (Mehran wants it — hiding root from banking apps). Plan: build
   **only the kernel** on GitHub Actions (fits the free runner, no server),
   repack it into build #2's boot.img, flash just BOOT. Rollback = build #2
   boot.img. First try KernelSU-Next's own per-app "Umount modules"; SUSFS if
   apps still detect root. Needs a susfs variant matched to KernelSU-Next
   legacy v3.2.0 on 4.9 (susfs4ksu patches do NOT apply — see section C).

## ⬇️ DOWNLOADS (GitHub Releases) — latest state 2026-09-26

| What | Release | Status |
|---|---|---|
| **TWRP fix9** (img + Odin tar) | https://github.com/Skyshadow2022/star2lte-los22/releases/tag/twrp-fix9 | ⚠️ works on PE13, but **hangs on the TWRP logo now that /data is LOS FBE** (tries to decrypt). Don't use with LOS. |
| LOS 22.2 build #1 (base) | https://github.com/Skyshadow2022/star2lte-los22/releases/tag/22.2-20260924 | superseded by build #2. Its boot.img = rollback kernel (no KSU) |
| **LOS 22.2 build #2** (camera fix + KernelSU-Next, KPROBES hook) | https://github.com/Skyshadow2022/star2lte-los22/releases/tag/22.2-20260925-build2 | ✅ **flashed 2026-09-26, boots, camera + root + GApps OK** |
| Recovery in use now | official **TWRP 3.7.0_9-0** from twrp.me (star2lte) | ✅ boots with LOS data; sideload works (no decrypt, not needed) |

Build #2 direct zip: https://github.com/Skyshadow2022/star2lte-los22/releases/download/22.2-20260925-build2/lineage-22.2-20260925-UNOFFICIAL-star2lte.zip
Build #2 sha256: zip `d95735a334a837587a9d48e556a083b00a40b2e4bf0e8d78ff7a72fdc9e645e1`,
boot.img `032a6912984e7072ae9a87f56608068a8e37297a154e82d3140b497facf65a14`,
recovery.img `6d9495d9a52bbcbaf5b10f4ff586b545beed0b4969cc65c73fe5340c76e4b3b3`.
Verified before upload: zip's boot.img == KSU kernel (CONFIG_KSU=y, KPROBES_HOOK);
vendor libhwjpeg.so (lib + lib64) exports `_ZN26ExynosJpegEncoderForCameraC1Eb`.

*(Historical — done on 2026-09-26, see UPDATE 4.)* **Next step was:** phone into TWRP fix9 → `adb sideload` build #2 zip
(dirty flash over build #1, no format) → boot → check camera + KernelSU-Next
manager. If bootloop: from TWRP `dd` build #1's boot.img (release 22.2-20260924,
also at `D:\star2lte-rom\2026-09-24\boot.img`) to BOOT — that isolates the
KernelSU kernel as the cause; then switch KSU to MANUAL_HOOK (see section B).
Server 5.161.80.56 is still up (hourly billing) with the tree ready for rebuilds;
delete it in Hetzner when root is confirmed.

TWRP sha256: img `a62808c766c1db21b779f7804eb59eb834ec30c4aec43cc69c64e461ec808aeb`,
odin tar `6c40ca38bf1fa33b14ffb3fb53691926c8e66a637a46e60ec84573f4a2980331`.
Local copy: `D:\star2lte-backup\twrp-fix9-working\`.
Note: the TWRP release is the **tested fix9 image**, not a fresh Actions rebuild
(fix2..fix9 were ramdisk/DT repacks with samsung_pack.py on top of Actions
build #37; a clean rebuild would need those patches folded into the TWRP
device tree first, and would be untested).

## Mission

Build **LineageOS 22.2 (Android 15) for star2lte** (Samsung Galaxy S9+ Exynos
9810, SM-G965F), then flash it and restore Mehran's data. After a clean base
boots, do **build #2 with KernelSU + SUSFS baked into the 4.9 kernel** (native,
because 4.9 is the permanent kernel ceiling for this SoC — no higher version
exists, all the "5.x" branches are still 4.9 with backported features).

This repo (`Skyshadow2022/star2lte-los22`) holds the pipeline: the local
manifest (`.repo-local-manifests/star2lte.xml`) and the GitHub Actions workflow
(unused for the real build — see below).

## Why we build on a cloud server (not Actions, not local)

- Free GitHub Actions runners cap at ~96 GB disk — too small for a full LOS
  source + build. Proven: it hit ENOSPC.
- Local build in Iran is impractical (≈100 GB source download over Iran net).
- Cloud VM: the ~100 GB source syncs on the datacenter link; Mehran only
  downloads the final ~2 GB ROM. GCP wanted a $30 deposit; Crave is approval-
  gated. So we used **Hetzner** (Mehran already has an account, hourly billing).

## LIVE BUILD SERVER (temporary — DELETE when done)

- **Hetzner server** name `star2lte-build`, type **cpx41** (8 vCPU, 16 GB RAM,
  240 GB disk), Ubuntu 22.04, location Ashburn (ash). Label `purpose=los22-build`.
- **IP: `5.161.80.56`** · SSH as **root**.
- **SSH key:** `C:\Users\PAV\.ssh\id_ed25519` (this is the Hetzner key
  `mehran-main`; its pubkey comment is `mehran-vps`). ⚠️ This key file lives on
  the **WORK PC**. From the home PC you must bring this key to reach the server.
- Connect: `ssh -i <path-to>/id_ed25519 root@5.161.80.56`
- **Build lives in a `tmux` session named `build`.** Source: `~/los`. Log:
  `~/build.log`. Output ROM (when done): `~/los/out/target/product/star2lte/`.
- Swap: a 24 GB `/swapfile` (needed so 16 GB RAM survives the soong analysis
  peak). If soong OOMs on a rebuild, add more: `fallocate -l 16G /swapfile2 &&
  chmod 600 /swapfile2 && mkswap /swapfile2 && swapon /swapfile2`.
- Disk was tight; we deleted `~/los/.repo/project-objects` (26 GB of git
  objects, not needed to compile). Consequence: `repo sync` won't work until a
  fresh `repo init`; the ROM version string may be generic. Fine for our goals.

### Check live build status (run these)
```bash
ssh -i <id_ed25519> root@5.161.80.56 '
  tmux has-session -t build && echo RUNNING || echo STOPPED
  grep -oE "\[ *[0-9]+% [0-9]+/[0-9]+\]" ~/build.log | tail -1
  grep -iE "FAILED:|BUILD EXIT|Unresolved symbol|ninja: build stopped" ~/build.log | tail -3
  ls -la ~/los/out/target/product/star2lte/lineage-*.zip 2>/dev/null
  df -h / | tail -1'
```
Re-attach the build console: `ssh -t ... 'tmux attach -t build'` (Ctrl-b d to detach).

## State as of last update (2026-09-24, ~16:50 UTC)

- repo init lineage-22.2 (LineageOS) + our 13-project local manifest → synced OK
  (~117 GB). Trees present: device/samsung/{star2lte,exynos9810-common},
  kernel/samsung/exynos9810 (4.9.337), vendor/samsung/{star2lte,exynos9810-common},
  hardware/samsung*, vendor/lineage.
- **Build ran to 86%**, then failed at `libexynoscamera3.so: Unresolved symbol
  ExynosJpegEncoderForCamera(bool)` (camera blob vs libhwjpeg version mismatch).
- **Fix applied on the server** (NOT yet committed to this repo): added
  `check_elf_files: false,` under `name: "libexynoscamera3",` in
  `~/los/vendor/samsung/star2lte/Android.bp`. Build **resumed** and is finishing
  the remaining ~24k ninja steps. Camera may not work at runtime; fix later with
  a matching `libhwjpeg` blob. **TODO: commit this fix** (e.g. as a patch or a
  note) so it's reproducible.

## Fixes already committed to this repo's manifest (do not re-hit these)

1. Dropped `LineageOS/android_hardware_samsung_slsi_nfc` — no lineage-22.x
   branch (23.2-only repo); NFC comes from the standard trees.
2. Dropped `ExyHyperBrick/..._exynos_dtbh` — on 22.2 `dtbhtoolExynos` is already
   in `hardware/samsung/dtbhtool`; adding it caused a duplicate-module error.

## When the build SUCCEEDS

1. Create a **GitHub Release** on `Skyshadow2022/star2lte-los22` and upload from
   the server (fast datacenter→GitHub link): `lineage-*.zip`, `boot.img`,
   `recovery.img` (LineageOS recovery), plus a `SHA256SUMS`. LOS zip is < 2 GB so
   it fits GitHub's asset limit. Use the token (below) for the upload.
2. Give Mehran the release link. He downloads the ~2 GB zip from GitHub.
3. **DELETE the Hetzner server** to stop billing (server name `star2lte-build`,
   label `purpose=los22-build`). Use the Hetzner MCP `server_delete`, or ask
   Mehran to delete it in the console. Billing is hourly (~€0.14/hr) — do not
   leave it running.
4. Flash: LOS 22 uses **Lineage Recovery** (not TWRP). Flow: Odin the stock
   firmware if needed → boot to Lineage recovery → sideload the zip. Then restore
   data (see below).

## Build #2 — KernelSU + SUSFS (after base boots)

Kernel is `~/los/kernel/samsung/exynos9810` = **4.9.337, non-GKI**, no KSU/SUSFS.
SUSFS has a **`kernel-4.9`** branch: `gitlab.com/simonpunk/susfs4ksu`.
Procedure (from that branch's README, "For non-GKI"):
1. Clone **official KernelSU** (tiann/weishu) at latest release tag into the
   kernel tree (`KernelSU/`). Apply the revert commit
   `tiann/KernelSU@898e9d4f8ca9b2f46b0c6b36b80a872b5b88d899`.
2. Add **manual non-KPROBE hooks** (fs/exec.c, fs/open.c, fs/read_write.c,
   fs/stat.c, drivers/input/input.c) per kernelsu.org non-GKI guide. Replace
   `#ifdef CONFIG_KPROBES` → `#if defined(CONFIG_KPROBES) && 0` inside KernelSU/.
3. Apply SUSFS: `cp kernel_patches/KernelSU/10_enable_susfs_for_ksu.patch KernelSU/`,
   `cp kernel_patches/50_add_susfs_in_kernel-4.9.patch .`, `cp kernel_patches/fs/*
   fs/`, `cp kernel_patches/include/linux/* include/linux/`; then
   `cd KernelSU && patch -p1 < 10_...patch`; `cd .. && patch -p1 < 50_...patch`.
4. Enable `CONFIG_KSU` and `CONFIG_KSU_SUSFS` in
   `arch/arm64/configs/exynos9810-star2lte_defconfig`.
5. Rebuild (`mka bacon` — incremental; only the kernel + boot image rebuild).
Rationale for doing base-first: never validated this tree boots; adding an
untested KSU+SUSFS 4.9 patch on an unproven base makes boot failures impossible
to isolate (same trap as the earlier TWRP saga).

## Secrets & other machines (paths, NOT contents — repo is public)

- **GitHub token:** `C:\Users\PAV\Desktop\tokenGh.txt` (on the WORK PC; classic
  PAT `ghp_...`, full control). Needed for release upload + pushes. ⚠️ Bring it to
  the home PC, or Mehran should **rotate it** and use a new one. It should be
  rotated regardless (it has sat in a plaintext desktop file).
- **Data backup** (pre-migration, from the current PE13 phone): on the WORK PC at
  `D:\star2lte-backup\2026-09-23\` — photos (563), SMS (12045), contacts, call
  log, Telegram + Instagram (data + apks). Has its own `README-restore.md`. This
  folder is **not on the home PC.**
- Phone: SM-G965F, currently on PixelExperience 13 (FBE), rooted with KernelSU,
  adb over USB. A working stock **omni TWRP 3.7.0** is on its RECOVERY partition;
  Odin rescue tar is `C:\Users\PAV\Desktop\recovery-twrp-old.tar` (work PC).

## If continuing from the HOME PC

You likely will NOT have: the SSH key, the GitHub token, the D:\ backup, or the
phone plugged in. So from home you can: read/understand state, check the build
via SSH **only if the key was brought over**, and advise. To actually drive the
server or push to GitHub from home, Mehran must bring `id_ed25519` and the token
(or generate a new token and add a new SSH key to the server via the Hetzner
console). The Hetzner MCP (server create/delete/list) is tied to the Claude
account config, so it may be available from home even without the local files —
use it to inspect or delete the server.

---

## UPDATE 2 — 2026-09-25 (build #1 BOOTS; build #2 = camera + KernelSU in progress)

### Build #1 result: SUCCESS ✅
LineageOS 22.2 (Android 15) **boots** on the phone. Confirmed:
`lineage_star2lte-userdebug 15 BP1A.250505.005`, /data mounts f2fs+inlinecrypt,
zygote/surfaceflinger up.

**Critical install lesson (not a build bug):** after installing the ROM you MUST
**format /data as f2fs**, NOT ext4. TWRP `format data` made it ext4 → LOS fstab
wants f2fs → /data wouldn't mount → apexd aborted → `reboot,apexd-failed`
bootloop. Fix that worked, from TWRP adb (root, no `su`):
```
umount /data 2>/dev/null; umount /dev/block/by-name/USERDATA 2>/dev/null
make_f2fs -g android -O encrypt -O quota -f /dev/block/by-name/USERDATA
```
(kernel DOES support inlinecrypt; the only issue was fs type.) /metadata warnings
in dmesg are non-fatal (device has no /metadata partition; not needed).

### Released
`https://github.com/Skyshadow2022/star2lte-los22/releases/tag/22.2-20260924`
Assets: `lineage-22.2-20260924-UNOFFICIAL-star2lte.zip` (948 MB), boot.img,
recovery.img (LOS recovery), SHA256SUMS. Also downloaded locally to the WORK PC:
`D:\star2lte-rom\2026-09-24\`.

### Flash procedure that worked (all from the custom TWRP already on RECOVERY, via adb)
TWRP on RECOVERY is `3.7.1_12-0` (our earlier build; adb+root, `su` not needed).
```
# 1. push LOS recovery for later (optional):  adb push recovery.img /tmp/
# 2. format data:  adb shell make_f2fs -g android -O encrypt -O quota -f /dev/block/by-name/USERDATA
# 3. install ROM by sideload:
adb shell 'twrp sideload' &   ; sleep 6 ; adb sideload lineage-22.2-*.zip
# 4. reboot:  adb reboot
```
Install log shows "Patching system/vendor/odm ... script succeeded ... RC=0".
We kept our TWRP on RECOVERY (did NOT flash LOS recovery) so the phone stays
adb-recoverable during testing.

### Known issue on build #1: CAMERA does not work
`libexynoscamera3.so` (blob) needs `_ZN26ExynosJpegEncoderForCameraC1Eb`
(1-arg ctor `ExynosJpegEncoderForCamera(bool)`), but the A15 source libhwjpeg
only emits the 2-arg `C1Ebj` (constructor is `#if HWJPEG_ANDROID_VERSION >= 10`
= `(bool,uint)`). We shipped build #1 with `check_elf_files: false` on
libexynoscamera3 to let it build; camera fails at runtime. **Build #2 fixes it.**

## Build #2 — camera fix + KernelSU (SUSFS deferred). ALL CHANGES ARE ON THE
## HETZNER SERVER ONLY (not committed). Reproduce them if the server is lost.

Server: `5.161.80.56` root, key `C:\Users\PAV\.ssh\id_ed25519`. Source `~/los`.
Build kernel-only fast: `tmux new-session -d -s kbuild "/root/kbuild.sh"`
(kbuild.sh = source build/envsetup.sh; breakfast star2lte userdebug; mka bootimage).
Full ROM: `/root/build.sh` (mka bacon). Remember `umount -l /sys/kernel/debug`
before the ota/zip step or `zip` hangs following the `d -> /sys/kernel/debug`
symlink (a QEMU HID debugfs file blocks the read).

### (A) Camera fix — libhwjpeg 1-arg constructor
Dir: `~/los/hardware/samsung_slsi-linaro/graphics/base/libhwjpeg/`
- `include/ExynosJpegEncoderForCamera.h`, in the `#if HWJPEG_ANDROID_VERSION >= 10`
  branch, change the single ctor decl to TWO:
  ```
  ExynosJpegEncoderForCamera(bool bBTBComp, unsigned int index);
  ExynosJpegEncoderForCamera(bool bBTBComp = true);
  ```
- `ExynosJpegEncoderForCamera.cpp`, before `~ExynosJpegEncoderForCamera()`:
  ```
  #if HWJPEG_ANDROID_VERSION >= 10
  ExynosJpegEncoderForCamera::ExynosJpegEncoderForCamera(bool bBTBComp)
          : ExynosJpegEncoderForCamera(bBTBComp, 0) {}
  #endif
  ```
This emits `C1Eb` so the blob links; keeps `C1Ebj` for source. (We also left
`check_elf_files: false` on libexynoscamera3 in vendor/samsung/star2lte/Android.bp
as belt-and-suspenders — harmless.)

### (B) KernelSU (root) — KernelSU-Next LEGACY, KPROBES hook (non-GKI 4.9)
**STATUS 2026-09-25 12:26 UTC: kernel with KernelSU COMPILES — `mka bootimage`
"build completed successfully", new boot.img 33388560 B. Not yet flashed/tested.**
Kernel dir: `~/los/kernel/samsung/exynos9810/`
1. `curl -LSs https://raw.githubusercontent.com/KernelSU-Next/KernelSU-Next/next/kernel/setup.sh | bash -s next`
   then in `KernelSU-Next/`: `git checkout legacy` (v3.2.0-legacy). This gives
   `drivers/kernelsu -> ../KernelSU-Next/kernel` + Makefile/Kconfig wiring.
   ⚠️ **SYSCALL_TABLE_HOOK does NOT work on 4.9** — hard `#error "syscall table
   hook requires kernel >= 4.17 (pt_regs syscall ABI)"`. Use **KPROBES_HOOK**
   (arm64 4.9 selects HAVE_SYSCALL_TRACEPOINTS, so it's available once KPROBES=y).
2. defconfig `arch/arm64/configs/exynos9810-star2lte_defconfig` append:
   ```
   CONFIG_KPROBES=y
   CONFIG_KSU=y
   # CONFIG_KSU_MANUAL_HOOK is not set
   # CONFIG_KSU_SYSCALL_TABLE_HOOK is not set
   CONFIG_KSU_KPROBES_HOOK=y
   ```
3. **4.9 header/API compat fixes inside `KernelSU-Next/kernel/`** (all done, compiles):
   - ALL `#include <linux/sched/<anything>.h>` (signal, task, task_stack, user, types)
     → `#include <linux/sched.h>`
   - `manager/apk_sign.c`: add `#include "compat/kernel_compat.h"` after `#include "util.h"`
     (provides the <4.12 `kvmalloc` shim already in that header).
   - all `#include <linux/compiler_types.h>` → `#include <linux/compiler.h>` (4.13 split)
   - raw `kernel_write(`/`kernel_read(` → `ksu_kernel_write_compat(`/`ksu_kernel_read_compat(`
     (4.9 has old signatures) in runtime/ksud_integration.c, manager/apk_sign.c,
     manager/throne_tracker.c, policy/allowlist.c (+ ensure compat header included).
   - Note: KPROBES on a Samsung kernel is untested here — if the phone bootloops
     after flashing, fall back to KSU_MANUAL_HOOK (hand-add ksu_handle_* hooks in
     fs/exec.c, fs/open.c, fs/read_write.c, fs/stat.c, drivers/input/input.c).

### (C) SUSFS — DEFERRED (not done yet)
susfs4ksu's patches are written for OFFICIAL KernelSU and do NOT apply to
KernelSU-Next's source (Makefile/allowlist.c differ; 10_enable patch fails).
Plan: use a susfs variant matched to KernelSU-Next (its own susfs support /
matching susfs kernel patch version) AFTER KernelSU root is confirmed working.
Do NOT mix susfs4ksu patches with KernelSU-Next.

### Next steps
0. TWRP: the known-good TWRP (boot+GUI+adb+brightness all OK) is **fix9**, saved at
   `D:\star2lte-backup\twrp-fix9-working\recovery-samsung-37-fix9.img`
   (sha256 a62808c766c1db21b779f7804eb59eb834ec30c4aec43cc69c64e461ec808aeb).
   Flash from any TWRP: `adb push` to /tmp, `dd of=/dev/block/by-name/RECOVERY bs=1048576`,
   then read back the first N 2048-byte pages and compare sha.
1. ✅ Build #2 kernel compile done (KPROBES hook). Optional: test boot.img alone first
   (`dd` to BOOT from TWRP; keep build-#1 boot.img from D:\star2lte-rom\2026-09-24 as rollback).
2. ✅ Full ROM built 2026-09-25 (`/root/build.sh`; debugfs unmounted first).
   Upload trick: create the release locally with `gh`, then upload assets FROM THE
   SERVER with curl to uploads.github.com (token piped over ssh stdin into a 600
   file, deleted after — script `/root/up2.sh`). Never put the token in the repo.
3. ✅ Uploaded to release `22.2-20260925-build2`. TODO: flash (dirty over build #1 keeps
   /data — no re-format needed since /data is already f2fs). Verify root via the
   KernelSU-Next manager app + `adb shell su`.
4. Then tackle SUSFS (C).

---

## UPDATE 4 — 2026-09-26 (build #2 FLASHED & WORKING, from the HOME PC)

Continued from Mehran's home PC (Windows user `Mehran`). Session vault restored
(7z archive in `star2lte-session-vault`; SSH key was NOT installed — the Claude
Code safety classifier blocks it, Mehran has to copy it himself). Local copies of
all images are in `G:\claude\star2lte-rom\` on the home PC (build2, build1
boot.img rollback, twrp-fix9, MindTheGapps, KernelSU-Next manager apk; all sha256
verified).

### Result (tested on device by Mehran)
- LOS 22.2 build #2 boots (~90 s), kernel `4.9.337-ies` built 2026-09-25.
- **Camera works** → libhwjpeg 1-arg ctor fix (section A) confirmed.
- **KernelSU-Next: "Working"** with KPROBES_HOOK → no need for MANUAL_HOOK.
  Manager: **KernelSU-Next v3.2.0** (`com.rifsxd.ksunext`, official GitHub
  release `KernelSU_Next_v3.2.0_33129-release.apk`) — matches the v3.2.0-legacy
  kernel side. The old official KernelSU manager (`me.weishu.kernelsu`) is still
  installed and useless with this kernel (can be uninstalled).
- **MindTheGapps-15.0.0-arm64-20260915** installed dirty (after LOS had already
  booted) — Play Store + GMS work, no crashes.

### Lessons (do not re-hit these)
1. **TWRP stuck on logo:** both our decrypt TWRPs (3.7.1_12-0 and fix9) hang on
   the splash once /data holds LOS FBE (they wait on keymaster for PE13 keys).
   *(Cause is a hypothesis, not yet log-confirmed. Evidence source if ever needed:
   fix9's `dbgdump` service writes `/cache/recovery/dbg-{state,dmesg,recovery}-*`
   at t+10/30/60/120 s even during a hung boot. Note: CACHE is now f2fs, and
   dbgdump mounts it as ext4 — so on LOS it can no longer save these logs.)*
   Windows shows only `Unknown USB Device (Device Descriptor Request Failed)`.
   Fix: flash via Odin (AP slot, Auto Reboot OFF) either LOS recovery
   (build2 `recovery.img` in a plain ustar tar) or **official TWRP 3.7.0_9-0**.
   Download mode itself was fine (`SAMSUNG Mobile USB CDC Composite Device`).
2. **LOS recovery sideload aborted** with `failed to set up expected mounts for
   install` + `Invalid f2fs superblock on .../CACHE`: CACHE (600 MB, sda21) was
   still **ext4** from PE13, LOS fstab wants **f2fs**. Fix (no user data):
   `umount /cache; make_f2fs -f /dev/block/by-name/CACHE`.
3. **Flash that worked:** official TWRP → `adb shell twrp sideload` → `adb sideload
   lineage-22.2-20260925-UNOFFICIAL-star2lte.zip` → `script succeeded`, RC=0
   (194 s), dirty over build #1, no data format.
4. **MindTheGapps on official TWRP fails** with `Could not mount /mnt/system!`:
   its installer reads the block device from `/etc/recovery.fstab` in AOSP
   format, but TWRP's fstab is `mountpoint fstype device`. Fix (RAM only, until
   reboot): back up `/etc/recovery.fstab`, drop its `/system` line, append
   `/dev/block/platform/11120000.ufs/by-name/SYSTEM /system ext4 ro wait`, then
   sideload the GApps zip → `/mnt/system mounted … Done!`, RC=0.
5. Git Bash on Windows rewrites `/sdcard/...` for adb → use `MSYS_NO_PATHCONV=1`.
6. Claude Code CLI installs to `%USERPROFILE%\.local\bin\claude.exe` but does
   not add it to PATH — call it by full path or add it to the user PATH.
