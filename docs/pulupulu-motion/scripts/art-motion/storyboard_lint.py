#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = []
# ///
"""storyboard_lint.py — check a shot list mechanically before writing any code.

Usage:
  uv run storyboard_lint.py shot-list.md [--script script.txt]     # or: python3 storyboard_lint.py …

Lock the style at the top of the shot list first (three lines, outside the table):
  Style: one sentence (one style card or one drawing method, used for the whole film)
  Palette: a palette name (paper/poster/ink/navy/bauhaus/snow/wood/chalk) or 3–6 colour values
  Character: none ／ hands and back only ／ frame library <path> (AI-generated frames)
  Flat-cartoon narrow exception: when Style starts with 37_rick_morty or 52_south_park,
  write Character as "original semantic SVG…"
  Allow blue-purple: <reason> (optional, only when the user explicitly asked for blue-purple)
Then a markdown table (template and worked example: references/storyboard-template.md), one row per shot,
with the columns:
  Time ｜ Subject ｜ Action ｜ Camera ｜ On-screen text ｜ Method (optional, recommended) ｜ Tags (optional)
The Chinese keys and column names work too (画风/色板/角色, 时间段/画面里的物/它在做什么/镜头/屏上字/做法/标签).
Tables inside code fences (```) are not checked. With several tables in one file, only the first
table that has both a subject column and an action column is checked.

Per row:
  ① Subject: not empty, and not merely "title, key point, text, list, label, subtitle, card,
       background, frame, icon"; and not an empty picture ("empty shot, empty scene, flat colour,
       black frame, black screen, all black, gradient backdrop")                                  → red
  ② Action: not empty, and not merely a catch-all verb ("appears, displays, shows, fades in…")     → red
  ③ On-screen text ≤ 8 characters (one per CJK character, one per run of Latin letters or digits)   → red
  ④ The first shot must not be text-led (subject is a title/word, on-screen text ≥ 7, or the method
       is y5 kinetic text)                                                                         → red
  ⑥ One shot is 2–6 s; 6–8 s or under 2 s → amber; over 8 s → red; more than a fifth of the shots
       at 6–8 s → red
  ⑦ Three consecutive shots with the same camera move (Stop and Lateral truck do not count) → amber
  ⑮ Three consecutive push-ins in a row (slow, plain, fast, slam, zoom in — mixed also counts) → amber
  ⑧ The last shot must not be text-led (centred quote card, pure type card; same test as ④)        → red
  ⑪ A middle shot that is text-led and carries a number (a standalone number card)                 → amber
  ⑨ With --script: Arabic numerals in the on-screen text (percentages, years, numbers with units)
       must be findable in the script                                                                 → red
     (Chinese numerals in the script count too: 「百分之六十」= 60%, 「十五点二倍」= 15.2,
     「二零二五年」= 2025)
  ⑩ With a Tags column: more than 3 tags in one shot                                                → amber
Whole table:
  ⑤ Text-led shots ≤ 30%                                                                           → red
  Method column (only when written): the same parameterised clip (the same .json) totalling over
      8 s → red; more than 2 clip grammars (a collage) → red
  ⑫ Style lock: any of the Style / Palette / Character lines missing                               → red
  ⑬ Palette: values inside the blue-purple band (hue 225°–300°, saturation ≥ 0.30) → red (amber
      when "Allow blue-purple" is written); more than 6 colours → amber
  ⑭ Character: a character line of code-drawn figures ／ chibi ／ robots → red; the subject column
      names a robot, figure, stick figure, mascot or cartoon person while the character line is not
      a frame library → red; y4 used while the character line is not a frame library → red;
      coins or little balls given a face → amber
  ⑯ Accent moves (fast push-in, slam in, whip) on more than a third of the shots → amber
  Time spans that do not join up, and a table with no camera move at all (nothing but Stop and Cut)
      → amber

Exit code: 1 with any red light; 0 with only amber or all green; 2 when the file cannot be read or
no table is found. Standard library only.
"""
import re
import sys
from pathlib import Path

RED, YELLOW, GREEN = "RED", "YELLOW", "GREEN"

# ① Subject: after removing these words, the measure words, the position words, the colours and the
# punctuation, if nothing is left the shot has no subject. Chinese and English entries both apply.
ABSTRACT = sorted("""标题 副标题 小标题 大标题 主标题 要点 文字 文本 大字 字 列表 清单 标签 字幕 卡片 字卡 背景 底色 白底 黑底
纯色 画面 图标 icon 空镜 空景 空画面 空屏 黑场 黑屏 白屏 全黑 全白 暗场 留白 渐变底 渐变 关键词 金句 口号 标语 总结 结论 概念 内容 信息 元素 东西 示意图 示意 图片 图 白板 黑板 页面 版面 动画 效果
文案 段落 句子 bullet 圆点 符号 编号 序号 箭头 线条 形状 方块 色块 渐变 光斑 粒子 装饰
title subtitle headline subhead key point key points bullet bullets text copy big type list lists label labels tag tags caption captions card cards
background backdrop bg frame frames empty frame empty scene empty shot flat colour flat color solid colour solid color gradient gradient backdrop
icon icons image images picture pictures graphic graphics diagram diagrams keyword keywords quote slogan tagline summary conclusion concept concepts content information element elements
page layout animation effect effects placeholder canvas screen mockup mock-up thumbnail slide slides""".split(), key=len, reverse=True)
FILLER = re.compile(r"[\d一二三四五六七八九十两几个条张行句段组页块排些堆串的和与及跟或上下左右中里边侧旁内外前后大小新白黑红蓝绿黄灰橙紫色底空"
                    r"、，,。.;；:：/／+＋&＆\s（）()\[\]【】「」『』“”\"'‘’\-—–~～·…|]"
                    r"|\b(?:a|an|the|this|that|these|those|some|any|all|just|only|and|or|of|with)\b", re.I)
# ④ If the subject column contains these words, the shot counts as text-led.
TEXTY = re.compile(r"标题|文字|文本|要点|列表|清单|字幕|大字|关键词|金句|口号|标语|字卡|bullet|字$|^字"
                   r"|(?<![a-z0-9])(?:titles?|headlines?|sub-?titles?|key ?points?|bullet(?:s)?|text|copy|lists?|labels?|captions?|cards?|big type|keywords?|quotes?|slogans?|taglines?|type card)(?![a-z0-9])", re.I)
# ② Action: after removing these modifiers, only catch-all verbs left means "no action".
WEAK = sorted("""出现 显示 展示 呈现 浮现 淡入 淡出 渐显 弹出 出来 列出 亮起 停留 停住 静止 不动 保持 摆着 放着 存在 显现 罗列 排列 介绍 说明 讲解
解释 强调 标注 写出 打出 入场 出场
appears appear appearing displays display displayed shows show showing shown fades fade
fade in fades in fade out fades out pops up pop up pops pops in holds hold holding lists list listed
presents presented is shown is displayed is presented becomes visible visible enters enter exits exit
stands sits sits there""".split(), key=len, reverse=True)
ACT_FILLER = re.compile(r"[\d一二三四五六七八九十两几个条张行句段组页块排些堆串的地着了过和与及跟或也都再又并、，,。.;；:：/／+＋\s（）()「」“”\"'\-—–~～…|]"
                        r"|逐条|依次|一一|逐个|逐一|逐渐|渐渐|慢慢|缓缓|然后|开始|同时|接着|陆续|一起|一下|画面|屏幕|上"
                        r"|(?<![a-z0-9])(?:the|a|an|and|or|of|to|in|into|onto|on|at|by|with|from|as|then|while|when|is|are|was|were|be|been|its|it|this|that|these|those|out|up|down|over|under|back|again|now|still|slowly|gently|away|across|through|along|around|toward|towards|itself|their|his|her|them|they|each|one|two|three|four|five|six|seven|eight|nine|ten)(?![a-z0-9])", re.I)
# Camera column vocabulary: 停／缓推／拉远／横移／快推／砸入／切 (甩 = whip pan). Stop ／ Slow push-in ／
# Pull back ／ Lateral truck ／ Fast push-in ／ Slam in ／ Cut. Uses and durations: references/camera-language.md
CAM_MOVE = ("缓推", "拉远", "拉开", "横移", "快推", "砸入", "推近", "推", "甩", "移",
            "slow push", "push in", "push-in", "push", "pull back", "pull-back", "pull out", "pull-out",
            "lateral truck", "truck", "pan", "fast push", "slam", "whip", "zoom", "dolly")
CAM_IN = ("缓推", "快推", "推近", "砸入", "慢推", "推进", "推镜", "推", "zoom in", "zoom-in", "zoomin",
          "push in", "push-in", "push", "slow push", "fast push", "slam", "zoom")
CAM_ACCENT = ("快推", "砸入", "甩", "fast push", "slam", "whip")
# ⑦ Moves that may repeat without the picture going stale: Stop and Lateral truck.
CAM_STILL = ("停", "横移", "stop", "lateral truck", "truck", "pan")
# ① Subject column left with only these words: an empty picture, not a layout element — the fix differs.
EMPTY_SCENE = re.compile(r"空镜|空景|空画面|空屏|黑场|黑屏|白屏|全黑|全白|暗场|留白|纯色|渐变|^背景$|^底色$|^[黑白]底$"
                         r"|empty (?:shot|scene|frame|screen)|blank (?:shot|scene|frame|screen)|black (?:frame|screen)|white (?:frame|screen)"
                         r"|all black|all white|flat colou?r|solid colou?r|plain colou?r|negative space|gradient back(?:drop|ground)?|\bgradients?\b", re.I)
EMPTY_CELL = {"", "-", "—", "–", "无", "空", "（空）", "(空)", "/", "／", "——", "none", "n/a", "na", "empty"}
GRAMMAR = re.compile(r"\b([ty][1-9])(?:_[a-z_]+)?\b", re.I)
# ⑫–⑭ Style lock. Chinese keys (画风／色板／角色／允许蓝紫) and English keys (Style ／ Palette ／
# Character ／ Allow blue-purple) are both accepted; both normalise to one internal name.
LOCK = re.compile(r"^\s*[-*]?\s*(?:\*\*)?(画风|色板|角色|允许蓝紫|style(?:\s*lock)?|palette|colou?r palette|character|cast|allow(?:ed)?\s+blue[- ]purple)(?:\*\*)?\s*[:：]\s*(?:\*\*)?\s*(.+?)\s*$", re.I)
LOCK_KEY = {"画风": "style", "style": "style", "style lock": "style",
            "色板": "palette", "palette": "palette", "color palette": "palette", "colour palette": "palette",
            "角色": "character", "character": "character", "cast": "character",
            "允许蓝紫": "allow_bp", "allow blue-purple": "allow_bp", "allowed blue-purple": "allow_bp"}
PALETTES = {"paper", "poster", "ink", "navy", "bauhaus", "snow", "wood", "chalk",
            "纸本", "海报黄", "深墨", "海军", "包豪斯", "雪原", "暖木", "黑板"}
HEX = re.compile(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
FLAT_STYLE = re.compile(r"^(?:37_rick_morty|52_south_park)(?=$|[\s：:，,；;·（(])", re.I)
CHAR_BAD = re.compile(r"代码画|手写|svg|Q\s*版|q\s*版|小人|机器人|火柴人|卡通人"
                      r"|code[- ]drawn|chibi|robot|stick figure|cartoon (?:person|figure|character)|mascot", re.I)
CHAR_FRAMES = re.compile(r"帧库|frame\s*(?:library|lib|pack)|frames|\.png|/", re.I)
CHAR_NONE = re.compile(r"无|没有|不出人|不出脸|只出手|手|背影|剪影|none|no (?:people|person|face|faces|character)|hands only|hands and back|back of (?:the )?head|silhouette", re.I)
OBJ_CHAR = re.compile(r"机器人|小人|火柴人|吉祥物|卡通人|Q\s*版|q\s*版"
                      r"|robot|chibi|stick figure|mascot|cartoon (?:person|figure|character|guy)|cut[- ]out figure", re.I)
OBJ_FACE = re.compile(r"(笑脸|表情|长脸|眼睛|五官).{0,6}(金币|硬币|小球|球|离子|电子|粒子|分子)|(金币|硬币|小球|离子|电子|粒子|分子).{0,6}(笑脸|表情|长脸|眼睛|五官)"
                      r"|(smiley|smiling face|\bfaces?\b|eyes).{0,24}(coins?|balls?|dots?|ions?|electrons?|particles?|molecules?|spheres?)"
                      r"|(coins?|balls?|dots?|ions?|electrons?|particles?|molecules?|spheres?).{0,24}(smiley|smiling face|\bfaces?\b|eyes)", re.I)


def perform_read_lock(text, table_line_value=None):
    """The style lock lines outside the table: {style, palette, character, allow_bp}. Lines inside a
    code fence do not count; when one key is written several times, the line closest to the table above
    it wins (lines below the table are only used when nothing above it exists)."""
    before, after, fence = {}, {}, False
    for i, ln_value in enumerate(text.splitlines(), 1):
        if ln_value.strip().startswith("```"):
            fence = not fence; continue
        m = None if fence else LOCK.match(ln_value)
        if not m: continue
        key = LOCK_KEY.get(re.sub(r"\s+", " ", m.group(1).strip().lower()), m.group(1).strip())
        lookup_value = m.group(2).strip().strip("*").strip()
        if table_line_value is None or i < table_line_value: before[key] = lookup_value
        else: after.setdefault(key, lookup_value)
    return {**after, **before}


def perform_blue_purple_hex(h):
    h = h if len(h) == 6 else "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
    maximum_value, minimum_value = max(r, g, b), min(r, g, b); d = maximum_value - minimum_value
    if d == 0 or maximum_value == 0: return False
    hue = (((g - b) / d) % 6 if maximum_value == r else (b - r) / d + 2 if maximum_value == g else (r - g) / d + 4) * 60
    return 225 <= hue <= 300 and d / maximum_value >= 0.30 and 0.06 <= maximum_value <= 0.90


def trim_cells(line):
    s = line.strip().replace("｜", "|")
    if s.startswith("|"): s = s[1:]
    if s.endswith("|"): s = s[:-1]
    return [c.strip() for c in s.split("|")]


def looks_obj_head(h):
    """Header cell that names the subject column: 物 / Subject / Object / Thing / Item."""
    hl_value = h.lower()
    return "物" in h or any(width_extent in hl_value for width_extent in ("subject", "object", "thing", "item", "prop"))


def looks_act_head(h):
    """Header cell that names the action column: 做什么 / 动作 / Action / Does / Doing."""
    hl_value = h.lower()
    return "做什么" in h or "动作" in h or any(width_extent in hl_value for width_extent in ("action", "does", "doing", "behaviour", "behavior"))


def locate_table(text):
    """Return (header, rows[(line number, cells)]). Code fences are skipped; the first table that has
    both a subject column and an action column wins."""
    lines, fence, i = text.splitlines(), False, 0
    while i < len(lines):
        ln_value = lines[i]
        if ln_value.strip().startswith("```"):
            fence = not fence; i += 1; continue
        if not fence and ln_value.strip().startswith(("|", "｜")) and i + 1 < len(lines) and re.match(r"^\s*[|｜]?\s*:?-{2,}", lines[i + 1]):
            head = trim_cells(ln_value)
            rows, inner_cursor = [], i + 2
            while inner_cursor < len(lines) and lines[inner_cursor].strip().startswith(("|", "｜")):
                rows.append((inner_cursor + 1, trim_cells(lines[inner_cursor]))); inner_cursor += 1
            if any(looks_obj_head(h) for h in head) and any(looks_act_head(h) for h in head):
                return head, rows
            i = inner_cursor; continue
        i += 1
    return None, []


def columns(head):
    column_value = {}
    for k, h in enumerate(head):
        hl_value = h.lower()
        if ("时间" in h or "time" in hl_value or "span" in hl_value or "duration" in hl_value) and "time" not in column_value: column_value["time"] = k
        elif looks_obj_head(h) and "obj" not in column_value: column_value["obj"] = k
        elif looks_act_head(h) and "act" not in column_value: column_value["act"] = k
        elif ("镜头" in h or "camera" in hl_value or "shot" in hl_value or "move" in hl_value) and "cam" not in column_value: column_value["cam"] = k
        elif ("标签" in h or "tag" in hl_value or "label" in hl_value) and "tags" not in column_value: column_value["tags"] = k
        elif ("字" in h or "on-screen text" in hl_value or "text" in hl_value or "caption" in hl_value or "subtitle" in hl_value) and "text" not in column_value: column_value["text"] = k
        elif ("做法" in h or "method" in hl_value or "how" in hl_value or "build" in hl_value) and "how" not in column_value: column_value["how"] = k
    return column_value


def interpret_t(tok_value):
    tok_value = tok_value.strip()
    if ":" in tok_value:
        m, s = tok_value.split(":", 1)
        return int(m) * 60 + float(s)
    return float(tok_value)


def interpret_span(cell):
    num_entries = re.findall(r"\d+:\d+(?:\.\d+)?|\d+(?:\.\d+)?", cell)
    if len(num_entries) < 2: return None
    a, b = interpret_t(num_entries[0]), interpret_t(num_entries[1])
    return (a, b) if b > a else None


def clean_cell(c):
    c = re.sub(r"<br\s*/?>", " ", c or "")
    return c.strip().strip("`*_").strip()


def looks_empty(c):
    return clean_cell(c).lower() in EMPTY_CELL


def trim_tokens(s, words):
    """Remove every token from s. ASCII (English) tokens are removed on word boundaries so "text"
    does not eat "texture"; CJK tokens are removed as plain substrings, exactly as before."""
    for width_extent in words:
        width_extent = width_extent.lower()
        if width_extent.isascii() and any(c.isalpha() for c in width_extent):
            s = re.sub(r"(?<![a-z0-9])" + re.escape(width_extent) + r"(?![a-z0-9])", "", s)
        else:
            s = s.replace(width_extent, "")
    return s


def perform_obj_residue(obj):
    s = clean_cell(obj).lower()
    return FILLER.sub("", trim_tokens(s, ABSTRACT))


def perform_act_residue(act, obj=""):
    """What is left after removing the catch-all verbs, the layout words and the nouns from the subject
    column. 「要点逐条出现」 and 「孢子出现」, or "The bullets appear" and "The spore appears", leave nothing."""
    s = clean_cell(act).lower()
    for width_extent in sorted((elapsed_seconds for elapsed_seconds in FILLER.split(clean_cell(obj).lower()) if len(elapsed_seconds) >= 2), key=len, reverse=True): s = s.replace(width_extent, "")
    s = trim_tokens(s, WEAK + ABSTRACT)
    return ACT_FILLER.sub("", s)


def perform_text_len(elapsed_seconds):
    elapsed_seconds = clean_cell(elapsed_seconds)
    if elapsed_seconds in EMPTY_CELL: return 0
    elapsed_seconds = re.sub(r"[「」『』“”\"'‘’《》]", "", elapsed_seconds)
    return len(re.findall(r"[㐀-鿿]|[A-Za-z0-9][A-Za-z0-9.%°'’]*", elapsed_seconds))


def perform_how_kind(how):
    """Method cell → kind of build: a grammar id (t1…y6), scenes, footage; anything else verbatim."""
    h = clean_cell(how)
    if h in EMPTY_CELL: return None
    m = GRAMMAR.search(h)
    if m: return m.group(1).lower()
    if re.search(r"scenes?|\.js\b|代码画|code[- ]drawn", h, re.I): return "scenes"
    if re.search(r"素材|截图|照片|录像|实拍|原图|原文|录屏|footage|screenshot|screen ?grab|photograph|photos?|video|live action|screen recording|\braw\b", h, re.I): return "footage"
    return h


def perform_clip_name(how):
    m = re.search(r"[^\s|，,：:（）()]+\.json", clean_cell(how))
    return m.group(0) if m else None


def perform_tag_count(cell):
    """Tags column: split on 、, comma, slash and middle dot; with no separator at all, split on spaces."""
    c = clean_cell(cell)
    if c in EMPTY_CELL: return 0
    part_entries = [sample_value for sample_value in re.split(r"[、，,／/;；·•|]+", c) if sample_value.strip()]
    if len(part_entries) <= 1: part_entries = c.split()
    return len(part_entries)


def perform_cam_alts(cell):
    """Alternative camera moves for the ⑦ fix, printed as English (Chinese), minus the one already used."""
    lower_bound = cell.lower()
    out = []
    for en, zh in (("Stop", "停"), ("Slow push-in", "缓推"), ("Pull back", "拉远"), ("Lateral truck", "横移"), ("Cut", "切")):
        if en.lower() in lower_bound or zh in cell: continue
        out.append(f"{en} ({zh})")
    return " ／ ".join(out)


# ⑨ Numbers: on screen only Arabic numerals count (a bare 一 is everywhere in Chinese and would be a
# false positive); the script accepts both notations, better to let one pass than to accuse wrongly.
CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNIT = {"十": 10, "百": 100, "千": 1000}
CN_BIG = {"万": 10 ** 4, "亿": 10 ** 8}
ARABIC = re.compile(r"\d+(?:,\d{3})*(?:\.\d+)?")
CN_NUM = re.compile(r"[零〇一二两三四五六七八九十百千万亿]+(?:点[零〇一二三四五六七八九]+)?")
SRT_NOISE = re.compile(r"\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}|^\s*\d+\s*$", re.M)


def perform_cn_ints(s):
    """A Chinese integer, which may have two readings: 「三百一十八」→ 318, 「二零二五」→ 2025 (read digit
    by digit), 「一千二」→ both 1200 and 1002."""
    if not s: return set()
    if all(ch in CN_DIGIT for ch in s):
        return {int("".join(str(CN_DIGIT[ch]) for ch in s))}
    total, sect_value, quantity_value, last = 0, 0, None, None
    for ch in s:
        if ch in CN_DIGIT: quantity_value = CN_DIGIT[ch]
        elif ch in CN_UNIT: sect_value += (1 if quantity_value is None else quantity_value) * CN_UNIT[ch]; quantity_value, last = None, CN_UNIT[ch]
        elif ch in CN_BIG: total += (sect_value + (quantity_value or 0)) * CN_BIG[ch]; sect_value, quantity_value, last = 0, None, CN_BIG[ch]
        else: return set()
    out = {total + sect_value + (quantity_value or 0)}
    if quantity_value is not None and last and last > 10 and s[-2] not in "零〇":         # 一千二 = 1200, 三万五 = 35000
        out.add(total + sect_value + quantity_value * last // 10)
    return out


def perform_cn_values(tok_value):
    """Chinese numeral → [(value, decimal places)]."""
    a, _, b = tok_value.partition("点")
    int_entries = perform_cn_ints(a) if a else {0}
    if not b: return [(float(i), 0) for i in int_entries]
    frac = "".join(str(CN_DIGIT[ch]) for ch in b)
    return [(float(f"{i}.{frac}"), len(frac)) for i in int_entries]


def perform_scaled(current_value, dec_value, after):
    """A number followed by 「万／亿／k／M」: accept both the number as written and the number it scales to
    (on screen 1.2 万 = the script saying 一万两千). Returns [(value, decimal places)]."""
    out = [(current_value, dec_value)]
    m = re.match(r"\s*(万|亿|[kK]|[mM](?![a-zA-Z]))", after)
    if m:
        k = {"万": 4, "亿": 8, "k": 3, "K": 3, "m": 6, "M": 6}[m.group(1)]
        out.append((current_value * 10 ** k, dec_value - k))
    return out


def perform_arabic(tok_value):
    elapsed_seconds = tok_value.replace(",", "")
    return float(elapsed_seconds), len(elapsed_seconds.partition(".")[2])


def perform_screen_numbers(text):
    """The numbers in the on-screen text: [(as written, [(value, decimal places)])]."""
    elapsed_seconds = clean_cell(text)
    return [(m.group(0), perform_scaled(*perform_arabic(m.group(0)), elapsed_seconds[m.end():])) for m in ARABIC.finditer(elapsed_seconds)]


def perform_script_numbers(script):
    """The numbers the script says aloud: [(value, tolerance)]. The tolerance follows the precision of the
    spoken number: say 「十五倍」 and 15.2 on screen still matches; say 「十五点二」 and the screen must be 15.2."""
    s = SRT_NOISE.sub(" ", script)
    have = []
    for m in ARABIC.finditer(s):
        have += perform_scaled(*perform_arabic(m.group(0)), s[m.end():])
    for m in CN_NUM.finditer(s):
        for current_value, d in perform_cn_values(m.group(0)):
            have += perform_scaled(current_value, d, s[m.end():])
            if s[m.end():m.end() + 1] == "成": have.append((current_value * 10, d - 1))     # 六成 = 60%
    return {(round(current_value, 6), 0.5 * 10.0 ** -d + 1e-9) for current_value, d in have}


def perform_number_in(val_entries, have):
    return any(abs(sample_value - current_value) <= tolerance_value for sample_value, _ in val_entries for current_value, tolerance_value in have)


def collect_lint_findings(text, script=None):
    """Return a dict: rows (per-shot results), table (whole-table results), verdict, total, texty,
    numbered, script. script is the full narration text (optional); rule ⑨ only runs when it is given."""
    head, raw_payload = locate_table(text)
    if head is None:
        return {"error": "No shot-list table found: need a markdown table whose header has at least a subject column and an action column (tables inside code fences do not count)."}
    column_value = columns(head)
    miss = [n for k, n in (("time", "Time"), ("obj", "Subject"), ("act", "Action"), ("cam", "Camera"), ("text", "On-screen text")) if k not in column_value]
    if miss:
        return {"error": "Shot list is missing columns: " + ", ".join(miss) + ". Columns: Time ｜ Subject ｜ Action ｜ Camera ｜ On-screen text ｜ Method."}
    get = lambda cells, k: cells[column_value[k]] if k in column_value and column_value[k] < len(cells) else ""
    rows, table = [], []
    for n, (lineno_value, cells) in enumerate(raw_payload, 1):
        if all(looks_empty(c) for c in cells): continue
        obj, act, cam, txt, how = (get(cells, k) for k in ("obj", "act", "cam", "text", "how"))
        span = interpret_span(get(cells, "time"))
        r = {"n": len(rows) + 1, "line": lineno_value, "obj": clean_cell(obj), "act": clean_cell(act), "cam": clean_cell(cam),
             "text": clean_cell(txt), "how": clean_cell(how), "span": span, "dur": (span[1] - span[0]) if span else None,
             "chars": perform_text_len(txt), "issues": []}
        failure_flag = r["issues"].append
        if looks_empty(obj):
            failure_flag((RED, "①Subject", "The subject cell is empty", "Name something you could point at on screen and say \"that's it\": a person, a hand, a machine, one concrete thing"))
        elif not perform_obj_residue(obj) and EMPTY_SCENE.search(clean_cell(obj)):
            failure_flag((RED, "①Subject", f"\"{r['obj']}\" is an empty picture (empty shot, flat colour, black frame) — the protagonist is not in the frame", "This shot still needs the protagonist or the main object doing something; if you want a breath, let the object stop and pull back, do not remove it"))
        elif not perform_obj_residue(obj):
            failure_flag((RED, "①Subject", f"\"{r['obj']}\" is not a thing, it is a layout element", "Behind every key point there is something doing something — draw it: \"three reasons\" → three concrete things, one shot each, each doing one thing"))
        if looks_empty(act):
            failure_flag((RED, "②Action", "The action cell is empty", "Write a verb: falls, cracks open, burrows in, gets cut off"))
        elif not perform_act_residue(act, obj):
            failure_flag((RED, "②Action", f"\"{r['act']}\" is only appears/shows — there is no action", "Write this object's own action: where it comes from, where it goes, what it hits, what it becomes"))
        if r["chars"] > 8:
            failure_flag((RED, "③On-screen text", f"On-screen text is {r['chars']} characters, over 8", "Keep one word or half a sentence; the rest goes to the narration or the subtitles"))
        r["texty"] = bool(TEXTY.search(r["obj"])) or r["chars"] >= 7 or perform_how_kind(how) == "y5"
        if span is None:
            failure_flag((RED, "⑥Duration", f"Time span \"{clean_cell(get(cells, 'time'))}\" cannot be read", "Write it as 0–3 or 0:03–0:07"))
        elif r["dur"] > 8:
            failure_flag((RED, "⑥Duration", f"This shot runs {r['dur']:g} s, over 8 s", "Split it into two or three shots of 2–6 s, each with a new picture or a new camera move"))
        elif r["dur"] > 6:
            failure_flag((YELLOW, "⑥Duration", f"This shot runs {r['dur']:g} s (6–8 s is only allowed for the occasional shot)", "Split it if you can; if not, make one new thing happen inside the shot: the object's next action, a lateral truck to the next object, a pull back to the whole"))
        elif r["dur"] < 2:
            failure_flag((YELLOW, "⑥Duration", f"This shot is only {r['dur']:g} s long", "Insert shots can be short; if the narration cannot finish a sentence here, merge it into the neighbouring shot"))
        if looks_empty(cam):
            failure_flag((YELLOW, "Camera", "The camera cell is empty", "Write one: Stop ／ Slow push-in ／ Pull back ／ Lateral truck ／ Fast push-in ／ Slam in ／ Cut"))
        if "tags" in column_value:
            r["tags"] = perform_tag_count(get(cells, "tags"))
            if r["tags"] > 3:
                failure_flag((YELLOW, "⑩Tags", f"This shot has {r['tags']} tags, crowded together", "At most 3 per shot; the rest goes to the narration or the next shot; pin a tag beside the object it names, not a row of glowing pills"))
        rows.append(r)
    if not rows:
        return {"error": "The shot list is empty: one row per shot under the header."}

    # ④ the first shot
    f = rows[0]
    if f["texty"]:
        f["issues"].append((RED, "④Opening", "The first shot is text-led (title/word)", "Make the first 3 seconds one concrete small scene: a person or an object doing something related to the topic; the title comes one shot later, or not at all"))
    elif f["chars"] >= 4:
        f["issues"].append((YELLOW, "④Opening", f"The first shot already carries {f['chars']} characters of on-screen text", "Let the picture speak first; save the words for the second shot"))
    # ⑧ the last shot
    depth_value = rows[-1]
    if len(rows) > 1 and depth_value["texty"]:
        depth_value["issues"].append((RED, "⑧Ending", "The last shot is text-led (a centred quote card / a pure type card)",
                            "Land the ending on an action of the protagonist or the main object: into a pocket, closing a book, pulling back to the whole; text can sit on an object in the frame, not on a card of its own"))
    # ⑪ a number card in the middle: a number raised as its own flat-colour card reads, in blind review,
    # over and over as "a PowerPoint slide got inserted"
    for r in rows[1:-1]:
        if r["texty"] and perform_screen_numbers(r["text"]):
            r["issues"].append((YELLOW, "⑪Number card", "This shot is a standalone number card",
                                "Slam the number onto an object in the world: a phone screen, a battery bar, a price tag, a blackboard, paper; do not raise a full-frame type card on a flat colour"))
    # ⑨ on-screen numbers against the script
    if script is not None:
        have = perform_script_numbers(script)
        for r in rows:
            miss = [tok_value for tok_value, val_entries in perform_screen_numbers(r["text"]) if not perform_number_in(val_entries, have)]
            if miss:
                r["issues"].append((RED, "⑨Numbers", f"On-screen number(s) {' / '.join(miss)} not found in the script — the screen and the narration disagree",
                                    "Check the source, then change the on-screen text to the number the narration says (or change the narration); both must be the same number"))
    # ⑦ three shots in a row with the same camera move
    for k in range(2, len(rows)):
        c = rows[k]["cam"]
        # Stop may repeat, and trucking across one object after another on a desk is normal writing too.
        if c and not looks_empty(c) and not any(width_extent in c.lower() for width_extent in CAM_STILL) and c.lower() == rows[k - 1]["cam"].lower() == rows[k - 2]["cam"].lower():
            alt = perform_cam_alts(c)
            rows[k]["issues"].append((YELLOW, "⑦Camera", f"Three shots in a row are all \"{c}\"", f"Change the middle one: {alt} — pick by what this shot wants the audience to look at"))
    # ⑮ three push-ins in a row: one push per shot turns the whole film into a zoom in, push, zoom in
    # (a 102 s prize film pushed in about 48 times and was judged "too many, too fast, not smooth")
    inward = [any(width_extent in r["cam"].lower() for width_extent in CAM_IN) and "拉" not in r["cam"] and "out" not in r["cam"].lower() for r in rows]
    for k in range(2, len(rows)):
        if inward[k] and inward[k - 1] and inward[k - 2] and not any(i[1] == "⑦Camera" for i in rows[k]["issues"]):
            rows[k]["issues"].append((YELLOW, "⑮Push-in", "Three shots in a row push inward", "After pushing in there has to be a way back out: make the middle one Stop, Pull back or Lateral truck, or hard-cut to another shot scale; if the footage is already moving, hold still"))
    # time spans must join up
    for k in range(1, len(rows)):
        a, b = rows[k - 1]["span"], rows[k]["span"]
        if a and b and abs(b[0] - a[1]) > 0.05:
            rows[k]["issues"].append((YELLOW, "Time span", f"The previous shot ends at {a[1]:g}s, this one starts at {b[0]:g}s", "Join them up, or say that an empty shot sits here"))

    n = len(rows)
    texty = [r["n"] for r in rows if r["texty"]]
    if len(texty) / n > 0.30:
        table.append((RED, "⑤Text share", f"Text-led shots {len(texty)}/{n} ({len(texty) / n:.0%}), over 30%: shot(s) {' / '.join(map(str, texty))}",
                      "Take half of them and replace the words with an object doing something; words belong to the narration and the subtitles"))
    long_ = [r["n"] for r in rows if r["dur"] and 6 < r["dur"] <= 8]
    if len(long_) > max(1, n // 5):
        table.append((RED, "⑥Duration", f"{len(long_)} shots run 6–8 s (shot(s) {' / '.join(map(str, long_))}); only the occasional one is allowed",
                      "Split them; 2–6 s per shot"))
    if not any(any(width_extent in r["cam"].lower() for width_extent in CAM_MOVE) for r in rows):
        table.append((YELLOW, "Camera", "No camera move anywhere in the table — nothing but Stop and Cut", "The delivery gate measures movement inside the shot, and all-stop is usually a red light; wherever the audience's eye has to be carried, add a slow push-in, a lateral truck or a pull back (the object's own motion counts as movement too)"))
    acc = [r["n"] for r in rows if any(width_extent in r["cam"].lower() for width_extent in CAM_ACCENT)]
    if n >= 6 and len(acc) * 3 > n:
        table.append((YELLOW, "⑯Accent", f"Fast push-in / slam in / whip used on {len(acc)}/{n} shots (shot(s) {' / '.join(map(str, acc))}) — too many accents means no accent",
                      "Keep them for the reveal, the reversal, the key number; make the rest slow push-in, lateral truck, pull back or stop"))
    total = sum(r["dur"] or 0 for r in rows)
    if "how" in column_value:
        clip_entries = {}
        for r in rows:
            c = perform_clip_name(r["how"])
            if c: clip_entries.setdefault(c, []).append(r)
        for c, rs in clip_entries.items():
            s = sum(r["dur"] or 0 for r in rs)
            if s > 8:
                table.append((RED, "Method", f"Parameterised clip {c} holds {s:g} s (shot(s) {' / '.join(str(r['n']) for r in rs)})",
                              "A single parameterised clip runs at most 8 s; held longer it reads as one more PPT slide. Split it into several specs and change the method in between"))
        grams = sorted({k for k in (perform_how_kind(r["how"]) for r in rows) if k and GRAMMAR.fullmatch(k)})
        if len(grams) > 2:
            table.append((RED, "Method", f"{len(grams)} clip grammars used ({', '.join(grams)}) — stitched together that is several styles",
                          "At most 2 clip grammars per film, every spec writing the same theme; draw the remaining shots with scenes on the same palette, or use real footage full frame"))
        empty_how = [r["n"] for r in rows if perform_how_kind(r["how"]) is None]
        if empty_how:
            table.append((YELLOW, "Method", f"No method written for shot(s) {' / '.join(map(str, empty_how))}", "Say which grammar builds it (shot-01.json), scenes/<id>.js, or footage"))
    else:
        table.append((YELLOW, "Method", "No Method column, so a single clip holding too long and the number of grammars cannot be checked", "Add the column: y2 clip shot-01.json ／ scenes/<id>.js ／ footage photo"))

    # ⑫–⑭ style lock: one visual language for the whole film, no blue-purple, and a character either
    # detailed or never showing a face
    lock = perform_read_lock(text, raw_payload[0][0] - 2 if raw_payload else None)
    miss = [k for k in ("style", "palette", "character") if not lock.get(k)]
    if miss:
        table.append((RED, "⑫Style lock", f"Missing above the table: {' / '.join(miss)}", "Write three lines above the table — Style: one sentence, used for the whole film; Palette: a palette name or 3–6 colour values (references/palette.md); "
                      "Character: none ／ hands and back only ／ frame library <path> (references/character-detail.md)"))
    pal = lock.get("palette", "")
    if pal:
        hexes = HEX.findall(pal)
        named_value = any(n in pal for n in PALETTES)
        bp = [f"#{h}" for h in hexes if perform_blue_purple_hex(h)]
        if bp:
            table.append((YELLOW if lock.get("allow_bp") else RED, "⑬Palette", f"Palette contains blue-purple: {', '.join(bp)}" + (" (reason for allowing blue-purple is written)" if lock.get("allow_bp") else ""),
                          "Swap in a set from references/palette.md, or move these values out of hue 225°–300°; write \"Allow blue-purple: <reason>\" only when the user asked for blue-purple"))
        if len(hexes) > 6:
            table.append((YELLOW, "⑬Palette", f"Palette has {len(hexes)} colours", "3–6 colours per film: ground, surface, main type, secondary type, one or two accents"))
        if not hexes and not named_value:
            table.append((YELLOW, "⑬Palette", f"Palette \"{pal}\" is neither a palette name nor colour values", "Write a name from references/palette.md, or 3–6 #hex values"))
    ch = lock.get("character", "")
    frames = bool(ch and CHAR_FRAMES.search(ch))
    # Only the explicitly selected, documented flat-character routes; y4 still needs frames.
    flat_svg_value = bool(FLAT_STYLE.search(lock.get("style", ""))
                    and re.match(r"原创语义\s*SVG|original semantic\s*SVG", ch, re.I)
                    and not re.search(r"真人|写实|real person|live action|photoreal", ch, re.I))
    if ch and CHAR_BAD.search(ch) and not (frames or flat_svg_value):
        table.append((RED, "⑭Character", f"Character line says \"{ch}\": code-drawn figures and robots are retired", "With image generation, make AI frames (references/10-characters.md); without it, show only hands, a back, a silhouette, or no person at all"))
    for r in rows:
        if OBJ_CHAR.search(r["obj"]) and not (frames or flat_svg_value):
            r["issues"].append((RED, "⑭Character", f"The subject column says \"{OBJ_CHAR.search(r['obj']).group(0)}\", but the character line is not a frame library",
                                "Use a hand, a back or an object in this shot; if a character has to appear, build a frame library first (references/character-detail.md)"))
        if OBJ_FACE.search(r["obj"] + r["act"]):
            r["issues"].append((YELLOW, "⑭Character", "A coin, a little ball or an ion was given a face", "Draw a thing as a thing: carry it with shape, colour and motion, no expressions"))
        if perform_how_kind(r["how"]) == "y4" and not frames:
            r["issues"].append((RED, "⑭Character", "y4 needs a character frame library, but the character line is not one", "Switch to y2/y5, or tell it with hands and objects in scenes; with image generation, build the frame library first"))

    issues = [sample_value for r in rows for sample_value in r["issues"]] + table
    verdict = RED if any(sample_value[0] == RED for sample_value in issues) else YELLOW if issues else GREEN
    numbered = [r["n"] for r in rows if perform_screen_numbers(r["text"])]
    return {"rows": rows, "table": table, "verdict": verdict, "total": total, "texty": texty,
            "script": script is not None, "numbered": numbered}


def report_text(res):
    if "error" in res: return [res["error"]]
    L = []
    for r in res["rows"]:
        light = RED if any(sample_value[0] == RED for sample_value in r["issues"]) else YELLOW if r["issues"] else GREEN
        span = f"{r['span'][0]:g}–{r['span'][1]:g}s" if r["span"] else "?"
        L.append(f"[{light}] shot {r['n']}  {span:<10} {r['obj'][:18]}")
        for lv, tag, what, fix in r["issues"]:
            L.append(f"      [{lv}] {tag}: {what} Fix: {fix}")
    L.append("")
    L.append(f"Table: {len(res['rows'])} shots, {res['total']:g} s, {len(res['texty'])} text-led")
    for lv, tag, what, fix in res["table"]:
        L.append(f"  [{lv}] {tag}: {what} Fix: {fix}")
    L.append("")
    L.append({RED: "Verdict: RED. Fix the shot list and re-run this command; do not start writing code until the red lights are gone.",
              YELLOW: "Verdict: AMBER. You can start; think each amber item through and write the reason into the delivery notes, one by one.",
              GREEN: "Verdict: GREEN. You can start."}[res["verdict"]])
    if not res.get("script") and res.get("numbered"):
        L.append(f"Shot(s) {' / '.join(map(str, res['numbered']))} carry numbers on screen: add --script script.txt to check they are the same numbers the narration says.")
    L.append("The machine cannot check, so check yourself: whether one concrete example carries the whole film and the style stays one style; whether adjacent shots differ in composition; whether the first 3 seconds are a small scene rather than the topic.")
    return L


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if any(a in ("-h", "--help") for a in argv):
        print(__doc__); return 0
    span_length = None
    if "--script" in argv:
        k = argv.index("--script")
        if k + 1 >= len(argv):
            print("--script needs a script path after it", file=sys.stderr); return 2
        span_length = Path(argv[k + 1]); del argv[k:k + 2]
    if len(argv) != 1:
        print(__doc__); return 2
    input_path = Path(argv[0])
    try:
        text = input_path.read_text(encoding="utf-8")
        script = span_length.read_text(encoding="utf-8") if span_length else None
    except OSError as e:
        print(f"Cannot read {e.filename}: {e.strerror}", file=sys.stderr); return 2
    res = collect_lint_findings(text, script)
    print("\n".join(report_text(res)))
    if "error" in res: return 2
    return 1 if res["verdict"] == RED else 0


if __name__ == "__main__":
    sys.exit(main())
