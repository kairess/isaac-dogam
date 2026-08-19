# 아이작 아이템 한글 도감

The Binding of Isaac 의 아이템과 장신구를 **색깔별로 묶어** 보여 주는 한글 도감입니다.

**바로 보기 → https://kairess.github.io/isaac-dogam/**

만든 사람 · [빵형의 개발도상국](https://www.youtube.com/@bbanghyong)

[tboi.com](https://tboi.com) 은 아이템을 Rebirth / Afterbirth / Afterbirth+ / Repentance 로 나눠 놓지만,
게임 도중에 폰으로 찾을 때 기억나는 건 그 아이템이 어느 DLC 소속인지가 아니라 **어떻게 생겼고 무슨 색이었는지**입니다.
그래서 버전 구분을 없애고 아이콘에서 뽑은 대표 색으로만 묶었습니다.

- 아이템 **720개** + 장신구 **188개** + 카드 **97개** = 총 **1005개**
  (카드에는 타로·트럼프·룬·소울스톤이 모두 들어갑니다.)
- 12가지 색깔 묶음 · 한글 이름 · 한글 효과 설명
- 아이템 **등급**(Q0~Q4)과 **등장 장소**(보물방·악마방·천사방·상점 …)
- 초성 검색 (`ㅅㅍㅇㅍ` → 슬픈 양파) · 장소 검색 (`천사방`) · 등급 검색 (`q4`)
- 빌드 도구 없는 정적 페이지. 홈 화면에 추가하면 **통신이 끊겨도** 열립니다.

## 실행

정적 파일이라 아무 웹 서버로나 띄우면 됩니다.

```bash
python3 -m http.server 8000
# http://localhost:8000
```

`main` 에 올리면 [Actions 워크플로](.github/workflows/pages.yml)가 GitHub Pages 로 자동 배포합니다.
경로를 전부 상대경로로 잡아 둬서 `/isaac-dogam/` 같은 하위 경로에서도 그대로 동작합니다.
(서비스워커 때문에 `file://` 로 직접 열면 오프라인 기능만 빠집니다.)

## 데이터 다시 만들기

아이템 데이터와 아이콘은 `tools/` 안의 스크립트로 만듭니다. Python 3 와 Pillow 만 있으면 됩니다.

```bash
pip install pillow
python3 tools/fetch_sources.py     # 원본 텍스트·아이콘 내려받기 (tools/_cache/)
python3 tools/build.py             # items.json + sprite.webp 생성, 검증 리포트 출력
```

게임을 갖고 있다면 아이콘을 본인 설치 폴더에서 가져오는 편이 낫습니다.

```bash
python3 tools/fetch_sources.py --local-icons "…/The Binding of Isaac Rebirth/resources/gfx/items/collectibles"
```

### 스크립트

| 파일 | 하는 일 |
|---|---|
| `tools/fetch_sources.py` | EID 한국어·영어 텍스트와 아이콘 PNG 를 `tools/_cache/` 로 수집 |
| `tools/parse_eid.py` | Lua 텍스트 팩을 정규식으로 읽어 한글 이름·설명으로 병합 |
| `tools/parse_gamedata.py` | 게임 XML 에서 아이템 등급과 등장 장소를 읽음 |
| `tools/extract_colors.py` | 아이콘에서 대표 색을 뽑아 12개 묶음으로 분류 |
| `tools/build.py` | 위를 합쳐 `assets/data/items.json` 과 `assets/icons/sprite.webp` 생성 |

### 색깔 분류를 손보고 싶다면

자동 분류가 눈에 보이는 색과 다를 때가 있습니다. 검수 페이지를 열어 확인하세요.

```bash
open tools/_report/colors.html
```

이상한 항목을 찾으면 `tools/color_overrides.json` 에 적고 다시 빌드하면 됩니다.

```json
{ "item:105": "red", "trinket:12": "brown" }
```

색깔 키는 `red · orange · yellow · green · blue · purple · pink · skin · brown · white · gray · black` 입니다.

### 분류 방식

아이작 스프라이트는 검은 외곽선이 두꺼워서 픽셀 평균을 그냥 내면 전부 탁해집니다.
(슬픈 양파의 단순 평균은 RGB `(71,86,65)` 로, 초록이라기엔 너무 어둡습니다.)

그래서 `tools/extract_colors.py` 는 이렇게 합니다.

1. 반투명한 가장자리와 어두운 외곽선 픽셀을 걷어냅니다.
2. 남은 픽셀을 **진한 색일수록 무겁게** 세어 색상환 히스토그램을 만들고 최빈 색조를 찾습니다.
3. 채도가 거의 없으면 밝기에 따라 흰색 / 회색 / 검정으로 나눕니다.
4. 어두운 주황·노랑은 갈색으로, 흐리고 밝은 주황은 살구색으로 다시 분류합니다.
   (아이작의 살빛이 여기 해당합니다. 그냥 두면 빨강 묶음이 너무 커져 훑어보기 어려워집니다.)

## 출처

- 게임 저작권은 **Nicalis, Inc.** 와 **Edmund McMillen** 에게 있습니다.
  이 저장소는 팬이 만든 비영리 참고 자료이며 공식과 무관합니다.
- 한글 이름과 효과 설명: [External Item Descriptions](https://github.com/wofsauge/External-Item-Descriptions)
  한국어 번역 기여자들. 게임 공식 한국어 명칭을 따릅니다.
- 등급·등장 장소: 게임의 `items_metadata.xml` / `itempools.xml`
  ([isaac-crafting](https://github.com/EliteMasterEric/isaac-crafting) 이 보관한 v1.7.9b 사본)
- 아이템 아이콘: [isaac-save-viewer](https://github.com/Zamiell/isaac-save-viewer) (GPL-3.0)
- 장신구 아이콘: [IsaacWallpaper](https://github.com/NafzorOB/IsaacWallpaper)
- 카드 아이콘: [The Binding of Isaac: Rebirth Wiki](https://bindingofisaacrebirth.wiki.gg) (CC BY-SA)
- 구성 아이디어: [tboi.com (Platinum God)](https://tboi.com)
- 만든 사람: [빵형의 개발도상국](https://www.youtube.com/@bbanghyong)

> EID 저장소에는 라이선스 파일이 없습니다. 출처를 분명히 밝히고 **광고 없이 비영리로** 두는 것을 권합니다.
> 게임 자산을 직접 담고 싶지 않다면 `--local-icons` 로 각자 설치본에서 아이콘을 뽑아 쓰면 됩니다.

## 알려진 한계

- 아이템 ID 13개(43, 59, 61, 235, 587, 613, 620, 630, 648, 662, 666, 718)와 장신구 47번은
  게임에서 쓰지 않는 빈 번호입니다. 아이콘이 없거나 이름이 비어 있어 제외했습니다.
- 한글 이름이 없어 영문 그대로 두는 항목이 7개 있습니다
  (`Undefined`, `IBS`, `TMTRAINER`, `Missing No.`, `'M`, `1up!`, `YO LISTEN!`).
  대부분 원문이 약어이거나 고유명사라 원본 번역 팩에도 한글 표기가 없습니다.
- **등급과 등장 장소는 아이템에만** 붙습니다. 게임 XML 은 장신구 등급을 전부 0 으로 적어 두는데
  실제로 매긴 값이 아니라서, 그대로 보여주면 모든 장신구가 최하 등급인 것처럼 읽혀 뺐습니다.
  카드는 애초에 해당 사항이 없습니다.
- 아이템 23개는 어느 등장 장소에도 들어 있지 않습니다. 특정 보스나 해금으로만 나오는 것들입니다.
- 룬 8개(하갈라즈·제라 등)는 위키에 도트 원본이 아니라 크게 그린 그림만 있어,
  다른 카드와 크기를 맞춰 줄여 넣었습니다. 그래서 화풍이 살짝 다릅니다.
