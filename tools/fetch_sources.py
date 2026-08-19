#!/usr/bin/env python3
"""외부 소스 수집기.

EID 한국어/영어 텍스트 팩과 아이템·장신구 아이콘을 tools/_cache/ 로 내려받는다.
이미 받은 파일은 건너뛰므로 몇 번을 다시 돌려도 안전하다.

    python3 tools/fetch_sources.py                # 기본 (원격에서 전부 수집)
    python3 tools/fetch_sources.py --local-icons "/path/to/resources/gfx/items/collectibles"
                                                  # 보유한 게임 설치 폴더에서 아이템 아이콘 사용
"""
import argparse
import concurrent.futures
import json
import re
import shutil
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "_cache"
TEXT_DIR = CACHE / "text"
ITEM_ICONS = CACHE / "icons" / "item"
TRINKET_ICONS = CACHE / "icons" / "trinket"
CARD_ICONS = CACHE / "icons" / "card"

EID_RAW = "https://raw.githubusercontent.com/wofsauge/External-Item-Descriptions/master/descriptions"

# 게임의 resources XML 사본. 아이템 등급(quality)과 아이템 풀 구성이 들어 있다.
GAMEDATA_RAW = ("https://raw.githubusercontent.com/EliteMasterEric/isaac-crafting"
                "/master/src/crafting_calculator/gamedata/pc/v1.7.9b")

# 카드·룬·소울스톤 그림은 위키의 MediaWiki API 로 찾는다. 파일 이름 규칙이 일정하다.
WIKI_API = "https://bindingofisaacrebirth.wiki.gg/api.php"

TEXT_FILES = {
    "ko_abp.lua": f"{EID_RAW}/ab%2B/ko_kr.lua",
    "ko_rep.lua": f"{EID_RAW}/rep/ko_kr.lua",
    "ko_names.lua": f"{EID_RAW}/names/ko_kr.lua",
    "en_names.lua": f"{EID_RAW}/names/en_us.lua",
    # 등급 · 등장 장소 · 액티브/패시브 구분은 EID 에 없다. 게임이 들고 있는 XML 이 원본이다.
    "items_metadata.xml": f"{GAMEDATA_RAW}/items_metadata.xml",
    "itempools.xml": f"{GAMEDATA_RAW}/itempools.xml",
    "items.xml": f"{GAMEDATA_RAW}/items.xml",
}

SAVE_VIEWER_TREE = "https://api.github.com/repos/Zamiell/isaac-save-viewer/git/trees/main?recursive=1"
SAVE_VIEWER_RAW = "https://raw.githubusercontent.com/Zamiell/isaac-save-viewer/main"
WALLPAPER_TREE = "https://api.github.com/repos/NafzorOB/IsaacWallpaper/git/trees/main?recursive=1"
WALLPAPER_RAW = "https://raw.githubusercontent.com/NafzorOB/IsaacWallpaper/main"

UA = {"User-Agent": "isaac-items-builder/1.0 (+https://github.com/)"}


def get(url: str) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def download(url: str, dest: Path) -> str:
    """이미 있으면 'skip', 새로 받으면 'ok', 실패하면 'fail:<이유>'."""
    if dest.exists() and dest.stat().st_size > 0:
        return "skip"
    try:
        data = get(url)
    except urllib.error.HTTPError as exc:
        return f"fail:{exc.code}"
    except Exception as exc:  # 네트워크 오류 전반
        return f"fail:{type(exc).__name__}"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    return "ok"


def download_many(jobs, label):
    """(url, dest) 목록을 병렬로 내려받고 요약을 출력한다."""
    ok = skipped = 0
    failures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        futures = {pool.submit(download, url, dest): dest for url, dest in jobs}
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result == "ok":
                ok += 1
            elif result == "skip":
                skipped += 1
            else:
                failures.append((futures[future].name, result))
    print(f"  {label}: 새로 받음 {ok} / 이미 있음 {skipped} / 실패 {len(failures)}")
    for name, why in failures[:10]:
        print(f"    ! {name} -> {why}")
    return not failures


def fetch_text():
    print("[1/4] EID 텍스트 팩 · 게임 XML")
    jobs = [(url, TEXT_DIR / name) for name, url in TEXT_FILES.items()]
    return download_many(jobs, "lua")


def fetch_item_icons(local_dir=None):
    print("[2/4] 아이템 아이콘")
    if local_dir:
        src = Path(local_dir).expanduser()
        if not src.is_dir():
            print(f"  ! 로컬 경로를 찾을 수 없음: {src}")
            return False
        ITEM_ICONS.mkdir(parents=True, exist_ok=True)
        copied = 0
        # 게임 파일 이름은 collectibles_001_the_sad_onion.png 형태다. 앞 숫자만 쓴다.
        for png in src.glob("*.png"):
            match = re.search(r"(\d{3,4})", png.name)
            if not match:
                continue
            shutil.copyfile(png, ITEM_ICONS / f"{int(match.group(1))}.png")
            copied += 1
        print(f"  로컬 복사: {copied}개")
        return copied > 0

    tree = json.loads(get(SAVE_VIEWER_TREE))["tree"]
    jobs = []
    for node in tree:
        path = node["path"]
        if not path.startswith("static/img/collectibles/collectibles_"):
            continue
        match = re.search(r"(\d+)\.png$", path)
        if not match:
            continue
        item_id = int(match.group(1))
        if item_id == 0:
            continue
        jobs.append((f"{SAVE_VIEWER_RAW}/{path}", ITEM_ICONS / f"{item_id}.png"))
    return download_many(jobs, "png")


def fetch_trinket_icons():
    """장신구 아이콘은 ID가 아니라 영문 이름으로 저장돼 있어 이름 색인을 함께 남긴다."""
    print("[3/4] 장신구 아이콘")
    tree = json.loads(get(WALLPAPER_TREE))["tree"]
    jobs = []
    index = {}
    for node in tree:
        path = node["path"]
        if not (path.startswith("assets/") and path.endswith(".png")):
            continue
        stem = path.rsplit("/", 1)[-1][:-4]
        index[stem] = f"{stem}.png"
        jobs.append((f"{WALLPAPER_RAW}/{path}", TRINKET_ICONS / f"{stem}.png"))
    ok = download_many(jobs, "png")
    (CACHE / "icons" / "wallpaper_index.json").write_text(
        json.dumps(index, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    return ok


def card_wiki_title(card_id, english, overrides):
    """카드 영문 이름을 위키 파일 이름으로 바꾼다."""
    if str(card_id) in overrides:
        english = overrides[str(card_id)]
    else:
        # 리펜턴스의 역방향 타로는 이름 끝에 ? 가 붙는다. 위키는 "0 - Inverted The Fool" 처럼 적는다.
        # 로마숫자로 시작하는 것만 골라야 한다. "Soul of ???" 같은 이름을 건드리면 안 된다.
        match = re.match(r"^([IVXL0-9]+) - (.+)\?$", english)
        if match:
            english = f"{match.group(1)} - Inverted {match.group(2)}"
    return f"File:Pickup {english} icon.png"


def wiki_image_urls(titles):
    """{제목: 이미지주소} 를 찾는다.

    물음표가 든 제목은 여러 개를 한 번에 물어보면 응답에서 짝을 잃어버린다.
    그런 것만 따로 하나씩 묻는다.
    """
    urls = {}

    def ask(batch):
        query = urllib.parse.urlencode(
            {"action": "query", "titles": "|".join(batch), "prop": "imageinfo",
             "iiprop": "url", "format": "json"}
        )
        data = json.loads(get(f"{WIKI_API}?{query}"))["query"]
        renamed = {n["from"]: n["to"] for n in data.get("normalized", [])}
        pages = {p.get("title"): p for p in data["pages"].values()}
        for title in batch:
            page = pages.get(renamed.get(title, title))
            if page and "imageinfo" in page:
                urls[title] = page["imageinfo"][0]["url"]

    plain = [t for t in titles if "?" not in t]
    for i in range(0, len(plain), 40):
        ask(plain[i : i + 40])
    for title in titles:
        if "?" in title:
            ask([title])
    return urls


def fetch_card_icons():
    print("[4/4] 카드 아이콘")
    names = (TEXT_DIR / "en_names.lua").read_text(encoding="utf-8")
    cards = {
        int(num): value
        for num, value in re.findall(r'\[Card_ID \.\. (\d+)\] = "([^"]*)"', names)
        if value
    }
    overrides = json.loads((ROOT / "card_icon_overrides.json").read_text(encoding="utf-8"))
    overrides = {k: v for k, v in overrides.items() if not k.startswith("_")}

    titles = {card_id: card_wiki_title(card_id, name, overrides)
              for card_id, name in cards.items()}
    urls = wiki_image_urls(sorted(set(titles.values())))

    jobs = []
    unresolved = []
    for card_id, title in sorted(titles.items()):
        if title in urls:
            jobs.append((urls[title], CARD_ICONS / f"{card_id}.png"))
        else:
            unresolved.append(f"{card_id} {cards[card_id]}")
    if unresolved:
        print(f"  ! 위키에서 그림을 못 찾음 {len(unresolved)}건: {', '.join(unresolved[:8])}")
    return download_many(jobs, "png") and not unresolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--local-icons",
        metavar="DIR",
        help="게임 설치 폴더의 resources/gfx/items/collectibles 경로 (아이템 아이콘을 여기서 가져옴)",
    )
    args = parser.parse_args()

    CACHE.mkdir(parents=True, exist_ok=True)
    results = [
        fetch_text(),
        fetch_item_icons(args.local_icons),
        fetch_trinket_icons(),
        fetch_card_icons(),
    ]
    if all(results):
        print("\n수집 완료. 이어서 `python3 tools/build.py` 를 실행하세요.")
        return 0
    print("\n일부 항목을 받지 못했습니다. 네트워크를 확인한 뒤 다시 실행하세요.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
