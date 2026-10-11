"""Solo Buddy Bunkers - build.

python build.py <out dir>              the release (Solo-Buddy-Bunkers-<ver>.zip)
python build.py <out dir> --tester     the release's Tester build (research details in the normal log, test GUID)
python build.py <out dir> --test N     numbered test build N (log in Logs\\test, test GUID)
  (add --recorder to a numbered test build whose Lua has its research blocks: presses nothing, records every switch
   change)
  - 9ba626afa44a3aa3.patch_0: the addon (plain Lua, Bingus Shared Loader finds it by its first line)
  - manifest.json, icon.png (the Arsenal icon from artwork/icon.png; test builds draw a simple TEST icon); zip
"""
import json, os, re, shutil, struct, subprocess, sys, zipfile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import patch_writer

VERSION = '1.0.1'
GUID_RELEASE = 'b02e6780-b30d-49a9-9d08-3450a4920466'
GUID_TEST = '24a930a3-0671-405e-ad87-60b6c0628ead'      # Tester and numbered test builds
LUA = 0xa14e8dfa2cd117e2
ADDON = 'mods/chef/solo_buddy_bunkers'
ANTON = os.path.join(HERE, 'fonts', 'anton-latin-400-normal.ttf')
ZIP_DATE = (2026, 10, 1, 0, 0, 0)       # every zip entry's date: the same sources give the same zip, byte for byte
# never in what ships (compared in lower case; a drive letter only at the start of a word, so 'record:\\n' is no hit)
PERSONAL = [re.compile(p) for p in (rb'c:\\+users', rb'(?<![a-z0-9_])d:\\', rb'/home/', rb'/mnt/', rb'steamlibrary')]


def resource_hash(name):
    """The game's 64-bit resource name hash (MurmurHash64A, seed 0)."""
    data = name.encode(); mask, mix = (1 << 64) - 1, 0xC6A4A7935BD1E995
    v = len(data) * mix & mask; end = len(data) // 8 * 8
    for (w,) in struct.iter_unpack('<Q', data[:end]):
        w = w * mix & mask; w ^= w >> 47; v = (v ^ (w * mix & mask)) * mix & mask
    if data[end:]: v = (v ^ int.from_bytes(data[end:], 'little')) * mix & mask
    v ^= v >> 47; v = v * mix & mask; v ^= v >> 47
    return v


assert resource_hash('lua') == LUA


def lua_resource(text):
    b = text.encode('utf-8')
    return struct.pack('<II', len(b), 2) + b


def icon(label):
    """A simple Arsenal icon: a bunker door with two switches, one lit (pressed) and the other pressed for you."""
    S = 1024
    img = Image.new('RGB', (S, S), (22, 24, 22))
    d = ImageDraw.Draw(img)
    # hazard stripes top and bottom
    for y0 in (0, S - 60):
        for x in range(-60, S + 60, 80):
            d.polygon([(x, y0 + 60), (x + 40, y0 + 60), (x + 100, y0), (x + 60, y0)], fill=(255, 231, 16))
    # the bunker door
    d.rounded_rectangle((260, 230, 764, 760), 24, fill=(70, 74, 68), outline=(140, 146, 132), width=10)
    for k in range(5):
        y = 290 + k * 92
        d.rectangle((300, y, 724, y + 40), fill=(58, 62, 56))
    # two switches on posts
    for cx, lit in ((150, True), (874, True)):
        d.rectangle((cx - 40, 520, cx + 40, 760), fill=(52, 56, 52), outline=(120, 126, 114), width=6)
        d.ellipse((cx - 32, 548, cx + 32, 612), fill=(120, 255, 140) if lit else (60, 70, 60))
    # one helldiver (a single figure): head and body
    d.ellipse((470, 790, 554, 874), fill=(255, 231, 16))
    d.rounded_rectangle((452, 870, 572, 980), 30, fill=(255, 231, 16))
    font = ImageFont.truetype(ANTON, 128)
    t = 'SOLO'
    w = d.textlength(t, font=font)
    d.text(((S - w) / 2, 70), t, font=font, fill=(255, 231, 16), stroke_width=6, stroke_fill=(0, 0, 0))
    if label:
        f2 = ImageFont.truetype(ANTON, 90)
        w = d.textlength(label, font=f2)
        d.text(((S - w) / 2, 620), label, font=f2, fill=(255, 80, 60), stroke_width=6, stroke_fill=(0, 0, 0))
    return img.resize((512, 512), Image.LANCZOS)


def clean_out(out):
    """The output folder: never the source folder or one of its parents; only this build's own outputs are removed."""
    real = os.path.realpath(out)
    if real == HERE or HERE.startswith(real.rstrip(os.sep) + os.sep):
        sys.exit('build.py: %s is the source folder or one of its parents; use an output folder of its own' % out)
    os.makedirs(real, exist_ok=True)
    for f in os.listdir(real):
        p = os.path.join(real, f)
        if f == 'pkg' and os.path.isdir(p) and not os.path.islink(p): shutil.rmtree(p)
        elif f == 'addon.built.lua' or (f.startswith('Solo-Buddy-Bunkers-') and f.endswith('.zip')): os.remove(p)


def check_lua(path):
    """The built Lua compiles (luajit -bl), when luajit is on PATH."""
    lj = shutil.which('luajit')
    if not lj:
        print('luajit not on PATH: the compile check was skipped')
        return
    r = subprocess.run([lj, '-bl', path], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    if r.returncode != 0:
        sys.exit('build.py: the built Lua does not compile: ' + r.stderr.decode('utf-8', 'replace').strip())


def check_private(paths):
    """Nothing personal (a user folder, a drive or Steam path) in what ships."""
    for p in paths:
        data = open(p, 'rb').read().lower()
        for k in PERSONAL:
            m = k.search(data)
            if m:
                sys.exit('build.py: %s contains %r (a personal path); remove it before building' % (os.path.basename(p), m.group().decode()))


def main():
    out, args = sys.argv[1], sys.argv[2:]
    tester = '--tester' in args
    recorder = '--recorder' in args
    test = int(args[args.index('--test') + 1]) if '--test' in args else None
    if recorder and not test:
        sys.exit('build.py: --recorder only goes with --test N (recorder builds are numbered test builds)')
    full = VERSION + (' Test %d' % test if test else ' (tester)' if tester else '')
    guid = GUID_TEST if (test or tester) else GUID_RELEASE
    clean_out(out)
    pkg = os.path.join(out, 'pkg'); os.makedirs(pkg)
    src = open(os.path.join(HERE, 'lua', 'solo_buddy_bunkers.lua'), encoding='utf-8').read()
    head = '-- HD2-Addon: %s\n' % ADDON
    if not src.startswith(head):
        sys.exit('build.py: the Lua must start with %r (Bingus Shared Loader finds the addon by it)' % head.strip())
    for a, b in (("local VERSION = '%s'" % VERSION, "local VERSION = '%s'" % full),
                 ('local TESTER = false', 'local TESTER = %s' % ('true' if (test or tester) else 'false')),
                 ('local TEST_BUILD = false', 'local TEST_BUILD = %s' % ('true' if test else 'false'))):
        assert src.count(a) == 1, a
        src = src.replace(a, b)
    research = '-- @research-begin' in src
    if recorder:
        # the recorder is research code: only a Lua with its research blocks has it
        if not research or src.count('local RECORDER = false') != 1:
            sys.exit('build.py: --recorder needs the Lua with its research blocks (this one has no recorder)')
        src = src.replace('local RECORDER = false', 'local RECORDER = true')
    if not test and research:
        # releases and Tester builds leave out the research-only code (the recorder, the probe, the research looks)
        n = len(src.splitlines())
        src, k = re.subn(r'[ \t]*-- @research-begin\n.*?-- @research-end\n', '', src, flags=re.S)
        assert '@research' not in src and 'RECORDER' not in src, k
        print('research code left out: %d blocks, %d lines' % (k, n - len(src.splitlines())))
    built = os.path.join(out, 'addon.built.lua')
    open(built, 'w', encoding='utf-8', newline='\n').write(src)
    check_lua(built)
    toc, gpu, stream = patch_writer.write([(resource_hash(ADDON), LUA, lua_resource(src), b'', b'', 16)], [(LUA, 16)])
    patch_writer.check(toc, gpu, stream)
    base = os.path.join(pkg, '9ba626afa44a3aa3.patch_0')
    open(base, 'wb').write(toc); open(base + '.gpu_resources', 'wb').write(gpu); open(base + '.stream', 'wb').write(stream)
    if test:
        icon('TEST %d' % test).save(os.path.join(pkg, 'icon.png'), optimize=True)
    else:   # the release art, 512x512 (Arsenal shows it small)
        Image.open(os.path.join(HERE, 'artwork', 'icon.png')).convert('RGB').resize((512, 512), Image.LANCZOS).save(
            os.path.join(pkg, 'icon.png'), optimize=True)
    man = {'Version': 1, 'Guid': guid, 'Name': 'Solo Buddy Bunkers ' + full,
           'Description': 'Open two-person (buddy) bunkers by yourself: when you press one of the two switches, the '
                          'other switch of the same bunker is pressed for you. Works solo, when you host, and when you '
                          'join someone else\'s game. Requires Bingus Shared Loader v19 or newer. With Mod Options '
                          'Menu it can be turned on and off in game (SOLO BUDDY BUNKERS section).',
           'IconPath': 'icon.png'}
    open(os.path.join(pkg, 'manifest.json'), 'w', encoding='utf-8', newline='\n').write(json.dumps(man, indent=2))
    check_private([base, base + '.gpu_resources', base + '.stream', os.path.join(pkg, 'manifest.json')])
    z = os.path.join(out, 'Solo-Buddy-Bunkers-%s.zip' % (VERSION + ('-Test-%d' % test if test else '-Tester' if tester else '')))
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(pkg)):
            zi = zipfile.ZipInfo(f, ZIP_DATE)
            zi.compress_type, zi.create_system, zi.external_attr = zipfile.ZIP_DEFLATED, 0, 0o644 << 16
            zf.writestr(zi, open(os.path.join(pkg, f), 'rb').read())
    print(z, os.path.getsize(z))


if __name__ == '__main__':
    main()
