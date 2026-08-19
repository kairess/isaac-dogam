#!/usr/bin/env python3
"""EID 한국어 텍스트 팩 파서.

EID는 설명을 두 층으로 나눠 관리한다.
  ab+/ko_kr.lua  : 기본 설명 (Afterbirth+ 기준)
  rep/ko_kr.lua  : Repentance 에서 바뀐 항목만 (기본값을 덮어씀)
따라서 둘을 병합해야 전체가 채워진다. 이름은 별도의 names/ko_kr.lua 가 정본이다.

Lua 를 실행하지 않고 정규식으로만 읽는다. 표 형식이 단순하고 고정적이라 그걸로 충분하다.

단독 실행하면 파싱 결과 요약을 출력한다:
    python3 tools/parse_eid.py
"""
import re
import sys
from pathlib import Path

TEXT_DIR = Path(__file__).resolve().parent / "_cache" / "text"

# {"1", "슬픈 양파", "↑ 연사 +0.7"} 와 [1] = {"1", ...} 두 형태를 함께 잡는다.
ENTRY_RE = re.compile(
    r'\{\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"\s*,\s*"((?:[^"\\]|\\.)*)"'
)
MARKUP_RE = re.compile(r"\{\{[^{}]*\}\}")


def read(name):
    path = TEXT_DIR / name
    if not path.exists():
        sys.exit(f"소스가 없습니다: {path}\n먼저 `python3 tools/fetch_sources.py` 를 실행하세요.")
    return path.read_text(encoding="utf-8")


def slice_table(text, start_marker, end_marker):
    """start_marker 부터 end_marker 직전까지 잘라낸다."""
    start = text.find(start_marker)
    if start < 0:
        sys.exit(f"표를 찾지 못했습니다: {start_marker}")
    end = text.find(end_marker, start)
    return text[start : end if end > 0 else len(text)]


def unescape(value):
    return value.replace('\\"', '"').replace("\\\\", "\\")


def clean_desc(raw):
    """EID 마크업을 화면에 쓸 수 있는 줄 목록으로 바꾼다.

    '#' 이 줄바꿈이고, '{{DamageSmall}}' 같은 토큰은 게임 내 아이콘 자리다.
    한국어 원문이 이미 '공격력 +0.5' 처럼 스탯 이름을 글자로 적고 있어 토큰은 군더더기라 지운다.
    증감을 나타내는 ↑ ↓ 는 화면에서 색으로 구분할 수 있게 남긴다.
    """
    text = MARKUP_RE.sub("", unescape(raw))
    lines = []
    for chunk in text.split("#"):
        chunk = re.sub(r"[ \t]+", " ", chunk).strip()
        if chunk:
            lines.append(chunk)
    return lines


def parse_entries(segment):
    """표 조각에서 {ID: (이름, 설명줄들)} 을 뽑는다."""
    out = {}
    for raw_id, name, desc in ENTRY_RE.findall(segment):
        if not raw_id.isdigit():
            continue
        out[int(raw_id)] = (unescape(name).strip(), clean_desc(desc))
    return out


def parse_names(text, prefix):
    """names/*.lua 의 [C_ID .. 12] = "마법의 버섯" 형태를 읽는다."""
    pattern = re.compile(rf'\[{prefix} \.\. (\d+)\]\s*=\s*"((?:[^"\\]|\\.)*)"')
    return {
        int(num): unescape(value).strip()
        for num, value in pattern.findall(text)
        if unescape(value).strip()
    }


def load():
    """모든 소스를 병합해 {'item': {...}, 'trinket': {...}, 'card': {...}} 를 돌려준다.

    각 항목은 {'ko': 한글이름, 'en': 영문이름, 'desc': [줄, ...]} 이다.
    """
    abp = read("ko_abp.lua")
    rep = read("ko_rep.lua")
    ko_names = read("ko_names.lua")
    en_names = read("en_names.lua")

    tables = {
        "item": {
            "base": parse_entries(slice_table(abp, ".collectibles={", ".carBattery")),
            "over": parse_entries(slice_table(rep, "repCollectibles={", "repCarBattery")),
            "ko": parse_names(ko_names, "C_ID"),
            "en": parse_names(en_names, "C_ID"),
        },
        "trinket": {
            "base": parse_entries(slice_table(abp, ".trinkets={", ".cards=")),
            "over": parse_entries(slice_table(rep, "repTrinkets={", "repCards")),
            "ko": parse_names(ko_names, "T_ID"),
            "en": parse_names(en_names, "T_ID"),
        },
        # 게임이 말하는 '카드' 에는 타로, 트럼프, 룬, 소울스톤이 모두 들어간다.
        "card": {
            "base": parse_entries(slice_table(abp, ".cards={", ".pills=")),
            "over": parse_entries(slice_table(rep, "repCards={", "repPills")),
            "ko": parse_names(ko_names, "Card_ID"),
            "en": parse_names(en_names, "Card_ID"),
        },
    }

    result = {}
    for kind, src in tables.items():
        merged = {}
        ids = set(src["base"]) | set(src["over"]) | set(src["ko"]) | set(src["en"])
        for entry_id in sorted(ids):
            # 설명과 인라인 이름은 Repentance 판이 우선한다.
            over_name, over_desc = src["over"].get(entry_id, ("", []))
            base_name, base_desc = src["base"].get(entry_id, ("", []))
            desc = over_desc or base_desc
            # 이름은 정식 명칭표가 정본이고, 없으면 인라인, 그것도 없으면 영문으로 떨어뜨린다.
            english = src["en"].get(entry_id, "")
            korean = src["ko"].get(entry_id) or over_name or base_name or english
            merged[entry_id] = {"ko": korean, "en": english, "desc": desc}
        result[kind] = merged
    return result


def main():
    data = load()
    for kind, entries in data.items():
        no_desc = [i for i, e in entries.items() if not e["desc"]]
        no_ko = [i for i, e in entries.items() if not e["ko"]]
        only_en = [i for i, e in entries.items() if e["ko"] and e["ko"] == e["en"]]
        print(f"{kind}: {len(entries)}개")
        print(f"  설명 없음 {len(no_desc)}  이름 없음 {len(no_ko)}  한글명 대신 영문 사용 {len(only_en)}")
        if no_desc:
            print(f"    설명 없는 ID: {no_desc[:15]}")
    sample = data["item"][1]
    print(f"\n예시 item 1 -> {sample['ko']} / {sample['en']} / {sample['desc']}")
    sample = data["item"][12]
    print(f"예시 item 12 -> {sample['ko']} / {sample['desc']}")


if __name__ == "__main__":
    main()
