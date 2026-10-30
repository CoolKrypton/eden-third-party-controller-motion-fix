#!/usr/bin/env python3
"""Compare a PE image's imported symbols against the export tables of the DLLs
that the Windows loader would actually pick, and report missing symbols.

Used to diagnose STATUS_ENTRYPOINT_NOT_FOUND (0xC0000139) at process startup.
"""
import os
import struct
import sys


def read_headers(data):
    pe = struct.unpack_from('<I', data, 0x3C)[0]
    nsect, = struct.unpack_from('<H', data, pe + 6)
    size_opt, = struct.unpack_from('<H', data, pe + 20)
    opt = pe + 24
    magic, = struct.unpack_from('<H', data, opt)
    is64 = magic == 0x20B
    dd = opt + (112 if is64 else 96)
    exp_rva, exp_size = struct.unpack_from('<II', data, dd)
    imp_rva, = struct.unpack_from('<I', data, dd + 8)
    sect_off = opt + size_opt
    secs = []
    for i in range(nsect):
        o = sect_off + 40 * i
        vsize, vaddr, rsize, roff = struct.unpack_from('<IIII', data, o + 8)
        secs.append((vaddr, vsize, roff, rsize))
    return imp_rva, exp_rva, exp_size, secs, is64


def r2o(rva, secs):
    for vaddr, vsize, roff, rsize in secs:
        if vaddr <= rva < vaddr + max(vsize, rsize):
            return roff + (rva - vaddr)
    return None


def cstr(data, off):
    if off is None:
        return ''
    end = data.index(b'\x00', off)
    return bytes(data[off:end]).decode('ascii', 'replace')


def imports(data):
    imp_rva, _, _, secs, is64 = read_headers(data)
    out = []
    off = r2o(imp_rva, secs)
    if off is None:
        return out
    while True:
        d = data[off:off + 20]
        if len(d) < 20:
            break
        oft, = struct.unpack_from('<I', d, 0)
        name_rva, = struct.unpack_from('<I', d, 12)
        first, = struct.unpack_from('<I', d, 16)
        if name_rva == 0:
            break
        dll = cstr(data, r2o(name_rva, secs))
        thunk = oft if oft else first
        names = []
        t = r2o(thunk, secs)
        if t is not None:
            step = 8 if is64 else 4
            fmt = '<Q' if is64 else '<I'
            while True:
                v = struct.unpack_from(fmt, data, t)[0]
                if v == 0:
                    break
                ordinal_base = 0x8000000000000000 if is64 else 0x80000000
                if v & ordinal_base:
                    names.append('ordinal:%d' % (v & 0xFFFF))
                else:
                    names.append(cstr(data, r2o(v, secs)) + 2 if False else cstr(data, r2o(v, secs)))
                t += step
        out.append((dll, names))
        off += 20
    return out


def import_names(data):
    """Return {dll: [imported symbol names]} using the hint/name table."""
    imp_rva, _, _, secs, is64 = read_headers(data)
    out = []
    off = r2o(imp_rva, secs)
    if off is None:
        return out
    while True:
        d = data[off:off + 20]
        if len(d) < 20:
            break
        oft, = struct.unpack_from('<I', d, 0)
        name_rva, = struct.unpack_from('<I', d, 12)
        first, = struct.unpack_from('<I', d, 16)
        if name_rva == 0:
            break
        dll = cstr(data, r2o(name_rva, secs))
        thunk = oft if oft else first
        names = []
        t = r2o(thunk, secs)
        if t is not None:
            step = 8 if is64 else 4
            fmt = '<Q' if is64 else '<I'
            while True:
                v = struct.unpack_from(fmt, data, t)[0]
                if v == 0:
                    break
                ob = (1 << 63) if is64 else (1 << 31)
                if v & ob:
                    names.append('ordinal:%d' % (v & 0xFFFF))
                else:
                    p = r2o(v, secs)
                    names.append(cstr(data, p + 2) if p is not None else '?')
                t += step
        out.append((dll, names))
        off += 20
    return out


def exports(data):
    _, exp_rva, exp_size, secs, _ = read_headers(data)
    if not exp_rva:
        return set(), {}
    off = r2o(exp_rva, secs)
    base, = struct.unpack_from('<I', data, off + 16)
    nfunc, = struct.unpack_from('<I', data, off + 20)
    nname, = struct.unpack_from('<I', data, off + 24)
    addr_rva, = struct.unpack_from('<I', data, off + 28)
    names_rva, = struct.unpack_from('<I', data, off + 32)
    ords_rva, = struct.unpack_from('<I', data, off + 36)
    names = set()
    forwards = {}
    noff = r2o(names_rva, secs)
    ooff = r2o(ords_rva, secs)
    eoff = r2o(addr_rva, secs)
    if None in (noff, ooff, eoff):
        return names, forwards
    for i in range(nname):
        nrva, = struct.unpack_from('<I', data, noff + 4 * i)
        nm = cstr(data, r2o(nrva, secs))
        names.add(nm)
        idx, = struct.unpack_from('<H', data, ooff + 2 * i)
        frva, = struct.unpack_from('<I', data, eoff + 4 * idx)
        if exp_rva <= frva < exp_rva + exp_size:
            f = cstr(data, r2o(frva, secs))
            if '.' in f:
                forwards[nm] = f
    return names, forwards


def resolve(name, appdir):
    search = [appdir, r'C:\Windows\System32', r'C:\Windows']
    search += [p for p in os.environ.get('PATH', '').split(os.pathsep) if p]
    for d in search:
        c = os.path.join(d, name)
        if os.path.isfile(c):
            return c
    return None


def main():
    target = sys.argv[1]
    appdir = os.path.dirname(os.path.abspath(target))
    data = bytearray(open(target, 'rb').read())
    print('目标: %s' % target)
    print('应用目录: %s' % appdir)
    print('-' * 78)
    total_missing = 0
    for dll, names in import_names(data):
        path = resolve(dll, appdir)
        if path is None:
            print('[!] %-40s 无法定位 DLL' % dll)
            continue
        try:
            ddata = bytearray(open(path, 'rb').read())
        except Exception as exc:
            print('[!] %-40s 读取失败: %s' % (dll, exc))
            continue
        exp, fwd = exports(ddata)
        missing = [n for n in names if n not in exp]
        tag = 'OK' if not missing else '缺 %d 个符号' % len(missing)
        print('%-40s %-12s <- %s' % (dll, tag, path))
        if missing:
            total_missing += len(missing)
            for m in missing[:10]:
                f = fwd.get(m)
                print('     缺失: %s%s' % (m, '  (该 DLL 内为转发: %s)' % f if f else ''))
            if len(missing) > 10:
                print('     ... 还有 %d 个' % (len(missing) - 10))
    print('-' * 78)
    print('合计缺失符号: %d' % total_missing)


if __name__ == '__main__':
    main()
