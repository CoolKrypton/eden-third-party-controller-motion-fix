#!/usr/bin/env python3
"""Recursively walk the PE import table of a Windows executable and report the
first dependency that cannot be resolved with the standard loader search order."""
import os
import struct
import sys


def sections(f):
    f.seek(0x3C)
    pe = struct.unpack('<I', f.read(4))[0]
    f.seek(pe + 6)
    nsect, = struct.unpack('<H', f.read(2))
    f.seek(pe + 20)
    size_opt, = struct.unpack('<H', f.read(2))
    opt = pe + 24
    f.seek(opt)
    magic, = struct.unpack('<H', f.read(2))
    is64 = magic == 0x20B
    dd = opt + (112 if is64 else 96)
    f.seek(dd + 8)
    imp_rva, imp_size = struct.unpack('<II', f.read(8))
    sect_off = opt + size_opt
    f.seek(sect_off)
    secs = []
    for _ in range(nsect):
        data = f.read(40)
        name = data[:8].rstrip(b'\x00').decode('ascii', 'replace')
        vsize, vaddr, rsize, roff = struct.unpack('<IIII', data[8:24])
        secs.append((vaddr, vsize, roff, rsize))
    return imp_rva, secs


def rva2off(rva, secs):
    for vaddr, vsize, roff, rsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return roff + (rva - vaddr)
    return None


def get_name(f, rva, secs):
    off = rva2off(rva, secs)
    if off is None:
        return None
    f.seek(off)
    out = bytearray()
    while True:
        c = f.read(1)
        if not c or c == b'\x00':
            break
        out += c
    return bytes(out).decode('ascii', 'replace')


def imports(path):
    try:
        with open(path, 'rb') as f:
            imp_rva, secs = sections(f)
            if not imp_rva:
                return []
            off = rva2off(imp_rva, secs)
            if off is None:
                return []
            f.seek(off)
            out = []
            while True:
                desc = f.read(20)
                if len(desc) < 20:
                    break
                name_rva = struct.unpack('<I', desc[12:16])[0]
                if name_rva == 0:
                    break
                n = get_name(f, name_rva, secs)
                if n:
                    out.append(n)
            return out
    except Exception as exc:  # unreadable / not a PE image
        return ['<%s: %s>' % (os.path.basename(path), exc)]


def resolve(name, appdir):
    search = [appdir, r'C:\Windows\System32', r'C:\Windows',
              r'C:\Windows\System32\Wbem']
    search += [p for p in os.environ.get('PATH', '').split(os.pathsep) if p]
    for d in search:
        cand = os.path.join(d, name)
        if os.path.isfile(cand):
            return cand
    return None


def main():
    target = sys.argv[1]
    appdir = os.path.dirname(os.path.abspath(target))
    seen = {}
    missing = []
    stack = [(target, appdir, [])]
    visited = set()
    while stack:
        path, ad, chain = stack.pop()
        key = os.path.basename(path).lower()
        if key in visited:
            continue
        visited.add(key)
        for dep in imports(path):
            if dep.startswith('<'):
                continue
            resolved = resolve(dep, ad)
            if resolved is None:
                missing.append((dep, chain + [os.path.basename(path)]))
            else:
                stack.append((resolved, os.path.dirname(resolved),
                              chain + [os.path.basename(path)]))
        seen[key] = True
    print('目标: %s' % target)
    print('已解析依赖数: %d' % len(visited))
    if missing:
        print('\n无法解析的依赖:')
        for dep, chain in missing:
            print('  %s   <- 引用链: %s' % (dep, ' -> '.join(chain)))
    else:
        print('\n所有依赖均可在搜索路径中找到（未检查嵌套失败）')


if __name__ == '__main__':
    main()
