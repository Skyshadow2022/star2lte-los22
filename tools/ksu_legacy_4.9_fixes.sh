#!/bin/sh
# 4.9 compat fixes for KernelSU-Next (legacy branch) sources.
# Run from KernelSU-Next/kernel. Same fixes that got build #2 compiling,
# re-derived for v3.4.0-legacy (see manoto.md, Build #2 section B).
set -eu

# Split sched headers arrived in 4.11, compiler_types.h in 4.13; on 4.9 the
# content lives in sched.h / compiler.h.
grep -rlE '#include <linux/sched/[a-z_]+\.h>' . | xargs -r sed -i -E 's@#include <linux/sched/[a-z_]+\.h>@#include <linux/sched.h>@'
grep -rl '#include <linux/compiler_types.h>' . | xargs -r sed -i 's@#include <linux/compiler_types.h>@#include <linux/compiler.h>@'

# 4.9 has the old kernel_read/kernel_write signatures. KernelSU-Next ships
# wrappers with the modern signature in compat/kernel_compat.h (they also
# provide kvmalloc for <4.12), but some files call the raw functions.
for f in $(grep -rlE '(^|[^_a-z])kernel_(read|write)\(' --include=*.c . | grep -v '^\./compat/'); do
	sed -i -E 's/(^|[^_a-z])kernel_(read|write)\(/\1ksu_kernel_\2_compat(/g' "$f"
done
for f in $(grep -rlE 'ksu_kernel_(read|write)_compat\(|\bkv(malloc|zalloc|free)\(' --include=*.c . | grep -v '^\./compat/'); do
	grep -q '"compat/kernel_compat.h"' "$f" || sed -i '0,/^#include /s@^#include @#include "compat/kernel_compat.h"\n#include @' "$f"
done

# Fail loudly if anything is left for the compiler to trip on.
left=$(grep -rnE '#include <linux/(sched/[a-z_]+|compiler_types)\.h>|(^|[^_a-z])kernel_(read|write)\(' --include=*.[ch] . | grep -v '^\./compat/' | grep -vE '^[^:]+:[0-9]+:\s*(//|\*)' || true)
[ -z "$left" ] || { echo "unfixed:"; echo "$left"; exit 1; }
echo "4.9 fixes applied"
