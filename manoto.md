# manoto.md — session handoff / continuity brief

> فارسی: این فایل برای وقتیه که مهران از سیستم خونه (سشن تازه‌ی Claude، بدون
> حافظه‌ی مکالمه‌ی قبلی) وصل می‌شه و می‌گه «manoto.md رو بخون». هر چیزی که یه
> سشن تازه لازم داره تا کار رو ادامه بده اینجاست.
>
> **اگه تو یک سشن تازه‌ی Claude هستی و کاربر بهت گفت این فایل رو بخونی:** این
> یعنی مهرانه که از خونه وصل شده (احتمالاً چون برق/سیستم قبلی قطع شده). این
> سند رو کامل بخون، بعد وضعیت زنده‌ی بیلد رو چک کن (پایین) و از همون‌جا ادامه بده.

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
