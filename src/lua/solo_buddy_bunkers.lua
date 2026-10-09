-- HD2-Addon: mods/chef/solo_buddy_bunkers
-- Solo Buddy Bunkers for Helldivers 2 (Bingus Shared Loader v19+ addon).
-- Two-person bunkers have two switches that must be pressed within the game's time window. With this mod, when you
-- press one switch, the other switch of the same bunker is pressed for you:
--   - solo or hosting: through the game's own switch routine (the same effects and the same door signal as a second
--     player pressing it);
--   - joined (someone else hosts): your game sends the host a press of the other switch, through the same game routine
--     your own press goes through.
-- Finds everything it needs in the game's code by itself (no fixed addresses), so a game update doesn't break it;
-- if something can't be found, it stays off and says why in its log.
local VERSION = '1.0.0'
local TESTER = false          -- Tester and numbered test builds: research details in the log
local TEST_BUILD = false      -- numbered test builds only: the log goes to Logs\test
local RECORDER = false        -- recorder test builds: press nothing, record every switch change (record log)

if rawget(_G, 'ChefSoloBuddyBunkers') then return end
local SB = { version = VERSION, status = 'starting' }
rawset(_G, 'ChefSoloBuddyBunkers', SB)

local ffi = require('ffi')
local bit = require('bit')

-- ======================================================================================================
-- Tuning (only needs a look if the game changes how buddy bunkers work)
-- ======================================================================================================
local PAIR_RANGE = 20.0       -- meters: a bunker's two switches are a few meters apart; the other switch is the
                              -- nearest switch of the other side within this distance
local FRESH_US = 1500000      -- a press counts as new for 1.5 s (switches already pressed when we first see them
                              -- are left alone)
local SCAN_EVERY = 120        -- frames between looks for the mission's switches (about 2 s)
local WATCH_EVERY = 4         -- frames between looks at the switches' states

-- ======================================================================================================
-- Windows API (private names, so they never clash with another mod's declarations)
-- ======================================================================================================
for _, d in ipairs({
  'void *SbGetModuleHandleA(const char *name) __asm__("GetModuleHandleA");',
  'void *SbGetCurrentProcess(void) __asm__("GetCurrentProcess");',
  'int SbReadProcessMemory(void *process, const void *address, void *buffer, size_t size, size_t *done) __asm__("ReadProcessMemory");',
  'int SbCreateDirectoryA(const char *path, void *security) __asm__("CreateDirectoryA");',
}) do pcall(ffi.cdef, d) end
local K32 = ffi.load('kernel32')
local PROCESS = K32.SbGetCurrentProcess()

-- ======================================================================================================
-- Log: Logs\SoloBuddyBunkers.log (numbered test builds: Logs\test\SoloBuddyBunkers.log)
-- ======================================================================================================
local LOADER = rawget(_G, 'CowboyBingusModLoader')
local V19 = type(LOADER) == 'table' and type(rawget(LOADER, 'capabilities')) == 'table'
  and type(rawget(LOADER, 'after_startup')) == 'function'
local LOGDIR
do
  local dir = type(LOADER) == 'table' and type(rawget(LOADER, 'log_directory')) == 'string' and LOADER.log_directory or nil
  if not dir then
    local base = os.getenv('LOCALAPPDATA')
    dir = base and (base .. '\\CowboyBingus\\Helldivers2\\Logs') or nil
  end
  if dir and TEST_BUILD then
    pcall(K32.SbCreateDirectoryA, dir .. '\\test', nil)
    local f = io.open(dir .. '\\test\\SoloBuddyBunkers.log', 'a')
    if f then f:close(); dir = dir .. '\\test' end
  end
  LOGDIR = dir
end
if LOGDIR and TEST_BUILD then           -- test builds keep the previous session's log (a crash leaves no other trace)
  pcall(os.remove, LOGDIR .. '\\SoloBuddyBunkers.previous.log')
  pcall(os.rename, LOGDIR .. '\\SoloBuddyBunkers.log', LOGDIR .. '\\SoloBuddyBunkers.previous.log')
end
local session = { started = os.date('%Y-%m-%d %H:%M:%S'), events = {}, notes = {} }
local function event(msg)
  local e = session.events
  e[#e + 1] = os.date('%H:%M:%S ') .. msg
  if #e > 60 then table.remove(e, 1) end
end
local function note(key, msg) session.notes[key] = msg end
local stats = { reads = 0, read_fails = 0, scans = 0, switches = 0, presses = 0, opened_for_you = 0, skipped = 0 }

-- ======================================================================================================
-- Memory: ReadProcessMemory on our own process into one reusable buffer (a bad address fails cleanly)
-- ======================================================================================================
local BUF_SIZE = 65536
local BUF = ffi.new('uint8_t[?]', BUF_SIZE)
local DONE = ffi.new('size_t[1]')
local PVOID = ffi.typeof('const void *')
local PU32, PU64, PF32 = ffi.typeof('const uint32_t *'), ffi.typeof('const uint64_t *'), ffi.typeof('const float *')
local cast = ffi.cast
local function fetch(addr, n)
  if type(addr) ~= 'number' or addr < 65536 or addr >= 140737488355328 or n <= 0 then return false end
  if n > BUF_SIZE then
    while BUF_SIZE < n do BUF_SIZE = BUF_SIZE * 2 end
    BUF = ffi.new('uint8_t[?]', BUF_SIZE)
  end
  stats.reads = stats.reads + 1
  if K32.SbReadProcessMemory(PROCESS, cast(PVOID, addr), BUF, n, DONE) == 0 or DONE[0] ~= n then
    stats.read_fails = stats.read_fails + 1
    return false
  end
  return true
end
-- after the start-up search of the game code (the buffer grew to the code's size): back to 64 KB
local function shrink_buf()
  if BUF_SIZE > 65536 then BUF_SIZE = 65536; BUF = ffi.new('uint8_t[?]', BUF_SIZE) end
end
local function b8(o) return BUF[o] end
local function b32(o) return tonumber(cast(PU32, BUF + o)[0]) end
local function b64(o) return tonumber(cast(PU64, BUF + o)[0]) end
local function bf32(o)
  local v = tonumber(cast(PF32, BUF + o)[0])
  if v == nil or v ~= v or v == math.huge or v == -math.huge then return nil end
  return v
end
local function bptr(o)
  local p = b64(o)
  if p < 65536 or p >= 140737488355328 then return nil end
  return p
end
local function read_ptr(addr) return fetch(addr, 8) and bptr(0) or nil end
local function read_u32(addr) return fetch(addr, 4) and b32(0) or nil end
local function read_u64(addr) return fetch(addr, 8) and b64(0) or nil end
local function read_string(addr, n) return fetch(addr, n) and ffi.string(BUF, n) or nil end

-- ======================================================================================================
-- Finding the game's code: byte patterns ('??' = any byte), each must match exactly once
-- ======================================================================================================
local function su32(t, o) local a, b, c, d = t:byte(o + 1, o + 4); return a + b * 256 + c * 65536 + d * 16777216 end
local function si32(t, o) local v = su32(t, o); return v >= 2147483648 and v - 4294967296 or v end
local function compile(p)
  p = p:gsub(' ', '')
  local segs, cur_off, cur = {}, nil, {}
  for k = 0, #p / 2 - 1 do
    local h = p:sub(2 * k + 1, 2 * k + 2)
    if h == '??' then
      if cur_off then segs[#segs + 1] = { cur_off, table.concat(cur) }; cur_off, cur = nil, {} end
    else
      cur_off = cur_off or k
      cur[#cur + 1] = string.char(tonumber(h, 16))
    end
  end
  if cur_off then segs[#segs + 1] = { cur_off, table.concat(cur) } end
  local anchor = 1
  for j = 2, #segs do if #segs[j][2] > #segs[anchor][2] then anchor = j end end
  return segs, anchor, #p / 2
end
-- 0-based offsets of every place the pattern matches (at most `limit`)
local function find_all(text, p, limit)
  local segs, anchor, n = compile(p)
  local a = segs[anchor]
  local init, out = 1, {}
  while #out < (limit or 8) do
    local s = string.find(text, a[2], init, true)
    if not s then break end
    local start = s - 1 - a[1]
    local ok = start >= 0 and start + n <= #text
    if ok then
      for j, seg in ipairs(segs) do
        if j ~= anchor and text:sub(start + seg[1] + 1, start + seg[1] + #seg[2]) ~= seg[2] then ok = false; break end
      end
    end
    if ok then out[#out + 1] = start end
    init = s + 1
  end
  return out
end
local function find_once(text, p, what)
  local r = find_all(text, p, 2)
  if #r == 0 then error(what .. ': not found', 0) end
  if #r > 1 then error(what .. ': found more than once', 0) end
  return r[1]
end
-- does the pattern match at this exact 0-based offset?
local function match_at(text, o, p)
  local segs, _, n = compile(p)
  if o < 0 or o + n > #text then return false end
  for _, seg in ipairs(segs) do
    if text:sub(o + seg[1] + 1, o + seg[1] + #seg[2]) ~= seg[2] then return false end
  end
  return true
end

local function module_info(module)
  local b = ffi.cast('uint8_t *', module)
  local function r32(p) return tonumber(ffi.cast('uint32_t *', p)[0]) end
  local function r16(p) return tonumber(ffi.cast('uint16_t *', p)[0]) end
  local pe = r32(b + 0x3c)
  local stamp, image = r32(b + pe + 8), r32(b + pe + 24 + 56)
  local count, optsize = r16(b + pe + 6), r16(b + pe + 20)
  local sec = b + pe + 24 + optsize
  local code
  for i = 0, count - 1 do
    local s = sec + 40 * i
    local vsize, rva, flags = r32(s + 8), r32(s + 12), r32(s + 36)
    if bit.band(flags, 0x20000000) ~= 0 and vsize > 0x100000 and not code then code = { rva = rva, size = vsize } end
  end
  return { base = tonumber(ffi.cast('uintptr_t', module)), stamp = stamp, image = image, code = code }
end
local TEXTS = {}              -- start-up only: each module's code, read once (dropped when start-up is done)
local function code_text(info)
  local text = TEXTS[info.base] or read_string(info.base + info.code.rva, info.code.size)
  assert(text, 'cannot read the game code')
  TEXTS[info.base] = text
  return text
end

-- The code we look for (game build of September 2026; the comments say what each piece is)
local P = {
  -- a bunker switch's 'pressed' routine (there are two: the right and the left switch); it ends by jumping to that
  -- switch's own state setter with state 4 (pressed)
  press = '89 54 24 10 53 48 83 EC 20 48 8B 01 4C 8D 44 24 38 48 8B D9 C7 44 24 38 00 00 00 00 BA 54 2F 78 CD 8B 48 0C'
       .. ' E8 ?? ?? ?? ?? 84 C0 74 12 48 8B 03 45 33 C0 8B 54 24 38 8B 48 0C E8 ?? ?? ?? ?? BA AD 9C A3 85 48 8B CB'
       .. ' E8 ?? ?? ?? ?? BA 04 00 00 00 48 8B CB 48 83 C4 20 5B E9 ?? ?? ?? ??',
  -- the behaviour update: switch (behaviour - 1) over a jump table
  dispatch = 'FF CA 48 8B F9 81 FA ?? ?? ?? ?? 0F 87 ?? ?? ?? ?? 49 89 5B 10 4C 8D 05 ?? ?? ?? ?? 49 89 73 20 48 63 C2'
          .. ' 41 0F 29 73 D8 41 8B 84 80 ?? ?? ?? ??',
  -- a switch's case: still pressed (state 4) and the window ran out (press time + window <= the game clock)? then
  -- 'timed out' (state 5) through the switch's state setter
  case = '48 8B 49 08 83 39 04 0F 85 ?? ?? ?? ?? 48 8B 05 ?? ?? ?? ?? 48 8B 89 ?? ?? ?? ?? 48 81 C1 ?? ?? ?? ?? 48 3B 48 18'
      .. ' 0F 87 ?? ?? ?? ?? 48 8B CF E8 ?? ?? ?? ?? BA 05 00 00 00 48 8B CF E8 ?? ?? ?? ??',
  -- adding a behaviour record: count +0x2c, records +0x60 (stride 0x1F8), entities +0x58, index map +0x40
  records = '48 8B 3D ?? ?? ?? ?? 48 8B E9 8B 77 2C 3B 77 48 72 0B 48 8B CF E8 ?? ?? ?? ?? 8B 77 2C 3B 77 20 72 0B'
         .. ' 48 8B CF E8 ?? ?? ?? ?? 8B 77 2C 8B DE 33 D2 48 69 CB F8 01 00 00 41 B8 F8 01 00 00 48 03 4F 60'
         .. ' E8 ?? ?? ?? ?? 48 8D 0C 9B 33 D2 48 C1 E1 05 41 B8 A0 00 00 00 48 03 4F 68 E8 ?? ?? ?? ?? 48 8B 47 58',
  -- (helldivers2.exe) a unit by its id: index = id & 0x3FFFFF must be below the count (+0x98), the generation byte
  -- (+0xA0) must be id >> 22, the unit object is at +0x88 [index]
  units = '48 8B 35 ?? ?? ?? ?? 8B D9 48 8D 8E D0 00 00 00 FF 15 ?? ?? ?? ?? 8B C3 25 FF FF 3F 00 3B 86 98 00 00 00'
       .. ' 72 04 33 DB EB 1C 8B C8 48 8B 86 A0 00 00 00 C1 EB 16 38 1C 01 75 EB 48 8B 86 88 00 00 00 48 8B 1C C8',
}
-- what this build had (only a cross-check: the log says 'moved' when a new build differs)
local KNOWN = { press_right = 0x250410, press_left = 0x250C70, records = 0x3326740, clock = 0x3326348, units = 0x1A100F0,
                right = 149, left = 150, window_us = 5000000 }

-- everything the mod needs, from the places the patterns matched (`sites`, offsets in the code sections). `rg`/`re`
-- read bytes of game.dll's / the exe's code: from the whole code text (first look) or from memory (cached places).
-- `behs`: the switch behaviours to check (nil: try every case of the behaviour update).
local function derive(G, E, sites, rg, re, behs)
  local crva = G.code.rva
  local function sub(r, o, n) local t = r(o, n); return t and #t == n and t or nil end
  local function pat_len(p) local _, _, n = compile(p); return n end
  local L = { game = G.base, exe = E.base, switches = {} }
  -- 1. the two switch 'pressed' routines and the state setter each one ends in
  local by_setter, npress = {}, pat_len(P.press)
  for _, o in ipairs(sites.press) do
    local t = sub(rg, o, npress)
    if not t or not match_at(t, 0, P.press) then error('switch routine changed', 0) end
    by_setter[crva + o + npress + si32(t, npress - 4)] = crva + o
  end
  -- 2. the behaviour update's jump table: which behaviours are switches (their case calls one of those setters)
  local d = sites.dispatch
  local t = sub(rg, d, pat_len(P.dispatch))
  if not t or not match_at(t, 0, P.dispatch) then error('behaviour update changed', 0) end
  local max = su32(t, 7)
  if si32(t, 24) + crva + d + 28 ~= 0 then error('behaviour update: unexpected table base', 0) end
  local table_rva = su32(t, 44)
  if max > 4096 or table_rva < crva or table_rva + 4 * (max + 1) > crva + G.code.size then error('behaviour update: table out of range', 0) end
  local list = behs
  if not list then list = {}; for b = 1, max + 1 do list[#list + 1] = b end end
  local clock, window, stoff
  local ncase = pat_len(P.case)
  for _, beh in ipairs(list) do
    local e = sub(rg, table_rva - crva + 4 * (beh - 1), 4)
    local c = e and su32(e, 0) - crva
    local ct = c and c >= 0 and sub(rg, c, ncase)
    if ct and match_at(ct, 0, P.case) then
      local setter = crva + c + 65 + si32(ct, 61)
      if by_setter[setter] then
        L.switches[beh] = { press = L.game + by_setter[setter], rva = by_setter[setter] }
        clock, window, stoff = crva + c + 20 + si32(ct, 16), su32(ct, 30), su32(ct, 23)
      end
    end
  end
  local n = 0
  for _ in pairs(L.switches) do n = n + 1 end
  if n ~= 2 then error('switch behaviours: found ' .. n .. ' (expected 2)', 0) end
  L.clock, L.window_us, L.press_time = L.game + clock, window, 8 + stoff
  -- 3. the behaviour records
  local rt = sub(rg, sites.records, pat_len(P.records))
  if not rt or not match_at(rt, 0, P.records) then error('behaviour records changed', 0) end
  L.records = L.game + crva + sites.records + 7 + si32(rt, 3)
  L.stride = su32(rt, 52)
  -- 4. units (in helldivers2.exe)
  local ut = sub(re, sites.units, pat_len(P.units))
  if not ut or not match_at(ut, 0, P.units) then error('units changed', 0) end
  L.units = L.exe + E.code.rva + sites.units + 7 + si32(ut, 3)
  -- names: the right switch's routine comes first in the code (as in the September 2026 build; only used in the log)
  local right, left
  for beh, sw in pairs(L.switches) do if not right or sw.rva < L.switches[right].rva then right = beh end end
  for beh in pairs(L.switches) do if beh ~= right then left = beh end end
  L.right, L.left = right, left
  L.other = { [right] = left, [left] = right }
  return L
end

-- cache: the places found, for this game build (looked at again, byte for byte, on every start)
local CACHE = LOGDIR and (LOGDIR .. '\\SoloBuddyBunkers.cache') or nil
local function cache_load()
  if not CACHE then return nil end
  local f = io.open(CACHE, 'r'); if not f then return nil end
  local s = f:read('*a'); f:close()
  local fn = loadstring('return ' .. s)
  if not fn then return nil end
  setfenv(fn, {})
  local ok, t = pcall(fn)
  return ok and type(t) == 'table' and t or nil
end
local function cache_save(key, sites, behs)
  if not CACHE then return end
  local f = io.open(CACHE, 'w'); if not f then return end
  f:write(string.format('{key=%q,press={%d,%d},dispatch=%d,records=%d,units=%d,behs={%d,%d}}', key,
    sites.press[1], sites.press[2], sites.dispatch, sites.records, sites.units, behs[1], behs[2]))
  f:close()
end

local function resolve_layout()
  local t0 = os.clock()
  local gmod = K32.SbGetModuleHandleA('game.dll')
  local emod = K32.SbGetModuleHandleA(nil)
  if gmod == nil or emod == nil then error('game modules not loaded', 0) end
  local G, E = module_info(gmod), module_info(emod)
  assert(G.code and E.code, 'no code section')
  local key = string.format('%08x-%08x-%08x/%08x-%08x-%08x', G.stamp, G.image, G.code.size, E.stamp, E.image, E.code.size)
  local function mem(info) return function(o, n) return read_string(info.base + info.code.rva + o, n) end end
  local L
  local cache = cache_load()
  if cache and cache.key == key and type(cache.press) == 'table' and type(cache.behs) == 'table' then
    local ok, res = pcall(derive, G, E, cache, mem(G), mem(E), cache.behs)
    if ok then L = res; session.layout = 'cached for this game build (checked)' end
  end
  if not L then
    local sites = {}
    local text = code_text(G)
    sites.press = find_all(text, P.press, 4)
    if #sites.press ~= 2 then error('switch routines: found ' .. #sites.press .. ' (expected 2)', 0) end
    sites.dispatch = find_once(text, P.dispatch, 'behaviour update')
    sites.records = find_once(text, P.records, 'behaviour records')
    local etext = code_text(E)
    sites.units = find_once(etext, P.units, 'units')
    L = derive(G, E, sites, function(o, n) return text:sub(o + 1, o + n) end, function(o, n) return etext:sub(o + 1, o + n) end)
    text, etext = nil, nil
    cache_save(key, sites, { L.right, L.left })
    -- the cross-check with the September 2026 build
    local moved = {}
    local function cmp(name, v) if KNOWN[name] ~= v then moved[#moved + 1] = string.format('%s %x -> %x', name, KNOWN[name], v) end end
    cmp('press_right', L.switches[L.right].rva); cmp('press_left', L.switches[L.left].rva)
    cmp('records', L.records - L.game); cmp('clock', L.clock - L.game); cmp('units', L.units - L.exe)
    cmp('right', L.right); cmp('left', L.left); cmp('window_us', L.window_us)
    session.layout = #moved == 0 and 'found in the game code (same as the September 2026 build)'
      or ('found in the game code (new game build; moved: ' .. table.concat(moved, ', ') .. ')')
  end
  session.window = string.format('%.1f s', L.window_us / 1e6)
  session.scan_seconds = os.clock() - t0
  return L
end

-- ======================================================================================================
-- The switches
-- ======================================================================================================
local L, broken, last_error
local next_look = 0          -- frame of the next look for switches
local enabled = true
local switches = {}          -- [entity id] = { j, beh, obj, unit, state, seen, done }
local doors = {}             -- (recorder builds: the bunker doors too)
-- the switches' entity type hashes (low, high 32 bits) as the entity table stores them
local T_RIGHT, T_LEFT = { 0x63CB630A, 0x574D0282 }, { 0x8F077BEC, 0x81A827B7 }
local function is_switch_type(lo, hi) return (lo == T_RIGHT[1] and hi == T_RIGHT[2]) or (lo == T_LEFT[1] and hi == T_LEFT[2]) end
local REC_STATE = 8          -- record + 8: the switch's state (4 = pressed, 5 = timed out); ctx = { entity, record + 8 }

local function records_base()
  local om = read_ptr(L.records); if not om then return nil end
  if not fetch(om + 0x2c, 4) then return nil end
  local count = b32(0)
  if count == 0 or count > 1000000 then return nil, nil, nil, count end
  local recs, ents = read_ptr(om + 0x60), read_ptr(om + 0x58)
  return recs, ents, om, count
end

-- every switch in the mission, by its behaviour record. The records are read a block at a time (only their first
-- 4 bytes, the behaviour, matter), one block per frame, so a mission with many records never costs a big read at once.
local pass = nil             -- { next, count, recs, ents, seen }
local function block(p)
  local per = math.floor(65536 / L.stride)
  local first = p.next
  local n = math.min(per, p.count - first)
  p.next = first + n
  if n <= 0 or not fetch(p.recs + first * L.stride, n * L.stride) then return end
  local found = {}
  for k = 0, n - 1 do
    local beh = b32(k * L.stride)
    if L.switches[beh] then found[#found + 1] = { first + k, beh } end
  end
  for _, f in ipairs(found) do
    local j, beh = f[1], f[2]
    local obj = read_ptr(p.ents + j * 8)
    if obj and fetch(obj, 16) then
      local lo, hi, eid, unit = b32(0), b32(4), b32(8), b32(12)
      if not is_switch_type(lo, hi) and not session.notes['switch types'] then
        note('switch types', string.format('a switch\'s entity type is %08x%08x, not one the mod knows (joined games may not find the switches)', hi, lo))
        event(session.notes['switch types'])
      end
      local s = switches[eid]
      if not s then s = { eid = eid }; switches[eid] = s end
      s.j, s.beh, s.obj, s.unit, s.rec = j, beh, obj, unit, p.recs + j * L.stride
      p.seen[eid] = true
    end
  end
end
local gone_hook              -- the recorder: told when a switch's record goes away
local function finish(p)
  local n = 0
  for eid, s in pairs(switches) do
    if not p.seen[eid] then switches[eid] = nil; if gone_hook then gone_hook(s) end else n = n + 1 end
  end
  stats.switches = n
end
local function start_pass()
  stats.scans = stats.scans + 1
  local recs, ents, _, count = records_base()
  if not (recs and ents) then switches = {}; stats.switches = 0; return nil end
  return { next = 0, count = count, recs = recs, ents = ents, seen = {} }
end
-- one step of the running look (or start one); true when a look just finished
local function scan_step()
  if not pass then pass = start_pass(); if not pass then return true end end
  block(pass)
  if pass.next >= pass.count then finish(pass); pass = nil; return true end
  return false
end
-- a whole look at once (after the records moved under us)
local function scan()
  local p = start_pass()
  if not p then return end
  while p.next < p.count do block(p) end
  finish(p)
  pass = nil
end

-- a unit's position (helldivers2.exe unit table; the unit's world pose, root node)
local UNITS_AT               -- the unit table's global (helldivers2.exe), from either path's start-up search
local function unit_position(unit)
  local reg = UNITS_AT and read_ptr(UNITS_AT); if not reg then return nil end
  local index, gen = bit.band(unit, 0x3FFFFF), bit.band(bit.rshift(unit, 22), 0xFF)
  local count = read_u32(reg + 0x98); if not count or index >= count then return nil end
  local gens = read_ptr(reg + 0xA0); if not gens or not fetch(gens + index, 1) or b8(0) ~= gen then return nil end
  local objs = read_ptr(reg + 0x88); local obj = objs and read_ptr(objs + 8 * index)
  if not obj or read_u32(obj + 8) ~= unit then return nil end
  local poses = read_ptr(obj + 0x88)
  if not poses or not fetch(poses + 48, 12) then return nil end
  local x, y, z = bf32(0), bf32(4), bf32(8)
  if not x or not y or not z or math.abs(x) > 1e5 or math.abs(y) > 1e5 or math.abs(z) > 1e5 then return nil end
  return x, y, z
end

-- the switch still is what we think (records move when other things in the mission go away)
local need_scan = false      -- look again after the walk through the switches (never during it)
local function still(s)
  if not fetch(s.rec, 4) or b32(0) ~= s.beh then return false end
  local _, ents = records_base()
  if not ents then return false end
  return read_ptr(ents + s.j * 8) == s.obj and read_u32(s.obj + 8) == s.eid
end

local PRESS_T = ffi.typeof('void (*)(void *, uint32_t)')
local CTX = ffi.new('uint64_t[2]')
local function press(s)
  CTX[0], CTX[1] = s.obj, s.rec + REC_STATE
  ffi.cast(PRESS_T, L.switches[s.beh].press)(CTX, 0)
end
local function no_jit(fn)    -- calls into the game are never compiled: the interpreter's call is the safe one
  local j = rawget(_G, 'jit')
  if type(j) == 'table' and type(j.off) == 'function' then pcall(j.off, fn) end
end
no_jit(press)

local function side(beh) return beh == L.right and 'right' or 'left' end

local function on_pressed(s)
  local px, py, pz = unit_position(s.unit)
  if not px then
    stats.skipped = stats.skipped + 1
    event('a ' .. side(s.beh) .. ' switch was pressed, but its position could not be read - left alone')
    return
  end
  local want, best, bd = L.other[s.beh], nil, PAIR_RANGE * PAIR_RANGE
  for _, o in pairs(switches) do
    if o.beh == want then
      local x, y, z = unit_position(o.unit)
      if x then
        local dd = (x - px) ^ 2 + (y - py) ^ 2 + (z - pz) ^ 2
        if dd < bd then best, bd = o, dd end
      end
    end
  end
  if not best then
    stats.skipped = stats.skipped + 1
    event('a ' .. side(s.beh) .. string.format(' switch was pressed, but no %s switch is within %d m - left alone', side(want), PAIR_RANGE))
    return
  end
  if not fetch(best.rec + REC_STATE, 4) then return end
  local st = b32(0)
  if st == 4 then return end                 -- the other one is pressed already: nothing to do
  if st < 1 or st > 5 then                   -- not a state the game's switches use: something moved
    stats.skipped = stats.skipped + 1
    event(string.format('the other switch\'s state reads %d (not a switch state) - left alone', st))
    need_scan = true
    return
  end
  if not still(best) or not still(s) then
    stats.skipped = stats.skipped + 1
    event('the switches moved in memory before the press - left alone (looking again)')
    need_scan = true
    return
  end
  press(best)
  stats.presses = stats.presses + 1
  local after = fetch(best.rec + REC_STATE, 4) and b32(0) or nil
  if after == 4 then stats.opened_for_you = stats.opened_for_you + 1 end
  event(string.format('you pressed a %s switch; pressed the %s switch %.1f m away for you (its state %d -> %s)',
    side(s.beh), side(best.beh), math.sqrt(bd), st, tostring(after)))
end

-- ======================================================================================================
-- Joined games (someone else hosts). The switches' logic runs only in the host's game, so the press above can't be
-- used there. When you press something in a joined game, your game sends the host an interaction request for it and
-- keeps a short note while it waits for the answer (your interactor's pending request: the thing's entity id, which
-- of its interactions, a 2 s timer). When that note names a bunker switch, the mod sends the host the same request for
-- the bunker's other switch, through the same game routine your press went through.
-- ======================================================================================================
local PJ = {
  -- 'interact' (your interactor's current target): the interactor manager's global
  head = '3B 15 ?? ?? ?? ?? 48 8B 1D ?? ?? ?? ?? 0F 84 ?? ?? ?? ?? 44 8B 5B 30 45 33 D2 48 89 78 20 45 8B C2 8B 7B 38 0F AF FA',
  -- ... its interactor list (+0x40: entity id at +8, 'yours' flag +0x14 bit 0) and instances (+0x48, 0x880 bytes each)
  inst = '41 8B 49 04 B8 FF FF FF FF 3B C8 0F 84 ?? ?? ?? ?? 8B D1 48 8B 4B 40 4C 8B 04 D1 4C 89 84 24 80 00 00 00'
      .. ' 41 F6 40 14 01 0F 84 ?? ?? ?? ?? 4C 89 6C 24 60 4C 69 EA 80 08 00 00 4C 03 6B 48',
  -- ... then the interaction routine (thing, interactor, which interaction) and the pending request it hands back,
  -- kept at instance + 0x818 (16 bytes) and + 0x828 (the timer)
  call = '8B 4B 08 48 8B D6 4C 6B C7 68 4D 03 C4 E8 ?? ?? ?? ?? 8B 46 04 48 8D 54 24 30 44 8B 4B 08 44 8B 06 89 44 24 20'
      .. ' E8 ?? ?? ?? ?? 0F 10 00 41 0F 11 85 ?? ?? ?? ?? F2 0F 10 48 10 F2 41 0F 11 8D ?? ?? ?? ??',
  -- the interactor update: the instance count (+0x1C)
  count = '48 89 4C 24 38 0F 28 F9 48 8B D1 89 5C 24 30 39 59 1C 0F 86',
  -- the interactables by entity id (hash buckets, size, empty key, multiplier)
  im = '3B 15 ?? ?? ?? ?? 4C 8B 1D ?? ?? ?? ?? 4D 63 F1 75 07 B8 FF FF FF FF EB ?? 45 8B 8B ?? ?? ?? ?? 45 33 C0 48 89 5C 24 10'
    .. ' 41 8B 9B ?? ?? ?? ?? 48 89 6C 24 18 0F AF DA 41 8D 69 FF 48 89 74 24 20 48 89 7C 24 28 45 85 C9 74 ?? 49 8B BB ?? ?? ?? ??'
    .. ' 41 8B B3 ?? ?? ?? ??',
  -- the entity table (entity id -> row): its global, and its rows (24 bytes: type hash, entity id, unit)
  ents = '4C 8B 2D ?? ?? ?? ?? 33 FF 8B 0D ?? ?? ?? ?? 90 44 8B D7 49 81 C2',
  rows = '41 8B 41 04 4C 8D 04 40 49 8D 85 ?? ?? ?? ?? 4A 8D 04 C0',
}
local KNOWN_J = { mgr = 0x33269A0, fn = 0x979570, req = 0x818, im = 0x3326D68, ents = 0x346BF98, rows = 0xF32F18 }
local J_ORDER = { 'head', 'inst', 'call', 'count', 'im', 'ents', 'rows' }
local ENT_ROWS = 2048
local J, J_state = nil, 'not looked for yet'
local JS = { requests = 0, sent = 0, skipped = 0, last = nil }
local JCACHE = LOGDIR and (LOGDIR .. '\\SoloBuddyBunkers.joined.cache') or nil

local function derive_join(G, E, sites, rg, re)
  local crva = G.code.rva
  local function pat_len(p) local _, _, n = compile(p); return n end
  local t = {}
  for _, k in ipairs(J_ORDER) do
    local o = sites[k]
    local s = type(o) == 'number' and rg(o, pat_len(PJ[k]))
    if not s or #s ~= pat_len(PJ[k]) or not match_at(s, 0, PJ[k]) then error(k .. ' changed', 0) end
    t[k] = s
  end
  local ut = type(sites.units) == 'number' and re(sites.units, pat_len(P.units))
  if not ut or not match_at(ut, 0, P.units) then error('units changed', 0) end
  -- the three pieces of 'interact' belong together
  local d1, d2 = sites.inst - sites.head, sites.call - sites.inst
  if d1 <= 0 or d1 > 0x200 or d2 <= 0 or d2 > 0x400 then error('the interaction code changed (its pieces are apart)', 0) end
  local g = G.base
  local j = {
    mgr = g + crva + sites.head + 13 + si32(t.head, 9),
    list = t.inst:byte(23), insts = t.inst:byte(62), stride = su32(t.inst, 54),
    fn = g + crva + sites.call + 42 + si32(t.call, 38), player = t.call:byte(30), req = su32(t.call, 49),
    count = t.count:byte(18),
    im = g + crva + sites.im + 13 + si32(t.im, 9),
    im_size = su32(t.im, 28), im_mult = su32(t.im, 43), im_buckets = su32(t.im, 77), im_empty = su32(t.im, 84),
    ents = g + crva + sites.ents + 7 + si32(t.ents, 3), rows = su32(t.rows, 11),
    units = E.base + E.code.rva + sites.units + 7 + si32(ut, 3),
  }
  j.head_n = math.max(j.count + 4, j.list + 8, j.insts + 8)
  if su32(t.call, 63) ~= j.req + 0x10 or j.stride < j.req + 0x18 or j.stride > 0x4000 or j.rows > 0x4000000 then
    error('layout not plausible', 0)
  end
  return j
end

local function resolve_join()
  local gmod, emod = K32.SbGetModuleHandleA('game.dll'), K32.SbGetModuleHandleA(nil)
  if gmod == nil or emod == nil then error('game modules not loaded', 0) end
  local G, E = module_info(gmod), module_info(emod)
  if not (G.code and E.code) then error('no code section', 0) end
  local key = string.format('%08x-%08x-%08x/%08x-%08x-%08x', G.stamp, G.image, G.code.size, E.stamp, E.image, E.code.size)
  local function mem(info) return function(o, n) return read_string(info.base + info.code.rva + o, n) end end
  if JCACHE then
    local f = io.open(JCACHE, 'r')
    if f then
      local s = f:read('*a'); f:close()
      local fn = loadstring('return ' .. s)
      if fn then
        setfenv(fn, {})
        local ok, c = pcall(fn)
        if ok and type(c) == 'table' and c.key == key then
          local ok2, j = pcall(derive_join, G, E, c, mem(G), mem(E))
          if ok2 then return j, 'cached for this game build (checked)' end
        end
      end
    end
  end
  local text, etext = code_text(G), code_text(E)
  local sites = {}
  for _, k in ipairs(J_ORDER) do sites[k] = find_once(text, PJ[k], k) end
  sites.units = find_once(etext, P.units, 'units')
  local j = derive_join(G, E, sites, function(o, n) return text:sub(o + 1, o + n) end, function(o, n) return etext:sub(o + 1, o + n) end)
  if JCACHE then
    local f = io.open(JCACHE, 'w')
    if f then
      local parts = { string.format('key=%q', key), 'units=' .. sites.units }
      for _, k in ipairs(J_ORDER) do parts[#parts + 1] = k .. '=' .. sites[k] end
      f:write('{', table.concat(parts, ','), '}'); f:close()
    end
  end
  local moved = {}
  local function cmp(name, v) if KNOWN_J[name] ~= v then moved[#moved + 1] = string.format('%s %x -> %x', name, KNOWN_J[name], v) end end
  cmp('mgr', j.mgr - G.base); cmp('fn', j.fn - G.base); cmp('req', j.req); cmp('im', j.im - G.base); cmp('ents', j.ents - G.base); cmp('rows', j.rows)
  return j, #moved == 0 and 'found in the game code (same as the September 2026 build)'
    or ('found in the game code (new game build; moved: ' .. table.concat(moved, ', ') .. ')')
end

-- the low 32 bits of a * b (both below 2^32)
local function mul32(a, b)
  local lo = a * (b % 65536)
  local hi = (a % 65536) * math.floor(b / 65536)
  return (lo + (hi % 65536) * 65536) % 4294967296
end
-- is this entity id one of the game's interactables (the same lookup the interaction routine makes first)?
local function interactable(eid)
  local im = read_ptr(J.im); if not im then return false end
  local buckets = read_ptr(im + J.im_buckets)
  local size, empty, mult = read_u32(im + J.im_size), read_u32(im + J.im_empty), read_u32(im + J.im_mult)
  if not (buckets and size and empty and mult) or size == 0 or size > 0x100000 then return false end
  local h, mask = mul32(eid, mult), size - 1
  for i = 0, math.min(size, 4096) - 1 do
    if not fetch(buckets + bit.band(h + i, mask) * 8, 8) then return false end
    local k, v = b32(0), b32(4)
    if k == eid then return v ~= 0xFFFFFFFF end
    if k == empty then return false end
  end
  return false
end

-- the bunker switches in the entity table: { [entity id] = { side, unit } }
local function entity_switches()
  local em = read_ptr(J.ents)
  if not em or not fetch(em + J.rows, ENT_ROWS * 24) then return nil end
  local out = {}
  for i = 0, ENT_ROWS - 1 do
    local o = i * 24
    local lo = b32(o)
    if lo == T_RIGHT[1] or lo == T_LEFT[1] then
      local hi, e, unit = b32(o + 4), b32(o + 8), b32(o + 12)
      if is_switch_type(lo, hi) and e ~= 0 and unit ~= 0 then out[e] = { side = lo == T_RIGHT[1] and 'right' or 'left', unit = unit } end
    end
  end
  return out
end

local REQ = ffi.typeof('void *(*)(void *, void *, uint32_t, uint32_t, uint32_t)')
local OUT = ffi.new('uint8_t[64]')
-- the joined-game watch: the manager header last seen, your interactors in it, and the request each one last had
local JW = { mgr = nil, n = nil, list = nil, insts = nil, mine = {}, next_mine = 0, active = false, unreadable = false }
local seen_req = {}          -- [instance] = the entity id of its pending request (so each press is acted on once)
local function on_request(k, target, which, info)
  JS.requests = JS.requests + 1
  local sw = entity_switches()
  local s = sw and sw[target]
  if not s then return end                   -- not a bunker switch (a door, a terminal, a pickup...)
  local function skip(why)
    JS.skipped = JS.skipped + 1
    event('joined game: you pressed a ' .. s.side .. ' switch, ' .. why .. ' - left alone')
  end
  local px, py, pz = unit_position(s.unit)
  if not px then return skip('but its position could not be read') end
  local want, best, bd = s.side == 'right' and 'left' or 'right', nil, PAIR_RANGE * PAIR_RANGE
  for e, o in pairs(sw) do
    if o.side == want then
      local x, y, z = unit_position(o.unit)
      if x then
        local dd = (x - px) ^ 2 + (y - py) ^ 2 + (z - pz) ^ 2
        if dd < bd then best, bd = e, dd end
      end
    end
  end
  if not best then return skip(string.format('but no %s switch is within %d m', want, PAIR_RANGE)) end
  if not interactable(target) then return skip('but the game did not list it as something to press') end
  if not interactable(best) then return skip('but the game did not list the other switch as something to press') end
  if not fetch(info + J.player, 4) then return skip('but your interactor could not be read') end
  local player = b32(0)
  if player == 0 or player == 0xFFFFFFFF then return skip('but your interactor could not be read') end
  -- the request is still the one we saw (nothing moved under us)
  if not fetch(JW.insts + k * J.stride + J.req + 8, 4) or b32(0) ~= target then return skip('but the press was already answered') end
  ffi.fill(OUT, 64)
  ffi.cast(REQ, J.fn)(nil, OUT, best, player, which)
  JS.sent = JS.sent + 1
  JS.last = string.format('%s: you pressed switch %x (%s); sent the host a press of switch %x (%s) %.1f m away, as interactor %x (interaction %d)',
    os.date('%H:%M:%S'), target, s.side, best, want, math.sqrt(bd), player, which)
  event(string.format('joined game: you pressed a %s switch; asked the host to press the %s switch %.1f m away', s.side, want, math.sqrt(bd)))
end
no_jit(on_request)

-- every SCAN_EVERY frames while your game runs no switches: does the mission have buddy bunkers at all?
local function joined_look()
  local sw = entity_switches()
  if not sw then
    -- (normal on the ship and in menus; worth a line only when it stops being readable during a mission)
    if JW.was_readable and not JW.unreadable then JW.unreadable = true; event('joined games: the entity table could not be read (waiting)') end
    JW.active = false
  else
    JW.unreadable, JW.was_readable = false, true
    JW.active = next(sw) ~= nil
  end
  if not JW.active then seen_req, JW.mgr = {}, nil end
end

-- every frame in a mission with buddy bunkers that your game doesn't run: a new pending request on your interactor?
local function watch_join(f)
  local mgr = read_ptr(J.mgr); if not mgr then return end
  if not fetch(mgr, J.head_n) then return end                  -- the manager's header in one read
  local n, list, insts = b32(J.count), bptr(J.list), bptr(J.insts)
  if not (list and insts) or n > 64 then return end
  local moved = mgr ~= JW.mgr or n ~= JW.n or list ~= JW.list or insts ~= JW.insts
  if moved or f >= JW.next_mine then
    JW.mgr, JW.n, JW.list, JW.insts, JW.next_mine = mgr, n, list, insts, f + SCAN_EVERY
    local infos, mine = {}, {}
    if n > 0 and fetch(list, n * 8) then for k = 0, n - 1 do infos[k] = bptr(k * 8) end end
    for k = 0, n - 1 do
      local info = infos[k]
      if info and fetch(info + 0x14, 1) and b8(0) % 2 == 1 then mine[#mine + 1] = { k = k, info = info } end
    end
    JW.mine = mine
    if moved then
      -- a request already pending when the watch (re)starts is not a new press: noted, not acted on
      seen_req = {}
      for _, m in ipairs(mine) do
        if fetch(insts + m.k * J.stride + J.req + 8, 4) and b32(0) ~= 0 then seen_req[m.k] = b32(0) end
      end
      return
    end
  end
  for _, m in ipairs(JW.mine) do
    local k = m.k
    if fetch(insts + k * J.stride + J.req + 8, 8) then
      local target, which = b32(0), b32(4)
      if target ~= 0 and target ~= seen_req[k] then
        seen_req[k] = target
        if enabled then on_request(k, target, which, m.info) end
      elseif target == 0 then
        seen_req[k] = nil
      end
    end
  end
end

local rec_count = 0           -- (recorder builds: lines in the record log)

local function watch()
  for _, s in pairs(switches) do
    if fetch(s.rec + REC_STATE, 4) then
      local st = b32(0)
      if st == 4 and s.state ~= 4 then
        -- a new press? (press time within FRESH_US of the game clock)
        local pt = read_u64(s.rec + L.press_time)
        local clk = read_ptr(L.clock); local t = clk and read_u64(clk + 0x18)
        if s.state ~= nil and pt and t and t >= pt and t - pt <= FRESH_US then
          if enabled then on_pressed(s) end
        elseif TESTER and s.state == nil then
          note('first seen pressed', 'a switch was already pressed when first seen - left alone')
        end
      end
      s.state = st
    end
  end
  if need_scan then need_scan = false; scan() end
end


-- ======================================================================================================
-- Mod Options Menu (optional): one toggle
-- ======================================================================================================
local menu_state = 'Mod Options Menu not installed (on)'
local menu_linked = false
local function link_menu()
  local M = rawget(_G, 'ModOptionsMenu')
  if type(M) ~= 'table' or M.api ~= 1 or type(M.register_option) ~= 'function' then return false end
  local id = 'solo_buddy_bunkers.on'
  local ok, yes = pcall(M.register_option, id, {
    type = 'toggle', mod = 'Solo Buddy Bunkers', label = 'Open buddy bunkers alone', default = true,
    description = 'When you press one switch of a two-person bunker, the other switch is pressed for you.' })
  if ok and yes then
    local function apply(v) if type(v) == 'boolean' then enabled = v; event('options menu: ' .. (v and 'on' or 'off')) end end
    local okg, v = pcall(M.get, id)
    if okg then apply(v) end
    pcall(M.on_change, id, apply)
    menu_state = 'Mod Options Menu: 1 toggle'
  else
    menu_state = 'Mod Options Menu: could not add the toggle (' .. tostring(yes) .. ')'
  end
  return true
end

-- ======================================================================================================
-- Tick
-- ======================================================================================================
local frame, ready = 0, not V19
local host_off               -- why the solo/host part is off (a game update changed its code), or nil
local started = false        -- the start-up search is done (both parts)
local function tick()
  frame = frame + 1
  if not menu_linked and frame % 60 == 0 and frame < 3600 then menu_linked = link_menu() end
  if not ready then SB.status = 'waiting for start-up'; return end
  if not started then
    started = true
    -- the two parts are found on their own: if a game update breaks one, the other keeps working
    local ok, res = pcall(resolve_layout)
    if ok then
      L, UNITS_AT = res, res.units
      event('game code (solo and host): ' .. session.layout .. string.format(' (%.2f s)', session.scan_seconds))
    else
      host_off = 'could not find what it needs in the game code: ' .. tostring(res)
      event('solo and host games: off - ' .. host_off)
    end
    local t0 = os.clock()
    local okj, j, how = pcall(resolve_join)
    if okj then
      J, J_state = j, how .. string.format(' (%.2f s)', os.clock() - t0)
      UNITS_AT = UNITS_AT or j.units
    else J_state = 'off - could not find what it needs in the game code: ' .. tostring(j) end
    event('game code (joined games): ' .. J_state)
    TEXTS = {}; shrink_buf()                 -- the code copies are not needed any more
    if not L and not J then broken, last_error, SB.status = true, host_off, 'off'; return end
  end
  if L and (pass or frame >= next_look) then
    if scan_step() then
      next_look = frame + SCAN_EVERY
      if J and next(switches) == nil then joined_look() end
    end
  elseif not L and J and frame >= next_look then
    next_look = frame + SCAN_EVERY
    joined_look()
  end
  if next(switches) == nil and not (RECORDER and next(doors)) then
    if J and JW.active and not RECORDER then
      watch_join(frame)                      -- a joined game: your presses go to the host
      SB.status = enabled and 'on (joined game: your presses go to the host)' or 'off (options menu)'
    else
      SB.status = enabled and 'on (no buddy bunkers nearby)' or 'off (options menu)'
    end
    if host_off and enabled then SB.status = SB.status .. '; solo and host games: off' end
    if not J and enabled then SB.status = SB.status .. '; joined games: off' end
    return
  end
  SB.status = enabled and 'on (your game runs the switches: solo or hosting)' or 'off (options menu)'
  if not J and enabled then SB.status = SB.status .. '; joined games: off' end
  if RECORDER or frame % WATCH_EVERY == 0 then watch() end      -- the recorder looks every frame
end

-- ======================================================================================================
-- The log (looked at every 10 s, rewritten only when something in it changed)
-- ======================================================================================================
local T = { n = 0, sum = 0, max = 0 }
local function write_log()
  if not LOGDIR then return end
  local f = io.open(LOGDIR .. '\\SoloBuddyBunkers.log', 'w')
  if not f then return end
  f:write('Solo Buddy Bunkers ', VERSION, '  (started ', session.started, ', written ', os.date('%H:%M:%S'), ')\n')
  f:write('status: ', SB.status, broken and (' - ' .. tostring(last_error)) or '', '\n')
  if host_off then f:write('solo and host games: off - ', host_off, '\n') end
  f:write('Bingus Shared Loader: ', V19 and 'v19 or newer' or 'older than v19 (needs v19 or newer; using the old start-up)', '\n')
  if L then f:write('game code (solo and host): ', tostring(session.layout), string.format(' (%.2f s)', session.scan_seconds or 0), '\n') end
  f:write('game code (joined games): ', J_state, '\n')
  if session.window then f:write('the game\'s window for the second switch: ', session.window, '\n') end
  f:write('options menu: ', menu_state, '\n')
  if T.n > 0 then f:write(string.format('cost per frame: average %.4f ms, highest %.3f ms\n', T.sum / T.n, T.max)) end
  f:write(string.format('solo and host games: switches in the mission %d; pressed for you %d (worked %d), left alone %d\n',
    stats.switches, stats.presses, stats.opened_for_you, stats.skipped))
  if J then
    f:write(string.format('joined games: presses sent to the host for you %d, left alone %d\n', JS.sent, JS.skipped))
    if TESTER then
      f:write(string.format('joined games, research: pending requests seen %d; last: %s\n', JS.requests, tostring(JS.last)))
    end
  end
  if TESTER then
    f:write(string.format('looks for switches %d, game reads %d (failed %d)\n', stats.scans, stats.reads, stats.read_fails))
    if L then
      f:write(string.format('switch behaviours: right %d, left %d; record stride %d; press time at record + %d\n',
        L.right, L.left, L.stride, L.press_time))
      for eid, s in pairs(switches) do
        local x, y, z = unit_position(s.unit)
        f:write(string.format('  switch %d: %s, state %s, %s\n', eid, side(s.beh), tostring(s.state),
          x and string.format('at %.1f, %.1f, %.1f', x, y, z) or 'position unknown'))
      end
    end
    for k, v in pairs(session.notes) do f:write(k, ': ', v, '\n') end
  end
  f:write('\nrecent events:\n')
  for _, e in ipairs(session.events) do f:write('  ', e, '\n') end
  f:close()
end
SB.write_log = write_log

-- ======================================================================================================
-- Hooks
-- ======================================================================================================
local game_update, game_shutdown = rawget(_G, 'update'), rawget(_G, 'shutdown')
if type(game_update) ~= 'function' then SB.status = 'off: game update function not found'; write_log(); return end
pcall(ffi.cdef, 'int SbQueryPerformanceCounter(int64_t *c) __asm__("QueryPerformanceCounter"); int SbQueryPerformanceFrequency(int64_t *f) __asm__("QueryPerformanceFrequency");')
local q, per_ms = ffi.new('int64_t[1]'), nil
do
  local fq = ffi.new('int64_t[1]')
  if pcall(function() return K32.SbQueryPerformanceFrequency(fq) end) and fq[0] > 0 then per_ms = tonumber(fq[0]) / 1000 end
end
local next_log, logged = 0, nil
rawset(_G, 'update', function(...)
  if not broken then
    local a
    if per_ms then K32.SbQueryPerformanceCounter(q); a = q[0] end
    local ok, e = pcall(tick)
    if per_ms then
      K32.SbQueryPerformanceCounter(q)
      local ms = tonumber(q[0] - a) / per_ms
      T.n, T.sum = T.n + 1, T.sum + ms
      if ms > T.max then T.max = ms end
    end
    if not ok then broken, last_error, SB.status = true, 'tick: ' .. tostring(e), 'off'; event(last_error); pcall(write_log) end
  end
  local now = os.clock()
  if now >= next_log then
    next_log = now + 10
    local sig = SB.status .. #session.events .. ':' .. stats.presses .. ':' .. stats.switches .. ':' .. tostring(session.events[#session.events]) .. ':' .. rec_count .. ':' .. (JS.sent + JS.skipped)
    if sig ~= logged then logged = sig; pcall(write_log) end
  end
  return game_update(...)
end)
rawset(_G, 'shutdown', function(...)
  pcall(write_log)
  if type(game_shutdown) == 'function' then return game_shutdown(...) end
end)
if V19 then
  LOADER.after_startup(function()
    ready = true
    if not menu_linked then menu_linked = link_menu() end
  end)
else
  event('needs Bingus Shared Loader v19 or newer (using the old start-up)')
end
event('start-up finished')
pcall(write_log)
