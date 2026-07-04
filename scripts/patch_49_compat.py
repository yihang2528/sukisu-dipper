#!/usr/bin/env python3
"""Patch SukiSU source files for 4.9 kernel compatibility.
Called after stub_headers.py, before kernel build."""
import os, re

def patch_file(path, patches):
    """Apply list of (old, new) replacements to a file."""
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return
    content = open(path).read()
    orig = content
    for old, new in patches:
        if old in content:
            count = content.count(old)
            content = content.replace(old, new)
            print(f"  {path}: replaced '{old[:50]}...' x{count}")
    if content != orig:
        open(path, "w").write(content)

def insert_stubs(path, stubs):
    """Insert stub function implementations at the end of a file."""
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return
    content = open(path).read()
    if "KSU_4_9_STUBS" in content:
        print(f"  {path}: stubs already present")
        return
    content += "\n/* KSU_4_9_STUBS: empty implementations for 4.9 compatibility */\n"
    for stub in stubs:
        content += stub + "\n"
    open(path, "w").write(content)
    print(f"  {path}: added {len(stubs)} stubs")

base = "drivers/kernelsu"

# 1. patch_memory.c - fix page table walk (skip p4d layer)
# In 4.9, arm64 has 3-level page table: pgd->pud->pmd->pte
# No p4d layer. pud_offset takes (pgd, addr) directly.
pm = os.path.join(base, "hook/arm64/patch_memory.c")
patch_file(pm, [
    # Remove p4d variable declaration
    ("    p4d_t *p4d;\n", ""),
    # Remove p4d offset/none/bad/val/debug lines
    ('    p4d = p4d_offset(pgd, addr);\n', ""),
    ('    if (p4d_none(*p4d) || p4d_bad(*p4d))\n        goto fail;\n', ""),
    ('    pr_debug("p4d of 0x%lx p=0x%lx v=0x%lx", addr, (uintptr_t)p4d, (uintptr_t)p4d_val(*p4d));\n', ""),
    # pud_offset(p4d, addr) -> pud_offset(pgd, addr) (4.9 takes pgd directly)
    ("pud = pud_offset(p4d, addr)", "pud = pud_offset(pgd, addr)"),
    # __flush_icache_range -> flush_icache_range (4.9 name)
    ("__flush_icache_range", "flush_icache_range"),
    # caches_clean_inval_pou -> __clean_dcache_area_pou (4.9 name)
    ("caches_clean_inval_pou", "__clean_dcache_area_pou"),
    # dcache_clean_inval_poc -> __clean_dcache_area_poc (4.9 name)
    ("dcache_clean_inval_poc", "__clean_dcache_area_poc"),
    # copy_to_kernel_nofault -> probe_kernel_write (4.9 name)
    ("copy_to_kernel_nofault", "probe_kernel_write"),
    # copy_from_kernel_nofault -> probe_kernel_read (4.9 name)
    ("copy_from_kernel_nofault", "probe_kernel_read"),
])

# 2. set_fixmap_offset and clear_fixmap
# 4.9 has __set_fixmap(idx, phys, prot) but not set_fixmap_offset/clear_fixmap
# set_fixmap_offset returns a kernel virtual address for the fixmap entry
# In 4.9, we can use __fix_to_virt(idx) after __set_fixmap
patch_file(pm, [
    ("set_fixmap_offset(FIX_TEXT_POKE0, phy)", 
     "__set_fixmap(FIX_TEXT_POKE0, phy, FIXMAP_PAGE_TEXT)"),
    ("clear_fixmap(FIX_TEXT_POKE0)",
     "__set_fixmap(FIX_TEXT_POKE0, 0, FIXMAP_PAGE_CLEAR)"),
])
# Also need to fix the map variable - it was void *map = set_fixmap_offset(...)
# Now it needs to be the fixmap virtual address
patch_file(pm, [
    ('void *map = __set_fixmap(FIX_TEXT_POKE0, phy, FIXMAP_PAGE_TEXT);',
     'void *map = (void *)__fix_to_virt(FIX_TEXT_POKE0); __set_fixmap(FIX_TEXT_POKE0, phy, FIXMAP_PAGE_TEXT);'),
])
# If FIXMAP_PAGE_TEXT doesn't exist, use FIXMAP_PAGE_IO or PAGE_KERNEL
patch_file(pm, [
    ("FIXMAP_PAGE_TEXT", "PAGE_KERNEL_EXEC"),
])

# 2. lsm_hook stubs - provide empty implementations
# lsm_hook.c is wrapped with #if 0, so functions need stubs
# Add them to the END of lsm_hook.c (after the #endif)
lsm_c = os.path.join(base, "hook/lsm_hook.c")
if os.path.exists(lsm_c):
    content = open(lsm_c).read()
    if "KSU_4_9_LSM_STUBS" not in content:
        stubs_code = """
/* KSU_4_9_LSM_STUBS: empty implementations (lsm_hook.c disabled for 4.9) */
int ksu_lsm_hook(struct ksu_lsm_hook *hook) { return 0; }
void ksu_lsm_unhook(struct ksu_lsm_hook *hook) {}
int ksu_register_lsm_hook(struct ksu_lsm_hook *hook) { return 0; }
void ksu_unregister_lsm_hook(struct ksu_lsm_hook *hook) {}
int ksu_lsm_hook_init(void) { return 0; }
void ksu_lsm_hook_exit(void) {}
"""
        content += stubs_code
        open(lsm_c, "w").write(content)
        print(f"  {lsm_c}: added lsm_hook stubs after #endif")

# 4. Check for other potential issues
# set_memory.h stub - if SukiSU calls set_memory_* functions, they need real impl
# In 4.9, arm64 has set_memory_* in arch/arm64/mm/mmu.c
sm = os.path.join(base, "hook/patch_memory.h")
if os.path.exists(sm):
    content = open(sm).read()
    if "set_memory" in content and "KSU_SET_MEMORY_STUB" not in content:
        # 4.9 has set_memory_ro/rw/x/nx, should be fine
        pass

print("=== All 4.9 compatibility patches applied ===")
