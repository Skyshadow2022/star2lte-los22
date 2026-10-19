# Device Development Playbook — کرنل، رام، روت، integrity، تیونینگ

> تجربه‌های جمع‌شده از پروژه‌ی star2lte (Galaxy S9+, Exynos 9810). برای هر گوشی
> **جدید** اول این فایل رو بخون — خیلی از دام‌ها قابل‌تعمیم‌ان. وضعیت زنده‌ی
> star2lte توی `manoto.md` ـه؛ این فایل «درس‌ها و روش»ـه، نه وضعیت دستگاه.

---

## 0) فلسفه‌ی کلی کار (the core loop)

**edit → build → flash → test → read logs → fix → repeat.** هیچ‌وقت کور حدس نزن —
وقتی چیزی کار نکرد، **لاگ رو بخون** (logcat, dmesg, boot log, avc denial). ۹۰٪ وقت
جواب توی لاگه.

قوانین سخت که هزینه‌ی زیادی براشون دادیم:
- **قبل هر فلش:** sha فایل رو چک کن، بعد از فلش **readback با sha** بگیر و مقایسه کن.
- **همیشه rollback آماده داشته باش** (کرنل/پارتیشن قبلی با sha مشخص).
- **قبل هر ریبوت از کاربر اجازه بگیر** (ممکنه وسط تماس/کار باشه).
- **هر تغییر مهم → اول تداخل‌هاش رو بررسی کن، بعد اعمال کن.**
- بکاپ دیتای شخصی و بکاپ پارتیشن‌ها قبل از هر کار مخرب.

---

## 1) شناخت دستگاه (قبل از هر چیز)

```
getprop ro.product.device        # codename (مثل star2lte)
getprop ro.product.model         # SM-...
getprop ro.boot.slot_suffix      # خالی = A-only, _a/_b = A/B
getprop ro.build.ab_update       # true = seamless
cat /proc/version ; uname -r     # نسخه‌ی کرنل (سقف SoC)
mount | grep -E " /vendor | /system "   # erofs(ro) یا ext4(قابل‌ویرایش)؟
```

نکات کلیدی که سرنوشت پروژه رو عوض می‌کنن:
- **نسخه‌ی کرنل سقف داره و تغییر نمی‌کنه.** Exynos 9810 روی **4.9.337** قفله؛ همه‌ی
  «5.x»ها هم ته‌ش همون 4.9 با backportـن. این یعنی خیلی از ابزارهای GKI (که 5.10+
  می‌خوان) کار نمی‌کنن → باید نسخه‌ی **legacy/non-GKI** رو پیدا کنی.
- **vendor ext4 یا erofs؟** اگه ext4 و بدون dm-verity باشه، خیلی چیزها (مثل fstab)
  رو بدون بیلد رام می‌شه عوض کرد. اگه erofs(ro) باشه، باید repack/build کنی.
- **dm-verity فعاله؟** اگه پارتیشن مستقیم از `/dev/block/sdaXX` mount شه (نه از
  `/dev/block/dm-X`)، verity روش نیست و ویرایشش bootloop نمی‌ده.

---

## 2) ساخت رام (LineageOS / AOSP)

### زیرساخت بیلد — مهم‌ترین درس
- **GitHub Actions برای رام کامل بس نیست** (~۹۶ گیگ دیسک، سورس LOS ~۱۴۵ گیگ → ENOSPC).
- **بیلد محلی در ایران غیرمنطقیه** (~۱۰۰ گیگ دانلود سورس).
- **راه‌حل: VPS ابری ساعتی** (ما Hetzner cpx41: 8 vCPU / 16GB / 240GB گرفتیم). سورس
  روی لینک دیتاسنتر sync می‌شه، فقط رام نهایی ~۱ گیگ رو خودت دانلود می‌کنی.
  **بعد از کار سرور رو حتماً پاک کن** (ساعتی پول می‌خوره).
- swap زیاد بذار (۸–۲۴ گیگ) چون soong analysis پیک حافظه داره.
- اگه دیسک کم اومد: `rm -rf .repo/project-objects` (۲۶ گیگ، فقط git رو می‌شکنه نه بیلد).

### جریان بیلد
```
repo init -u <lineage manifest> -b <branch>   # مثل lineage-22.2
# local_manifests/<device>.xml: device tree + kernel + vendor + HALs را pin کن
repo sync -c -j$(nproc)
source build/envsetup.sh ; breakfast <device> ; mka bacon
```
- **local manifest رو دقیق pin کن** (شاخه‌ی درست هر ریپو). ریپویی که شاخه‌ی مطابق
  نداره → sync fail. ریپوی تکراری (مثل دو تا dtbh) → «already defined» build fail.
- خروجی: `out/target/product/<device>/lineage-*.zip` + `boot.img` + `recovery.img`.

### دام‌های رام که بهشون خوردیم
- **apexd-failed / bootloop بعد فلش:** fstab رام یه fs type خاص می‌خواد (مثلاً
  `/data` باید **f2fs** باشه نه ext4). با TWRP درست format کن:
  `make_f2fs -g android -O encrypt -O quota -f /dev/block/by-name/USERDATA`.
- **sideload «Invalid f2fs superblock on CACHE»:** پارتیشن CACHE هنوز ext4 بود.
  `umount /cache; make_f2fs -f /dev/block/by-name/CACHE`.
- **دوربین خراب (missing symbol):** روی Exynos، بلاب `libexynoscamera3` یه constructor
  از `libhwjpeg` می‌خواد که با نسخه‌ی اندروید فرق می‌کنه. درس: `HWJPEG_ANDROID_VERSION`
  و layout ساختار `exif_attribute_t` باید با بلاب بخونه (ما مجبور شدیم نسخه ۱۰ نگه
  داریم تا SIGSEGV هنگام ذخیره‌ی عکس نده). برای کامپایل سریع libhwjpeg به‌تنهایی،
  ۵-۶ ریپو رو مستقیم clone کن و با clang runner کامپایل کن (نه sync کامل LOS).
- **ota/zip hang:** `zip -r .` ممکنه یه symlink به debugfs رو دنبال کنه و برای همیشه
  بلاک شه → `umount -l /sys/kernel/debug` قبل از zip.

---

## 3) کرنل + روت (KernelSU) — پراهمیت‌ترین بخش

### انتخاب پیاده‌سازی روت (درس گران‌قیمت)
برای کرنل **non-GKI قدیمی (4.9)**:
- **KernelSU-Next شاخه‌ی `legacy`** → **این جواب می‌ده.** از `v3.4.0-legacy` استفاده
  کن (یا جدیدترین tag ی که `-legacy` داره). hook: **KPROBES** (نه syscall-table).
- **rsuntk/rksu (`susfs-rksu-master`)** → روی Samsung 4.9 **sepolicy موقع بوت خرابه**:
  init نمی‌تونه `/data/adb/ksud` رو exec کنه، su دامنه‌اش permissive نمی‌شه، ماژول‌ها
  موقع بوت بالا نمیان. ساعت‌ها دیباگ کردیم؛ policydb درست بود، AVC flush می‌شد،
  `CONFIG_ALWAYS_ENFORCE` خاموش بود، ولی باز permissive honored نمی‌شد (یه quirk
  عمیق Samsung SELinux porting). **درس: روی Samsung 4.9 از KernelSU-Next legacy برو،
  نه rksu.**
- **Manager و کرنل باید هم‌نسخه باشن** (مثل هر دو 33294). اگه manager جلوتر باشه،
  «kernel version too low» می‌ده و تب‌های Superuser/Modules رو مخفی می‌کنه.
- hook‌های موجود بسته به نسخه‌ی کرنل:
  - `KSU_SYSCALL_TABLE_HOOK` → فقط **کرنل ≥ 4.17** (ABI جدید pt_regs). روی 4.9 خطای
    کامپایل می‌ده.
  - `KSU_KPROBES_HOOK` → روی 4.9 کار می‌کنه (arm64 خودش `HAVE_SYSCALL_TRACEPOINTS`
    رو select می‌کنه؛ فقط `CONFIG_KPROBES=y` لازمه).
  - `KSU_MANUAL_HOOK` → آخرین راه (دستی ksu_handle_* رو به fs/*.c اضافه کن).

### فیکس‌های سازگاری 4.9 برای KernelSU-Next (چون کد برای کرنل جدید نوشته شده)
هر بار `mka bootimage` بزن، خطای بعدی رو بخون، فیکس کن:
- همه‌ی `#include <linux/sched/<x>.h>` → `#include <linux/sched.h>`
- `#include <linux/compiler_types.h>` → `#include <linux/compiler.h>`
- `kvmalloc` ندار → `#include "compat/kernel_compat.h"` اضافه کن
- `kernel_read/write` با امضای قدیمی → wrapperهای `ksu_kernel_*_compat`
- **legacy HEAD خطرناکه:** ممکنه کد SELinux جدید (selinux_state، flask.h) داشته باشه
  که روی 4.9 نیست. از **tag پایدار** `-legacy` بیلد کن، نه شاخه‌ی HEAD.

### بیلد کرنل روی GitHub Actions (برای کرنل‌تنها کافیه، برعکس رام کامل)
الگوی workflow ما:
```
git clone --depth=1 -b <kernel_branch> <kernel_repo> kernel
curl .../KernelSU-Next/<tag>/kernel/setup.sh | bash -s <tag>
# defconfig: CONFIG_KPROBES=y + CONFIG_KSU=y + CONFIG_KSU_KPROBES_HOOK=y
make O=out ARCH=arm64 <defconfig> ; make O=out olddefconfig ; make O=out Image
# Image جدید را در boot.img پایه (رام) repack کن
python samsung_bootimg.py repack base-boot.img out/.../Image boot.img
```
- **KSU_VERSION_OVERRIDE** رو برابر versionCode مَنیجر بذار (تا gate نسخه راضی شه).
- بعد از defconfig **حتماً verify کن** config مورد نظر `=y` شده (olddefconfig ممکنه
  بندازدش اگه وابستگی نباشه — مثال BBR که `CONFIG_TCP_CONG_ADVANCED` می‌خواست).

---

## 4) ریکاوری (TWRP) — فرمت Samsung خاصه
- Samsung boot/recovery = هدر `ANDROID!` + یه **DTBH** چسبیده ته‌ش. آفست‌های مهم:
  dt_size در 40، os_version در 44.
- **SBL سقف ۱۶MiB برای ramdisk داره** و ۸ بایت آخر رو برای boot-command رزرو می‌کنه:
  - ramdisk رو با **LZMA** فشرده کن (نه gzip) تا زیر ۱۶MiB بمونه.
  - ۸ بایت padding به ته ramdisk gzip‌شده اضافه کن وگرنه CRC می‌شکنه → VFS mount fail.
- recovery رو با **Odin (اسلات AP، Auto Reboot خاموش)** فلش کن، یا از TWRP با
  `dd of=/dev/block/by-name/RECOVERY`.
- **درس FBE:** ریکاوری که برای دیکریپت یه رام (مثلاً PE13) ساخته شده، روی رام دیگه
  (LOS) روی لوگو هنگ می‌کنه چون منتظر keymaster برای کلیدهای اون رامه. برای هر رام
  ریکاوری سازگار خودش. برای کار عادی (sideload/backup) TWRP رسمی کافیه.

---

## 5) Integrity / اپ‌های بانکی (Play Integrity) — مفصل‌ترین دردسر

### تشخیص اینکه چرا یه اپ باز نمی‌شه
- اپ **بدون crash خودش رو می‌کشه** (SIG 9 از thread خودش، بدون tombstone) → یه
  RASP/anti-tamper است، نه باگ.
- لحظه‌ی بسته‌شدن، logcat رو ببین: اگه `DroidGuard` / `play.integrity.api` /
  `ExpressIntegrity` صدا زده شد → اپ روی **Play Integrity** قفل می‌کنه.
- یه مکث ~۱۰ ثانیه‌ای قبل از مرگ = رفت‌وبرگشت DroidGuard با سرور گوگل.
- با **Frida** (به‌صورت on-demand، نه ماژول همیشه‌روشن چون بانکی‌ها frida-server رو
  تشخیص می‌دن) می‌تونی دقیق ببینی چه چکی fail می‌شه.

### استک عبور (روی گوشیِ TEE-خراب / بوت‌لودر unlock)
- **PlayIntegrityFix (PIF)** → spoof کردن fingerprint (Pixel) → BASIC + DEVICE integrity.
  برای خیلی از اپ‌ها همین کافیه (حتی بدون keybox معتبر).
- **TrickyStore / TrickyStoreOSS** → جعل keystore attestation با یه **keybox**.
  `target.txt` رو با پکیج اپ پر کن. `tee_status=teeBroken` یعنی TEE واقعی کار نمی‌کنه
  و با keybox fallback می‌زنه.
- **ReZygisk/ZygiskNext** → موتور Zygisk که PIF بهش تزریق می‌شه (ضروری).
- **mountify** → مخفی کردن mount ماژول‌ها از اپ‌ها.
- **keybox معتبر** (برای STRONG) → keyboxهای سخت‌افزاری که به root گوگل زنجیر می‌شن
  (سریال root گوگل: `f92009e853b6b045`). keyboxهای عمومی سریع revoke می‌شن.
  جایگزین‌های هم‌کار (فقط یکی، نه با هم): **OhMyKeyMint**, **TEESimulator**.
- **propspoof** → propهای خام سامسونگ (userdebug/test-keys/orange/warranty_bit) رو
  به (user/release-keys/green/0) تغییر بده.
- بعد از هر تغییر: `pm clear com.google.android.gms.unstable` تا verdict کش‌شده پاک شه.

### درس بزرگ این بخش
مشکل Wepod/Bale ما **از کرنل یا تشخیص ساده‌ی روت نبود** — از این بود که روی کرنل rksu
ماژول‌ها موقع بوت اجرا نمی‌شدن، پس PIF/TrickyStore فعال نبودن. **سوییچ به کرنل
KernelSU-Next** (که ماژول‌ها رو درست بوت‌استرپ می‌کنه) همه‌چی رو حل کرد، حتی با keybox
نرم‌افزاری. یعنی: **اول مطمئن شو ماژول‌ها موقع بوت واقعاً اجرا می‌شن** (چک: props
اسپوف شده؟ daemonها بالان؟)، بعد برو سراغ keybox.

### keymaster/DAK (ریشه‌ی teeBroken روی Exynos)
سرویس `keymaster@3.0` با کاربر `nobody` اجرا می‌شه و `/efs/DAK` رو نمی‌تونه بخونه →
attestation سخت‌افزاری می‌شکنه. فیکس دائمی = پچ .rc سرویس keymaster در بیلد رام.
فیکس موقت (runtime) = bind-mount با دسترسی درست (با ریبوت پاک می‌شه).

---

## 6) تیونینگ performance

### zRAM (حافظه) — از مکانیزم خود رام استفاده کن، نه ماژول swapoff
- اندازه‌ی zRAM معمولاً توی **vendor fstab** هاردکد شده:
  `/dev/block/zram0 none swap defaults zramsize=<bytes>,max_comp_streams=8`
- اگه vendor ext4 + بدون verity باشه → **بدون بیلد** قابل‌ویرایش:
  `mount -o remount,rw /vendor` → عدد zramsize رو عوض کن (با cat redirect، نه sed -i
  که روی toybox temp file نمی‌سازه) → `mount -o remount,ro /vendor` → ریبوت.
- ۴ گیگ برای گوشی ۶ گیگی خوبه (با zstd). اول **بکاپ fstab** بگیر، بعد diff کن که فقط
  همون یه خط عوض شده (وگرنه bootloop).
- ❌ **یه ماژول KSU که post-fs-data swapoff/reset/resize/swapon می‌کنه با swapon_all
  خود رام تداخل می‌کنه و swap رو صفر می‌کنه.** از fstab برو.

### VM / IO / Network (با یه ماژول KSU، مرحله‌ی دیر بوت تا با رام تداخل نکنه)
- سودمند و امن: `vfs_cache_pressure=80`, `page-cluster=0`, `read_ahead_kb=256`,
  `tcp_fastopen=3`, `tcp_slow_start_after_idle=0`.
- دست نزن (ریسک/بی‌فایده): CPU governor (اگه `schedutil` ـه، خودش بهترینه)، LMK
  (ریسک OOM)، swappiness بالای ۱۰۰ (اندروید `/proc/sys/vm/swappiness` رو با SELinux
  `proc_swappiness` قفل کرده؛ فقط init می‌تونه بنویسه — حتی روت هم نه؛ و ۱۰۰ همون
  بهینه‌ست).

### BBR (شبکه‌ی بهتر، مخصوصاً VPN/موبایل پرنوسان)
- BBR روی کرنل 4.9 **موجوده** (`net/ipv4/tcp_bbr.c` + `net/sched/sch_fq.c`).
- در defconfig: `CONFIG_TCP_CONG_ADVANCED=y` (**لازم وگرنه BBR بعد olddefconfig می‌افتد**)
  + `CONFIG_TCP_CONG_BBR=y` + `CONFIG_NET_SCH_FQ=y` + `CONFIG_DEFAULT_BBR=y` +
  `CONFIG_DEFAULT_FQ=y`.
- در runtime (ماژول): `net.core.default_qdisc=fq` (BBR با fq بهترین pacing رو می‌ده)
  + `net.ipv4.tcp_congestion_control=bbr`.
- **اثبات فعال بودن:** `ss -ti | grep -c bbr` (تعداد سوکت‌هایی که BBR استفاده می‌کنن).

---

## 7) بکاپ و امنیت (قبل از هر کار مخرب)
- **دیتای شخصی:** عکس (بدون ویدیو)، SMS (xml فرمت SMS Backup&Restore + csv)،
  مخاطبین (vcf)، لاگ تماس (xml/csv)، دیتای اپ‌ها (tar)، دیتابیس خام
  (contacts2.db/mmssms.db/calllog.db). + SHA256SUMS + README-restore.
- **بکاپ پارتیشن‌ها** قبل از فلش رام جدید (BOOT/SYSTEM/VENDOR/... با dd) برای برگشت کامل.
- **کلید/توکن هیچ‌وقت توی repo** (حتی خصوصی). اگه لازم شد منتقل بشه، AES-256 رمزدار.
- بکاپ‌ها رو روی **دو جا** نگه دار (دیسک داخلی خراب می‌شه).

---

## 8) چک‌لیست سریع برای گوشی جدید
1. [ ] شناخت دستگاه (codename, کرنل, A/B, vendor fs)
2. [ ] بکاپ دیتای شخصی + بکاپ پارتیشن‌های رام فعلی
3. [ ] بوت‌لودر unlock (⚠️ دیتا پاک می‌شه، Knox می‌سوزه روی سامسونگ)
4. [ ] TWRP/ریکاوری سازگار
5. [ ] رام (LOS آماده یا بیلد روی VPS ابری)
6. [ ] کرنل + روت (KernelSU-Next legacy، hook مناسب نسخه‌ی کرنل)
7. [ ] Manager هم‌نسخه‌ی کرنل
8. [ ] integrity (PIF + ReZygisk + TrickyStore + keybox + propspoof) → تست بانکی‌ها
9. [ ] تیونینگ (zRAM via fstab, VM/IO/BBR via module)
10. [ ] ثبت همه‌چی توی یه manoto.md جدید برای اون دستگاه

---

## 9) ابزارها و منابع که استفاده کردیم
- بیلد ابری: **Hetzner Cloud** (ساعتی)، GitHub Actions (فقط کرنل)
- روت: **KernelSU-Next** (github.com/KernelSU-Next/KernelSU-Next, شاخه legacy)
- integrity: PlayIntegrityFix, TrickyStoreOSS (github.com/beakthoven), ReZygisk,
  mountify؛ keybox/راهنما از کانال‌های تخصصی (مثل t.me/yuriiroot — فایل عمومی،
  با احتیاط و اعتبارسنجی)
- تشخیص: VD Google (github.com/VD171/VD-Google)، integrity checker، Frida (on-demand)
- مدیریت: **App Manager** (MuntashirAkon)، **SmartPack Kernel Manager**
- فرمت Samsung boot: `samsung_bootimg.py` (در همین repo، tools/)
