#!/usr/bin/env python3
"""Scan SukiSU source for missing linux/ and asm/ headers, create stubs."""
import os, re, glob, sys

kernelsu_dir = "drivers/kernelsu"
if not os.path.isdir(kernelsu_dir):
    # Try symlink target
    if os.path.islink(kernelsu_dir):
        kernelsu_dir = os.path.realpath(kernelsu_dir)

stubs = []
for fp in glob.glob(os.path.join(kernelsu_dir, "**/*.c"), recursive=True) + \
        glob.glob(os.path.join(kernelsu_dir, "**/*.h"), recursive=True):
    try:
        content = open(fp).read()
    except:
        continue
    for m in re.finditer(r'#include\s+<(linux/[^>]+)>', content):
        hdr = m.group(1)
        tgt = os.path.join("include", hdr)
        if not os.path.exists(tgt):
            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            n = hdr.replace("/", "_").replace(".", "_")
            open(tgt, "w").write("/* Stub 4.9 */\n#ifndef _%s_STUB\n#define _%s_STUB\n#endif\n" % (n, n))
            stubs.append(tgt)
    for m in re.finditer(r'#include\s+<(asm/[^>]+)>', content):
        hdr = m.group(1)
        tgt = os.path.join("arch/arm64/include", hdr)
        if not os.path.exists(tgt) and not os.path.exists(os.path.join("include", hdr)):
            os.makedirs(os.path.dirname(tgt), exist_ok=True)
            n = hdr.replace("/", "_").replace(".", "_")
            open(tgt, "w").write("/* Stub 4.9 */\n#ifndef _%s_STUB\n#define _%s_STUB\n#endif\n" % (n, n))
            stubs.append(tgt)

for s in sorted(set(stubs)):
    print("  Created: " + s)
print("Total stubs: %d" % len(set(stubs)))
