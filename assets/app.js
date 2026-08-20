/* 아이작 한글 도감 — 색깔로 묶고, 초성으로 찾는다. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const listEl = $("list");
  const chipsEl = $("chips");
  const emptyEl = $("empty");
  const searchEl = $("q");
  const clearEl = $("clear");
  const sheetEl = $("sheet");
  const backdropEl = $("backdrop");

  const KIND_KO = { item: "아이템", trinket: "장신구", card: "카드" };
  const TYPE_KO = { active: "액티브", passive: "패시브", familiar: "패밀리어" };
  const CHARGE_KO = { timed: "시간 충전", special: "특수 충전" };
  // 등급이 높을수록 밝은 금색으로. 게임 안에서 강한 아이템을 고를 때 쓰는 눈금이다.
  const QUALITY_HEX = ["#7b8291", "#5d8ac0", "#4fa06a", "#c9903a", "#e0c04a"];

  let DATA = null;
  let cards = [];          // {entry, node} — 화면에 올려둔 카드. 색 순서 그대로다
  let visible = [];        // 지금 걸러내고 남은 카드. 칩 따라오기가 이걸 반씩 접어 훑는다
  let state = { kind: "all", quality: "all", query: "" };
  let setMembers = new Map();   // 세트 이름 -> 그 세트에 드는 항목들

  /* ---------- 초성 검색 ----------
     한국어 사용자는 'ㅅㅍㅇㅍ' 처럼 초성만 두들겨 찾는 데 익숙하다.
     한글 음절은 유니코드에서 (초성 * 588) 규칙으로 배열돼 있어 산술로 뽑을 수 있다. */

  const CHO = [
    "ㄱ", "ㄲ", "ㄴ", "ㄷ", "ㄸ", "ㄹ", "ㅁ", "ㅂ", "ㅃ", "ㅅ",
    "ㅆ", "ㅇ", "ㅈ", "ㅉ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ",
  ];

  function chosung(text) {
    let out = "";
    for (const ch of text) {
      const code = ch.charCodeAt(0);
      out += code >= 0xac00 && code <= 0xd7a3
        ? CHO[Math.floor((code - 0xac00) / 588)]
        : ch;
    }
    return out;
  }

  const squeeze = (text) => text.replace(/\s+/g, "").toLowerCase();

  /* ---------- 자료 준비 ---------- */

  function indexEntry(entry) {
    entry._ko = squeeze(entry.ko);
    entry._en = squeeze(entry.en);
    entry._desc = squeeze(entry.desc.join(" "));
    entry._cho = squeeze(chosung(entry.ko));
    // 등장 장소·등급·종류도 검색으로 걸리게 해 둔다.
    // "천사방", "등급4", "q4", "액티브" 가 모두 통한다.
    const extras = (entry.pools || []).join(" ")
      + (entry.quality === undefined ? "" : ` 등급${entry.quality} q${entry.quality}`)
      + (entry.type ? " " + TYPE_KO[entry.type] : "")
      // 패밀리어도 자리로 보면 패시브라 그 말로도 찾을 수 있어야 한다.
      + (entry.type === "familiar" ? " 패시브" : "")
      + (entry.charge ? ` 충전${entry.charge}` : "")
      + (entry.sets || []).map((t) => ` ${t.ko} ${t.en} 변신 세트`).join("");
    entry._extra = squeeze(extras) + squeeze(chosung(extras));
    return entry;
  }

  function matches(entry) {
    if (state.kind !== "all" && entry.kind !== state.kind) return false;
    if (state.quality !== "all" && String(entry.quality) !== state.quality) return false;
    const q = state.query;
    if (!q) return true;
    return entry._ko.includes(q) || entry._en.includes(q) || entry._cho.includes(q)
        || entry._desc.includes(q) || entry._extra.includes(q);
  }

  function groupSets() {
    for (const entry of DATA.entries) {
      for (const one of entry.sets || []) {
        if (!setMembers.has(one.ko)) setMembers.set(one.ko, []);
        setMembers.get(one.ko).push(entry);
      }
    }
  }

  /* ---------- 그리기 ---------- */

  /* 스프라이트 칸 번호만 넘긴다. 실제 픽셀 위치는 CSS 가 --cell 을 보고 계산한다. */
  function placeIcon(node, entry) {
    const { cols } = DATA.sprite;
    node.style.setProperty("--sx", entry.idx % cols);
    node.style.setProperty("--sy", Math.floor(entry.idx / cols));
  }

  /* 자료는 첫 아이콘(가장 새빨간 것)부터 마지막(가장 새까만 것)까지
     색이 이어지도록 이미 줄 세워져 있다. 그래서 묶음별로 칸을 나누지 않고
     한 판에 쭉 깐다. 중간에 칸을 끊으면 거기서 줄이 새로 시작해 흐름이 끊긴다. */
  function build() {
    const grid = document.createElement("div");
    grid.className = "grid";
    for (const entry of DATA.entries) {
      const button = document.createElement("button");
      button.type = "button";
      button.title = entry.ko;
      const icon = document.createElement("span");
      icon.className = "icon";
      placeIcon(icon, entry);
      button.append(icon);
      button.addEventListener("click", () => open(entry));
      grid.append(button);
      cards.push({ entry, node: button });
    }
    listEl.append(grid);
  }

  function buildChips() {
    const counts = new Map();
    for (const entry of DATA.entries) {
      counts.set(entry.color, (counts.get(entry.color) || 0) + 1);
    }
    const make = (key, label, dot, count) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.color = key;
      button.innerHTML =
        (dot ? `<span class="dot" style="background:${dot}"></span>` : "") +
        `${label}<span class="n">${count}</span>`;
      button.addEventListener("click", () => jumpTo(key));
      chipsEl.append(button);
    };
    make("all", "전체", "", DATA.entries.length);
    // 칩의 점 색은 그 묶음의 실제 대표색 평균이라, 화면 색과 아이콘 색이 따로 놀지 않는다.
    for (const bucket of DATA.buckets) {
      const group = DATA.entries.filter((e) => e.color === bucket.key);
      if (!group.length) continue;
      make(bucket.key, bucket.ko, averageHex(group), group.length);
    }
  }

  function buildQualityChips() {
    const counts = new Map();
    for (const entry of DATA.entries) {
      if (entry.quality === undefined) continue;
      counts.set(entry.quality, (counts.get(entry.quality) || 0) + 1);
    }
    const wrap = $("quals");
    const make = (key, label, dot, count) => {
      const button = document.createElement("button");
      button.type = "button";
      button.dataset.quality = key;
      button.innerHTML =
        (dot ? `<span class="dot" style="background:${dot}"></span>` : "") +
        `${label}<span class="n">${count}</span>`;
      button.addEventListener("click", () => {
        // 같은 등급을 다시 누르면 등급 조건을 푼다. 칸을 따로 두지 않아도 되게.
        state.quality = state.quality === key ? "all" : key;
        apply();
        window.scrollTo({ top: 0, behavior: "smooth" });
      });
      wrap.append(button);
    };
    make("all", "등급 전체", "", DATA.entries.filter((e) => e.quality !== undefined).length);
    for (const q of [...counts.keys()].sort((a, b) => b - a)) {
      make(String(q), `Q${q}`, QUALITY_HEX[q], counts.get(q));
    }
  }

  function averageHex(group) {
    let r = 0, g = 0, b = 0;
    for (const entry of group) {
      r += parseInt(entry.hex.slice(1, 3), 16);
      g += parseInt(entry.hex.slice(3, 5), 16);
      b += parseInt(entry.hex.slice(5, 7), 16);
    }
    const n = group.length;
    const hex = (v) => Math.round(v / n).toString(16).padStart(2, "0");
    return `#${hex(r)}${hex(g)}${hex(b)}`;
  }

  /* ---------- 걸러내기 ---------- */

  function apply() {
    visible = [];
    for (const card of cards) {
      const ok = matches(card.entry);
      card.node.hidden = !ok;
      if (ok) visible.push(card);
    }
    emptyEl.hidden = visible.length > 0;
    spy();

    for (const button of $("quals").children) {
      button.classList.toggle("on", button.dataset.quality === state.quality);
    }
    // 등급은 아이템에만 있다. 장신구·카드만 보는 중이면 등급 줄을 접어 둔다.
    $("quals").hidden = state.kind === "trinket" || state.kind === "card";
    for (const button of document.querySelectorAll(".seg button")) {
      button.classList.toggle("on", button.dataset.kind === state.kind);
    }
    clearEl.hidden = !state.query;
  }

  /* ---------- 색깔 칩: 그 자리로 뛰기 ----------
     아이콘이 색 순서로 한 줄에 이어져 있으니, 색깔은 걸러낼 갈래가 아니라
     띠 위의 위치다. 그래서 칩은 걸러내지 않고 그 자리로 데려다 준다. */

  const barEl = document.querySelector(".bar");

  function barHeight() {
    return barEl.getBoundingClientRect().height;
  }

  /* 고정된 머리말 높이는 검색줄이 접히고 펴짐에 따라 달라진다. 그 값을 CSS 에 넘겨
     두면 scroll-margin-top 이 알아서 자리를 비워, 뛰어간 아이콘이 머리말에 가리지 않는다. */
  function measureBar() {
    document.documentElement.style.setProperty("--bar-h", `${Math.round(barHeight())}px`);
  }

  /* 부드럽게 밀지 않고 바로 옮긴다. 검정까지는 만 오천 픽셀이 넘어서,
     그 거리를 애니메이션으로 흘리면 몇 초를 기다려야 하고 눈도 어지럽다.
     대신 칩에 불이 들어와 지금 어느 색에 서 있는지 알려 준다. */
  function jumpTo(key) {
    if (key === "all") {
      window.scrollTo(0, 0);
      spy();
      return;
    }
    // 검색이나 종류로 걸러 둔 상태면 남아 있는 것 중 첫째로 간다.
    const first = visible.find((card) => card.entry.color === key);
    if (!first) return;
    /* 자리를 직접 계산해 옮기면 안 된다. 화면 밖 칸은 아직 안 그려서 높이를
       어림잡아 두고 있어(content-visibility), 옮기고 나면 그 어림값이 실제 값으로
       바뀌면서 목표가 발밑에서 움직인다. scrollIntoView 는 브라우저가 그 칸을
       먼저 그려 놓고 옮겨 주므로 어긋나지 않는다. */
    measureBar();
    first.node.scrollIntoView({ block: "start" });
    spy();
  }

  /* 지금 화면 맨 위에 걸린 아이콘이 어느 색인지 칩에 표시한다.
     묶음 제목을 없앤 대신 이 칩이 '지금 어디쯤인지'를 알려 준다. */
  let spying = 0;

  function spy() {
    /* 한 줄에 다섯 칸이라 색이 바뀌는 자리는 줄 한가운데에 걸린다. 맨 윗줄로 재면
       파랑으로 뛰어왔는데도 그 줄 왼쪽에 남은 초록이 잡힌다. 화면 3분의 1쯤
       내려온 자리로 재면 지금 보고 있는 색이 제대로 잡힌다. */
    const top = barHeight();
    const line = top + (window.innerHeight - top) * 0.35;
    // 남아 있는 카드는 문서 순서 그대로라 위에서 아래로 정렬돼 있다.
    // 1005개를 매 프레임 재면 스크롤이 밀리니 반씩 접어 가며 찾는다.
    let lo = 0, hi = visible.length - 1, found = -1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (visible[mid].node.getBoundingClientRect().bottom > line) { found = mid; hi = mid - 1; }
      else lo = mid + 1;
    }
    const here = found < 0 ? null : visible[found].entry.color;
    for (const button of chipsEl.children) {
      const on = button.dataset.color === (here || "all");
      button.classList.toggle("on", on);
      if (on && button.dataset.color !== "all") {
        // 칩 줄도 가로로 따라 움직여야 지금 색이 눈에 보인다.
        const box = chipsEl.getBoundingClientRect();
        const chip = button.getBoundingClientRect();
        if (chip.left < box.left + 8 || chip.right > box.right - 8) {
          chipsEl.scrollTo({
            left: button.offsetLeft - chipsEl.clientWidth / 2 + button.offsetWidth / 2,
            behavior: "smooth",
          });
        }
      }
    }
  }

  /* 스크롤마다 다시 재면 손가락이 밀린다. 100ms 에 한 번이면 칩이 따라오는 데 충분하다.
     requestAnimationFrame 이 아니라 시계를 쓰는 건, 화면이 안 보이는 동안
     rAF 가 멈춰 서서 표시가 옛날 색에 걸린 채 남는 일이 없게 하려는 것이다. */
  function spySoon() {
    if (spying) return;
    spying = setTimeout(() => { spying = 0; spy(); }, 100);
  }

  /* ---------- 상세 시트 ---------- */

  let lastFocused = null;

  function open(entry) {
    lastFocused = document.activeElement;
    placeIcon($("sheet-icon"), entry);

    $("sheet-name").textContent = entry.ko;
    $("sheet-en").textContent = entry.en;

    /* 머리말 태그. 등급을 맨 앞에 두고, 그 다음이 액티브인지 패시브인지다.
       게임 중에 알고 싶은 순서가 그렇다. */
    const meta = $("sheet-meta");
    meta.textContent = "";
    const chip = (text, tone) => {
      const span = document.createElement("span");
      span.textContent = text;
      if (tone) span.className = tone;
      meta.append(span);
      return span;
    };

    if (entry.quality !== undefined) {
      const span = chip(`등급 ${entry.quality}`, "strong");
      span.style.color = QUALITY_HEX[entry.quality];
      span.style.borderColor = QUALITY_HEX[entry.quality] + "66";
    }

    if (entry.type) {
      // 패밀리어는 패시브 자리에 붙는 동료다. 둘 다 적어야 오해가 없다.
      const passive = entry.type !== "active";
      chip(passive ? "패시브" : "액티브", entry.type === "active" ? "active" : null);
      if (entry.type === "familiar") chip(TYPE_KO.familiar);
      if (entry.charge) chip(`충전 ${entry.charge}칸`, "active");
      else if (entry.chargetype && CHARGE_KO[entry.chargetype]) {
        chip(CHARGE_KO[entry.chargetype], "active");
      }
    } else {
      chip(KIND_KO[entry.kind]);
    }

    for (const one of entry.sets || []) chip(one.ko, "set");

    chip(`ID ${entry.id}`);
    const bucket = DATA.buckets.find((b) => b.key === entry.color);
    chip(`${bucket.emoji} ${bucket.ko}`);

    const ul = $("sheet-desc");
    ul.textContent = "";
    for (const line of entry.desc) {
      const li = document.createElement("li");
      li.textContent = line;
      if (line.startsWith("↑")) li.className = "up";
      else if (line.startsWith("↓")) li.className = "down";
      ul.append(li);
    }
    if (!entry.desc.length) {
      const li = document.createElement("li");
      li.textContent = "설명이 아직 없습니다.";
      ul.append(li);
    }

    /* 같은 세트의 아이템을 아이콘으로 늘어놓는다.
       이름만 적어 두면 "그래서 뭘 더 먹어야 하는데" 가 남는다. */
    const setsEl = $("sheet-sets");
    setsEl.textContent = "";
    setsEl.hidden = !entry.sets;
    for (const one of entry.sets || []) {
      const members = setMembers.get(one.ko) || [];
      const info = (DATA.setInfo || {})[one.ko] || {};
      const need = DATA.setsNeeded;
      /* 스톰피처럼 아이템만으로는 수가 모자란 세트가 있다.
         "2개 중 3개를 모으면" 이라고 적히면 말이 안 되니 구성을 밝혀 준다. */
      const note = info.other
        ? `${need}개를 모으면 변신 · 아이템 ${info.items}개 + 알약 ${info.other}개`
        : `${members.length}개 중 ${need}개를 모으면 변신`;
      const box = document.createElement("div");
      const head = document.createElement("h3");
      head.innerHTML = `세트 · ${one.ko} <span>${one.en} · ${note}</span>`;
      box.append(head);

      /* 모으면 뭐가 좋은지가 사실 제일 궁금한 부분이다. */
      if (info.effect && info.effect.length) {
        const effects = document.createElement("ul");
        effects.className = "set-effect";
        for (const line of info.effect) {
          const li = document.createElement("li");
          li.textContent = line;
          if (line.startsWith("↑")) li.className = "up";
          else if (line.startsWith("↓")) li.className = "down";
          effects.append(li);
        }
        box.append(effects);
      }

      const row = document.createElement("div");
      row.className = "set-row";
      for (const member of members) {
        const button = document.createElement("button");
        button.type = "button";
        button.title = member.ko;
        button.className = member.id === entry.id && member.kind === entry.kind ? "self" : "";
        const icon = document.createElement("span");
        icon.className = "icon sm";
        placeIcon(icon, member);
        button.append(icon);
        button.addEventListener("click", () => open(member));
        row.append(button);
      }
      box.append(row);
      setsEl.append(box);
    }

    const poolsEl = $("sheet-pools");
    const poolList = $("sheet-pool-list");
    poolList.textContent = "";
    poolsEl.hidden = !entry.pools;
    for (const name of entry.pools || []) {
      const span = document.createElement("span");
      span.textContent = name;
      // 그리드 모드는 별도 모드라 눈에 덜 띄게 둔다.
      if (name.startsWith("그리드")) span.className = "greed";
      poolList.append(span);
    }

    resetDrag();
    sheetEl.hidden = false;
    backdropEl.hidden = false;
    sheetEl.scrollTop = 0;
    document.body.style.overflow = "hidden";
    // 손잡이가 아니라 시트 자체에 초점을 준다. 단추에 주면 브라우저가
    // 손잡이 자리에 커다란 네모 테두리를 그린다.
    sheetEl.focus();
    writeHash(entry);
  }

  function close() {
    if (sheetEl.hidden) return;
    sheetEl.hidden = true;
    backdropEl.hidden = true;
    resetDrag();
    document.body.style.overflow = "";
    if (lastFocused) lastFocused.focus();
    writeHash();
  }

  /* ---------- 아래로 밀어서 닫기 ----------
     시트는 화면 아래에 붙어 있는데 닫는 자리(배경·손잡이)는 위에 있다.
     한 손으로 폰을 쥔 채 엄지를 위로 뻗는 게 은근히 번거롭다.
     손잡이가 이미 "잡아 끌 수 있게" 생겼으니 진짜로 끌리게 만든다.
     손가락을 따라 내려오다가, 충분히 내렸거나 툭 튕기면 닫힌다. */

  const wide = window.matchMedia("(min-width: 720px)");
  const CLOSE_DIST = 96;   // 이만큼 내리면 닫는다
  const CLOSE_FLICK = 0.5; // px/ms. 짧게 튕겨도 닫히게

  let drag = null;
  let dragged = false; // 방금 끝난 손짓이 끌기였는지 (손잡이 클릭과 구분)

  function resetDrag() {
    drag = null;
    sheetEl.classList.remove("dragging");
    sheetEl.style.transition = "";
    sheetEl.style.transform = "";
    backdropEl.style.transition = "";
    backdropEl.style.opacity = "";
  }

  function dragStart(event) {
    // 데스크톱은 Esc 와 배경 클릭이 이미 편하다. 마우스 드래그는 글자 선택을 방해한다.
    if (event.pointerType === "mouse" || wide.matches) return;
    // 손잡이는 언제나 끌 수 있고, 나머지 부분은 이미 맨 위까지 올라와 있을 때만.
    // 내용을 읽으려고 위로 올리는 손짓이 닫기로 오해받으면 안 된다.
    const fromGrab = event.target.closest(".grab");
    if (!fromGrab && sheetEl.scrollTop > 0) return;
    dragged = false;
    drag = {
      x: event.clientX, y: event.clientY, dy: 0, on: false, down: false,
      // 속도는 마지막 한 순간만 본다. 천천히 끌다가 마지막에 툭 튕기는
      // 손짓도 제대로 잡으려면 시작점부터의 평균으로는 안 된다.
      vy: event.clientY, vt: event.timeStamp,
    };
  }

  function dragMove(event) {
    if (!drag) return;
    const dx = event.clientX - drag.x;
    const dy = event.clientY - drag.y;
    drag.down = dy > 0; // touchmove 에서 브라우저 스크롤을 막을지 판단하는 근거

    if (!drag.on) {
      // 아래로 내려가는 손짓인지 확실해질 때까지 기다린다.
      if (dy < -6 || Math.abs(dx) > Math.abs(dy) + 4) { drag = null; return; }
      if (dy < 8) return;
      drag.on = true;
      dragged = true;
      sheetEl.classList.add("dragging");
      sheetEl.style.transition = "none";
      backdropEl.style.transition = "none";
      try { sheetEl.setPointerCapture(event.pointerId); } catch (_) {}
    }

    if (event.timeStamp - drag.vt > 60) { drag.vy = event.clientY; drag.vt = event.timeStamp; }
    drag.dy = dy > 0 ? dy : dy / 5; // 위로는 살짝만 따라와 고무줄처럼 버틴다
    sheetEl.style.transform = `translateY(${drag.dy}px)`;
    backdropEl.style.opacity = String(Math.max(0, 1 - drag.dy / 400));
  }

  function dragEnd(event) {
    if (!drag) return;
    const { on, dy, vy, vt } = drag;
    drag = null;
    if (!on) return;

    const speed = (event.clientY - vy) / Math.max(1, event.timeStamp - vt);
    sheetEl.classList.remove("dragging");

    if (dy > CLOSE_DIST || (speed > CLOSE_FLICK && dy > 24)) {
      // 손을 뗀 자리에서 그대로 미끄러져 내려가게 둔다. 툭 끊기면 어색하다.
      sheetEl.style.transition = "transform .16s ease-in";
      backdropEl.style.transition = "opacity .16s ease-in";
      sheetEl.style.transform = "translateY(100%)";
      backdropEl.style.opacity = "0";
      setTimeout(close, 150);
      return;
    }

    sheetEl.style.transition = "transform .2s cubic-bezier(.2, .8, .3, 1)";
    backdropEl.style.transition = "opacity .2s ease";
    sheetEl.style.transform = "";
    backdropEl.style.opacity = "";
  }

  /* ---------- 주소창에 상태 남기기 ----------
     색깔이나 아이템을 골랐을 때 주소가 바뀌면 링크로 공유할 수 있고,
     폰의 뒤로가기가 시트 닫기로 자연스럽게 이어진다. */

  let ignoreHash = false;

  function writeHash(entry) {
    const hash = entry ? `#i=${entry.kind}:${entry.id}` : " ";
    ignoreHash = true;
    if (entry) history.pushState(null, "", hash);
    else history.replaceState(null, "", hash);
    setTimeout(() => { ignoreHash = false; }, 0);
  }

  function readHash() {
    if (ignoreHash) return;
    const params = new URLSearchParams(location.hash.slice(1));
    const target = params.get("i");
    if (target) {
      const [kind, id] = target.split(":");
      const entry = DATA.entries.find((e) => e.kind === kind && String(e.id) === id);
      if (entry) { open(entry); return; }
    }
    close();
  }

  /* ---------- 이벤트 ---------- */

  function wire() {
    let timer = 0;
    searchEl.addEventListener("input", () => {
      clearTimeout(timer);
      // 909개를 매 글자마다 훑으면 입력이 밀린다. 잠깐 모았다 한 번에 거른다.
      timer = setTimeout(() => {
        state.query = squeeze(searchEl.value);
        apply();
      }, 90);
    });
    clearEl.addEventListener("click", () => {
      searchEl.value = "";
      state.query = "";
      apply();
      searchEl.focus();
    });
    for (const button of document.querySelectorAll(".seg button")) {
      button.addEventListener("click", () => {
        state.kind = button.dataset.kind;
        apply();
      });
    }
    backdropEl.addEventListener("click", close);
    $("sheet-close").addEventListener("click", () => {
      // 끌어내리다 되돌아온 손짓이 클릭으로 새어 나오면 엉뚱하게 닫힌다.
      if (dragged) { dragged = false; return; }
      close();
    });
    sheetEl.addEventListener("pointerdown", dragStart);
    sheetEl.addEventListener("pointermove", dragMove);
    /* pointermove 를 막아 봐야 스크롤은 안 멈춘다. 브라우저가 손짓을 스크롤로
       가져가 버리면 pointercancel 이 날아오고 끌기가 중간에 끊긴다.
       실제로 스크롤을 붙잡아 두는 건 touchmove 쪽이다. */
    sheetEl.addEventListener("touchmove", (event) => {
      if (drag && drag.down && event.cancelable) event.preventDefault();
    }, { passive: false });
    sheetEl.addEventListener("pointerup", dragEnd);
    sheetEl.addEventListener("pointercancel", () => { drag = null; resetDrag(); });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") close();
      if (event.key === "/" && document.activeElement !== searchEl) {
        event.preventDefault();
        searchEl.focus();
      }
    });
    window.addEventListener("hashchange", readHash);
    window.addEventListener("scroll", spySoon, { passive: true });
    window.addEventListener("resize", () => { measureBar(); spySoon(); }, { passive: true });
    measureBar();
  }

  /* ---------- 시작 ---------- */

  fetch("assets/data/items.json")
    .then((response) => {
      if (!response.ok) throw new Error(response.status);
      return response.json();
    })
    .then((data) => {
      DATA = data;
      DATA.entries.forEach(indexEntry);
      document.documentElement.style.setProperty("--sprite-cols", DATA.sprite.cols);
      groupSets();
      buildChips();
      buildQualityChips();
      build();
      wire();
      apply();
      readHash();
      const stamp = $("stamp");
      if (stamp) {
        const count = (kind) => DATA.entries.filter((e) => e.kind === kind).length;
        stamp.textContent =
          `아이템 ${count("item")}개 · 장신구 ${count("trinket")}개 · ` +
          `카드 ${count("card")}개 · ${DATA.generated} 기준`;
      }
    })
    .catch((error) => {
      listEl.innerHTML =
        `<p style="color:#e5686d;padding:24px 0">자료를 읽지 못했습니다 (${error.message}).<br>` +
        `<code>python3 tools/build.py</code> 를 실행했는지 확인해 주세요.</p>`;
    });

  /* ---------- 새 판 알림 ----------
     오프라인으로도 열리게 캐시를 깔아 둔 대가로, 아이템을 고치고 올려도
     이미 다녀간 기기는 예전 걸 계속 본다. 서버의 sw.js 에 적힌 판 번호와
     지금 물고 있는 번호가 다르면 제목 옆에 빨간 동그라미를 띄운다.
     누르면 캐시를 비우고 새로 받는다. */

  function watchVersion() {
    if (!("serviceWorker" in navigator)) return;
    const badge = $("fresh");
    if (!badge) return;

    const verEl = $("ver");
    let busy = false;
    let mine = null;   // 지금 화면이 물고 있는 판
    let latest = null; // 서버에 올라와 있는 판
    // 첫 방문에는 워커가 페이지를 넘겨받으면서 controllerchange 가 한 번 뜬다.
    // 그건 새 판이 아니라 그냥 설치다.
    const hadWorker = !!navigator.serviceWorker.controller;

    function paint() {
      if (!verEl) return;
      if (!mine) { verEl.hidden = true; return; }
      const stale = !!latest && latest !== mine;
      verEl.hidden = false;
      // 머리말은 폭이 빠듯하니 짧게. 새 판 번호는 빨간 동그라미와 맨 아래가 맡는다.
      verEl.textContent = mine;
      verEl.classList.toggle("stale", stale);
      if (stale) badge.setAttribute("aria-label", `새 판 ${latest} 나왔습니다. 눌러서 받기`);

      const build = $("build");
      if (build) {
        build.hidden = false;
        build.textContent = stale
          ? `이 기기는 ${mine} · 새 판 ${latest} 나왔습니다 — 제목 옆 빨간 동그라미를 누르세요`
          : `이 기기는 ${mine} · 최신입니다`;
      }
    }

    function show() {
      if (busy) return;
      badge.hidden = false;
      // 좁은 화면에서는 배지가 들어설 자리를 판 번호에서 빌려 온다.
      const heading = badge.closest("h1");
      if (heading) heading.classList.add("alerting");
    }

    // 지금 페이지를 먹여 살리고 있는 워커에게 판 번호를 물어본다.
    function askWorker() {
      return new Promise((resolve) => {
        const worker = navigator.serviceWorker.controller;
        if (!worker) { resolve(null); return; }
        const channel = new MessageChannel();
        const giveUp = setTimeout(() => resolve(null), 2000);
        channel.port1.onmessage = (event) => {
          clearTimeout(giveUp);
          resolve(event.data && event.data.version);
        };
        worker.postMessage({ type: "version" }, [channel.port2]);
      });
    }

    // 첫 방문에는 워커가 페이지를 넘겨받기 전이라 아직 대답할 상대가 없다. 잠깐 기다려 준다.
    async function myVersion() {
      for (let i = 0; i < 4; i++) {
        const found = await askWorker();
        if (found) return found;
        await new Promise((resolve) => setTimeout(resolve, 700));
      }
      return null;
    }

    async function check() {
      if (busy || !navigator.onLine) return;
      try {
        // 캐시를 건너뛰고 서버 것을 그대로 읽어야 판 번호를 견줄 수 있다.
        const response = await fetch("sw.js", { cache: "no-store" });
        if (!response.ok) return;
        latest = (/VERSION\s*=\s*"([^"]+)"/.exec(await response.text()) || [])[1] || latest;
        mine = (await askWorker()) || mine;
        paint();
        if (latest && mine && latest !== mine) show();
      } catch (_) { /* 통신이 안 되면 다음 기회에 */ }
    }

    async function refresh() {
      if (busy) return;
      if (!navigator.onLine) {
        // 캐시를 지웠는데 새로 받을 수 없으면 빈 화면만 남는다.
        badge.textContent = "!";
        badge.setAttribute("aria-label", "지금은 통신이 안 됩니다. 연결된 뒤에 눌러 주세요.");
        setTimeout(() => {
          badge.textContent = "N";
          badge.setAttribute("aria-label", "새 판이 나왔습니다. 눌러서 받기");
        }, 2000);
        return;
      }
      busy = true;
      badge.disabled = true;
      badge.textContent = "…";
      try {
        const keys = await caches.keys();
        await Promise.all(keys.map((key) => caches.delete(key)));
        const registration = await navigator.serviceWorker.getRegistration();
        if (registration) await registration.unregister();
      } catch (_) { /* 못 지워도 새로고침은 해 본다 */ }
      location.reload();
    }

    badge.addEventListener("click", (event) => {
      // 제목 안에 든 버튼이라 그냥 두면 제목의 새로고침까지 같이 걸린다.
      event.stopPropagation();
      refresh();
    });

    // 뒤에서 워커가 조용히 새 판으로 갈아탄 경우. 화면의 코드는 아직 예전 것이다.
    navigator.serviceWorker.addEventListener("controllerchange", () => {
      if (hadWorker) show();
    });

    myVersion().then((found) => { mine = found; paint(); check(); });
    // 게임하다 다시 들여다볼 때마다 한 번씩 확인한다. 켜 둔 채로 며칠 지나도 놓치지 않게.
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) check();
    });
  }

  // 제목을 누르면 그냥 새로고침. 새 판 받기는 옆의 빨간 동그라미가 맡는다.
  const reloadEl = $("reload");
  if (reloadEl) reloadEl.addEventListener("click", () => location.reload());

  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("sw.js").then(watchVersion).catch(() => {});
    });
  }
})();
