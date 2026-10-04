#!/usr/bin/env bash
# star2lte ROM build recipe — runs ON the Crave build node (invoked by
# .github/workflows/crave-rom.yml via `crave run`). Keep it self-contained:
# the node starts from the LOS 22 base snapshot and this script does the rest.
set -eo pipefail

DEVICE="star2lte"
BUILD_TYPE="${BUILD_TYPE:-user}"
MANIFEST_URL="https://raw.githubusercontent.com/Skyshadow2022/star2lte-los22/main/.repo-local-manifests/star2lte.xml"

echo "=================================================================="
echo " star2lte build on Crave  | variant: ${BUILD_TYPE}  | $(date -u)"
echo "=================================================================="

# --- source: real LineageOS 22.2 (matches build #2; accupara mirror only has 22.1) ---
rm -rf .repo/local_manifests || true
repo init -u https://github.com/LineageOS/android.git -b lineage-22.2 --git-lfs --depth=1
mkdir -p .repo/local_manifests
curl -fsSL -o .repo/local_manifests/star2lte.xml "${MANIFEST_URL}"
echo "----- local manifest -----"; cat .repo/local_manifests/star2lte.xml; echo "--------------------------"

# --- sync (prefer crave's mirror-accelerated resync; fall back to plain repo sync) ---
if [ -x /opt/crave/resync.sh ]; then
  /opt/crave/resync.sh || repo sync -c -j"$(nproc)" --force-sync --no-clone-bundle --no-tags
else
  repo sync -c -j"$(nproc)" --force-sync --no-clone-bundle --no-tags
fi
test -d device/samsung/${DEVICE} || { echo "::error:: device tree missing after sync"; exit 1; }

# --- camera fix: HWJPEG_ANDROID_VERSION=10 (device-verified, manoto UPDATE 13) ---
# The proprietary libexynoscamera3 blob is from Android 10. At the default 13,
# libhwjpeg's exif_attribute_t has model[64]+offset_time (gated >=12/>=11) while
# the blob fills the OLD layout (model[32], no offset_time); WriteAPP1 then reads
# past the blob's struct at the OffsetTime tags -> strlen(garbage) -> SIGSEGV on
# every capture. Version 10 keeps the blob-required 1-arg ctor (>=10) AND matches
# the struct layout (<11, <12). Clean root-cause fix (no libhwjpeg source patch).
DMK="device/samsung/${DEVICE}/device.mk"
if ! grep -q 'HWJPEG_ANDROID_VERSION,10' "${DMK}" 2>/dev/null; then
  printf '\n# star2lte camera fix: match the Android-10 libexynoscamera3 blob\n$(call soong_config_set,libhwjpeg,HWJPEG_ANDROID_VERSION,10)\n' >> "${DMK}"
  echo "camera fix appended to ${DMK}"
fi

# --- build ---
export BUILD_USERNAME="skyshadow"
export BUILD_HOSTNAME="crave"
source build/envsetup.sh
breakfast lineage_${DEVICE} "${BUILD_TYPE}"
make installclean
mka bacon

# --- expose the artifact under a fixed name for `crave pull` ---
mkdir -p out/artifacts
zip="$(ls -t out/target/product/${DEVICE}/lineage-*.zip 2>/dev/null | head -1)"
test -n "${zip}" || { echo "::error:: no ROM zip produced"; exit 1; }
cp "${zip}" "out/artifacts/$(basename "${zip}")"
# keep a stable name too so the workflow can pull a known path
cp "${zip}" "out/artifacts/star2lte-latest.zip"
sha256sum out/artifacts/*.zip | tee out/artifacts/SHA256SUMS
ls -lh out/artifacts/
echo "=== BUILD COMPLETE ==="
