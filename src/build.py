"""Solo Buddy Bunkers - build.

python build.py <out dir>              the release (Solo-Buddy-Bunkers-<ver>.zip)
python build.py <out dir> --tester     the release's Tester build (research details in the normal log, test GUID)
python build.py <out dir> --test N     numbered test build N (log in Logs\\test, test GUID)
  (add --recorder: presses nothing, records every switch change)
  - 9ba626afa44a3aa3.patch_0: the addon (plain Lua, Bingus Shared Loader finds it by its first line)
  - manifest.json, icon.png (the Arsenal icon from artwork/icon.png; test builds draw a simple TEST icon); zip
"""
import json, os, shutil, struct, sys, zipfile
from PIL import Image, ImageDraw, ImageFilter, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import patch_writer

VERSION = '1.0.0'
GUID_RELEASE = 'b02e6780-b30d-49a9-9d08-3450a4920466'
GUID_TEST = '24a930a3-0671-405e-ad87-60b6c0628ead'      # Tester and numbered test builds
LUA = 0xa14e8dfa2cd117e2
ADDON = 'mods/chef/solo_buddy_bunkers'
ANTON = os.path.join(HERE, 'fonts', 'anton-latin-400-normal.ttf')


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


def main():
    out, args = sys.argv[1], sys.argv[2:]
    tester = '--tester' in args
    recorder = '--recorder' in args
    test = int(args[args.index('--test') + 1]) if '--test' in args else None
    full = VERSION + (' Test %d' % test if test else ' (tester)' if tester else '')
    guid = GUID_TEST if (test or tester) else GUID_RELEASE
    if os.path.isdir(out): shutil.rmtree(out)
    pkg = os.path.join(out, 'pkg'); os.makedirs(pkg)
    src = open(os.path.join(HERE, 'lua', 'solo_buddy_bunkers.lua'), encoding='utf-8').read()
    for a, b in (("local VERSION = '1.0.0'", "local VERSION = '%s'" % full),
                 ('local TESTER = false', 'local TESTER = %s' % ('true' if (test or tester) else 'false')),
                 ('local TEST_BUILD = false', 'local TEST_BUILD = %s' % ('true' if test else 'false')),
                 ('local RECORDER = false', 'local RECORDER = %s' % ('true' if recorder else 'false'))):
        assert src.count(a) == 1, a
        src = src.replace(a, b)
    if not test:
        # releases and Tester builds leave out the research-only code (the recorder, the probe, the research looks)
        import re
        n = len(src.splitlines())
        src, k = re.subn(r'[ \t]*-- @research-begin\n.*?-- @research-end\n', '', src, flags=re.S)
        assert '@research' not in src, k
        if k: print('research code left out: %d blocks, %d lines' % (k, n - len(src.splitlines())))
    open(os.path.join(out, 'addon.built.lua'), 'w', encoding='utf-8').write(src)
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
    open(os.path.join(pkg, 'manifest.json'), 'w').write(json.dumps(man, indent=2))
    z = os.path.join(out, 'Solo-Buddy-Bunkers-%s.zip' % (VERSION + ('-Test-%d' % test if test else '-Tester' if tester else '')))
    with zipfile.ZipFile(z, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in sorted(os.listdir(pkg)):
            zf.write(os.path.join(pkg, f), f)
    print(z, os.path.getsize(z))


if __name__ == '__main__':
    main()
