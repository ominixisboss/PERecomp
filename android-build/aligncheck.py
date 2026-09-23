#!/usr/bin/env python3
"""Find data tables that C reads as pointer-holding structs but that start
misaligned. `ptr` pads to 8 relative to the absolute position, so a table whose
label is 4 bytes off gets every entry laid out 4 bytes short of the C struct.
Byte streams (scripts) use ptr_stream and leave unaligned relocations; those are
read byte-wise and are fine, so only symbols whose pointer relocations are all
8-aligned are checked."""
import subprocess, sys, collections
bad = []
for obj in sys.argv[1:]:
    syms = collections.defaultdict(list)
    out = subprocess.run(['objdump', '-t', obj], capture_output=True, text=True).stdout
    for l in out.splitlines():
        p = l.split()
        if len(p) >= 5 and p[-3] not in ('*ABS*', '*UND*', '.text') and not p[-3].startswith('.debug'):
            try: addr = int(p[0], 16)
            except ValueError: continue
            sec = p[-3]
            if p[-1].startswith('.L'): continue
            syms[sec].append((addr, p[-1]))
    relocs = collections.defaultdict(list)
    sec = None
    for l in subprocess.run(['objdump', '-r', obj], capture_output=True, text=True).stdout.splitlines():
        if l.startswith('RELOCATION RECORDS FOR ['):
            sec = l[len('RELOCATION RECORDS FOR ['):-2]
        elif sec and 'R_X86_64_64' in l:
            relocs[sec].append(int(l.split()[0], 16))
    for sec, lst in syms.items():
        lst.sort()
        rs = sorted(relocs.get(sec, []))
        for i, (a, name) in enumerate(lst):
            end = lst[i + 1][0] if i + 1 < len(lst) else 1 << 62
            inside = [r for r in rs if a <= r < end]
            if not inside: continue
            if all(r % 8 == 0 for r in inside) and a % 8 != 0:
                bad.append((obj, name, a, len(inside)))
for obj, name, a, n in bad:
    print('%s: %s at +0x%x (%d aligned pointers inside)' % (obj.split('/')[-1], name, a, n))
print('MISALIGNED POINTER TABLES: %d' % len(bad))
