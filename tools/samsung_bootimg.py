#!/usr/bin/env python3
"""Unpack / replace-kernel for the star2lte Samsung boot.img.

Layout (hardware/samsung/mkbootimg, header v1 page 2048):
  header page | kernel | ramdisk | second | dt   (each padded to page size)
  + trailing bytes (SEANDROIDENFORCE footer etc.) kept verbatim.
Samsung stores the DT (dtbh) size at offset 40, where AOSP v1 has
header_version. The SHA1 id at offset 576 is recomputed the same way
mkbootimg does (every section followed by its size).

  samsung_bootimg.py info    boot.img
  samsung_bootimg.py extract boot.img outdir
  samsung_bootimg.py repack  boot.img new_kernel_Image out.img
"""
import hashlib
import os
import struct
import sys

MAGIC = b"ANDROID!"


def _pad(n, page):
    return (page - n % page) % page


def parse(data):
    if data[:8] != MAGIC:
        sys.exit("not an Android boot image")
    (kernel_size, kernel_addr, ramdisk_size, ramdisk_addr, second_size,
     second_addr, tags_addr, page_size, dt_size, os_version) = struct.unpack_from("<10I", data, 8)
    sections = {}
    off = page_size
    for name, size in (("kernel", kernel_size), ("ramdisk", ramdisk_size),
                       ("second", second_size), ("dt", dt_size)):
        sections[name] = (off, size)
        off += size + _pad(size, page_size)
    return {
        "page_size": page_size, "os_version": os_version, "sections": sections,
        "end": off, "id": data[576:608],
    }


def compute_id(parts):
    sha = hashlib.sha1()
    for blob in parts:
        sha.update(blob)
        sha.update(struct.pack("<I", len(blob)))
    return sha.digest()


def blobs(data, info):
    return {k: data[o:o + s] for k, (o, s) in info["sections"].items()}


def cmd_info(path):
    data = open(path, "rb").read()
    info = parse(data)
    b = blobs(data, info)
    print(f"page_size={info['page_size']} os_version=0x{info['os_version']:08x}")
    for k, (o, s) in info["sections"].items():
        print(f"{k:8s} offset={o:9d} size={s:9d}")
    print(f"sections end={info['end']} file={len(data)} trailer={len(data) - info['end']}")
    stored = info["id"][:20]
    with_dt = compute_id([b["kernel"], b["ramdisk"], b["second"], b["dt"]])
    no_dt = compute_id([b["kernel"], b["ramdisk"], b["second"]])
    print("id matches:", "with-dt" if stored == with_dt else "no-dt" if stored == no_dt else "NONE")


def cmd_extract(path, outdir):
    data = open(path, "rb").read()
    info = parse(data)
    os.makedirs(outdir, exist_ok=True)
    for k, blob in blobs(data, info).items():
        if blob:
            open(os.path.join(outdir, k), "wb").write(blob)


def cmd_repack(path, kernel_path, out):
    data = open(path, "rb").read()
    info = parse(data)
    page = info["page_size"]
    b = blobs(data, info)
    stored = info["id"][:20]
    use_dt = stored == compute_id([b["kernel"], b["ramdisk"], b["second"], b["dt"]])
    if not use_dt and stored != compute_id([b["kernel"], b["ramdisk"], b["second"]]):
        sys.exit("cannot reproduce the original id; refusing to repack")
    b["kernel"] = open(kernel_path, "rb").read()

    header = bytearray(data[:page])
    struct.pack_into("<I", header, 8, len(b["kernel"]))
    parts = [b["kernel"], b["ramdisk"], b["second"]] + ([b["dt"]] if use_dt else [])
    header[576:608] = compute_id(parts).ljust(32, b"\0")

    body = bytearray(header)
    for k in ("kernel", "ramdisk", "second", "dt"):
        body += b[k] + b"\0" * _pad(len(b[k]), page)
    body += data[info["end"]:]  # SEANDROIDENFORCE trailer, verbatim
    open(out, "wb").write(body)
    print(f"wrote {out} ({len(body)} bytes), kernel {len(b['kernel'])} bytes")


if __name__ == "__main__":
    cmds = {"info": (cmd_info, 1), "extract": (cmd_extract, 2), "repack": (cmd_repack, 3)}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds or len(sys.argv) - 2 != cmds[sys.argv[1]][1]:
        sys.exit(__doc__)
    cmds[sys.argv[1]][0](*sys.argv[2:])
