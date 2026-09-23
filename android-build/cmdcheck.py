#!/usr/bin/env python3
"""Cross-check bytecode command handlers against the asm macros that encode
them. For each opcode: operand layout from the macro (sizes on 32- and 64-bit,
ptr_stream = 4/8), handler from the C dispatch table. Flags a handler that
  - advances by a literal equal to the 32-bit length when the 64-bit length
    differs (it will land mid-operand on 64-bit), or
  - reads a 32-bit value (T1/T2_READ_32) at an offset where the macro puts a
    pointer (truncation), or
  - reads any literal offset at or past the first pointer operand."""
import re, sys
macro_file, c_file, table_name, ip = sys.argv[1:5]
asm = open(macro_file).read()
src = open(c_file).read()
SZ = {'.byte':(1,1), '.2byte':(2,2), '.short':(2,2), '.hword':(2,2), '.4byte':(4,4), '.word':(4,4), '.int':(4,4), 'ptr_stream':(4,8)}
macros = {}
for m in re.finditer(r'\.macro\s+(\w+)[^\n]*\n(.*?)\.endm', asm, re.S):
    name, body = m.group(1), m.group(2)
    lines = [l.split('/*')[0].split('@')[0].strip() for l in body.split('\n')]
    lines = [l for l in lines if l]
    if not lines or not lines[0].startswith('.byte'): continue
    op = lines[0].split(None,1)[1].strip()
    try: op = int(op, 0)
    except ValueError: continue
    ops = []; ok = True
    for l in lines[1:]:
        d = l.split()[0]
        if d in SZ:
            n = max(1, l.count(',') + 1) if d != 'ptr_stream' else 1
            ops += [d] * n
        else:
            ok = False
    macros.setdefault(op, (name, ops, ok))
# dispatch table
t = re.search(re.escape(table_name) + r"[^=]*=\s*\{(.*?)\};", src, re.S)
funcs = [f.strip() for f in re.sub(r'//[^\n]*|/\*.*?\*/', '', t.group(1), flags=re.S).split(',') if f.strip()]
funcs = [re.sub(r'\[.*?\]\s*=\s*', '', f) for f in funcs]
def body_of(fn):
    m = re.search(r'\n(?:static\s+)?(?:void|bool8|u8)\s+' + re.escape(fn) + r'\s*\((?:void|struct ScriptContext \*ctx)?\)\s*\{', src)
    if not m: return None
    i = m.end(); d = 1
    while d: 
        d += {'{':1,'}':-1}.get(src[i],0); i += 1
    return src[m.end():i]
bad = 0
for op, fn in enumerate(funcs):
    if op not in macros: continue
    name, ops, ok = macros[op]
    if 'ptr_stream' not in ops: continue
    offs32 = []; o32 = 1; o64 = 1; pos = []
    for d in ops:
        pos.append((d, o32, o64)); o32 += SZ[d][0]; o64 += SZ[d][1]
    len32, len64 = o32, o64
    first_ptr = next(o for d,o,_ in pos if d == 'ptr_stream')
    ptr_offs32 = {o for d,o,_ in pos if d == 'ptr_stream'}
    b = body_of(fn)
    if b is None: continue
    probs = []
    for u in re.finditer(re.escape(ip) + r'\s*\+=\s*(\d+)\s*;', b):
        if int(u.group(1)) == len32 and len32 != len64:
            probs.append('advances += %s (32-bit length; 64-bit is %d)' % (u.group(1), len64))
    for u in re.finditer(r'T[12]_READ_32\s*\(\s*' + re.escape(ip) + r'\s*\+\s*(\d+)\s*\)', b):
        if int(u.group(1)) in ptr_offs32:
            probs.append('reads a pointer operand at +%s with a 32-bit read' % u.group(1))
    for u in re.finditer(re.escape(ip) + r'\s*(?:\[\s*(\d+)\s*\]|\+\s*(\d+)\b)', b):
        n = int(u.group(1) or u.group(2))
        tail = b[u.end():u.end()+3]
        if n > first_ptr and 'sizeof' not in b[u.start():u.end()+30] and not tail.lstrip().startswith('*'):
            probs.append('literal offset %d past the pointer at %d' % (n, first_ptr))
    if probs:
        bad += 1
        print('op 0x%02x %s -> %s  (len %d/%d)%s' % (op, name, fn, len32, len64, '' if ok else ' [macro partly unparsed]'))
        for p in sorted(set(probs)): print('    ' + p)
checked = sum(1 for op, fn in enumerate(funcs) if op in macros and 'ptr_stream' in macros[op][1])
print('%s: %d of %d pointer-carrying handlers flagged (%d opcodes in table, %d macros)' % (c_file, bad, checked, len(funcs), len(macros)))
