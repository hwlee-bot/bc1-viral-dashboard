/* report_dashboard/static/runtime.js — 리포트 iframe 런타임 (스펙 v4 §5·§6).
   순수 함수(RT.*)는 Python 정본과 같은 답을 내야 한다: reporting.delta_over_days,
   report_common.sorted_content_rows, reporting.average_participation_rate. */
(function (root) {
  function combineSeries(dates, byChannel, on) {
    const sel = on instanceof Set ? on : new Set(on);
    return dates.map((_, i) => Object.keys(byChannel).reduce((acc, ch) => acc + (sel.has(ch) ? (byChannel[ch][i] || 0) : 0), 0));
  }
  function dayNum(iso) { const [y, m, d] = iso.split("-").map(Number); return Date.UTC(y, m - 1, d) / 86400000; }
  function deltaOverDays(dates, values, days = 7) {
    if (dates.length < 2) return null;
    const lastI = dates.length - 1, cutoff = dayNum(dates[lastI]) - days;
    let base = -1;
    for (let i = 0; i < lastI; i++) if (dayNum(dates[i]) <= cutoff) base = i;
    if (base < 0) return null;
    return { delta: values[lastI] - values[base], span: dayNum(dates[lastI]) - dayNum(dates[base]) };
  }
  function orderRows(rows, sortKey) {
    const out = rows.slice();                          // 안정 정렬 2회: 부차 키 → 값0 맨 아래
    if (sortKey === "comments") out.sort((a, b) => b.comments - a.comments);
    else if (sortKey === "recent") out.sort((a, b) => (b.release || "").localeCompare(a.release || ""));
    else if (sortKey === "rate") out.sort((a, b) => (a.rate == null) - (b.rate == null) || ((b.rate || 0) - (a.rate || 0)));
    else out.sort((a, b) => b.pv - a.pv);
    out.sort((a, b) => Number(a.empty) - Number(b.empty));
    return out;
  }
  /* 참여율 시리즈: 채널별 {sum, n}을 선택 채널로 합쳐 `Σsum/Σn`. 그날 대상이 0건인 날짜는
     **빼버린다** — 0%로 채우면 아직 계산할 수 없던 날이 "참여율 0%"로 보인다.
     Python `views.rate_points`와 같은 규칙이어야 한다(스펙 §5). */
  function combineRate(dates, byChannel, on) {
    const sel = on instanceof Set ? on : new Set(on);
    const names = Object.keys(byChannel).filter((ch) => sel.has(ch));
    const out = [];
    dates.forEach((day, i) => {
      let sum = 0, n = 0;
      names.forEach((ch) => { sum += byChannel[ch].sum[i] || 0; n += byChannel[ch].n[i] || 0; });
      if (n) out.push([day, pyRound1(sum / n)]);
    });
    return out;
  }
  function avgRate(rates) {
    const xs = rates.filter((r) => r != null);
    return xs.length ? Math.round((xs.reduce((a, b) => a + b, 0) / xs.length) * 10) / 10 : null;
  }
  function fmtInt(n) { return Math.round(n).toLocaleString("en-US"); }
  /* Python 포맷 재현 — 서버가 그린 문자열과 한 글자도 달라지면 로드 직후 화면이 튄다.
     fmtG = `f"{x:g}"`(inline_bar 폭), pyRound = `round()`(짝수 반올림, 채널 분포 pct). */
  function fmtG(x) { return String(+x.toPrecision(6)); }
  /* charts.js는 라벨을 `innerHTML` 템플릿에 그대로 끼워 넣는다 — payload는 서버가 만들지만
     날짜 문자열이 그 경로로 마크업이 되는 걸 여기서 끊는다. 축 라벨은 `08.31`·`9.1` 같은
     숫자·점 조합뿐이므로 그 밖은 빈 문자열(= charts.js가 그 라벨을 건너뛴다). */
  function safeLabel(t) { return /^[\d.]{0,5}$/.test(String(t == null ? "" : t)) ? String(t == null ? "" : t) : ""; }
  function pyRound(x) { const f = Math.floor(x), d = x - f; return d > 0.5 ? f + 1 : d < 0.5 ? f : (f % 2 === 0 ? f : f + 1); }
  /* pyRound1 = Python `round(x, 1)`(참여율). `pyRound(x * 10) / 10`으로는 안 된다 —
     `0.15 * 10`이 부동소수에서 **정확히 1.5**가 되어 짝수 반올림이 0.2를 내지만, Python은
     0.15의 실제 값(0.1499…)을 보고 0.1을 낸다. 그래서 배정밀도의 정확한 십진 표기를
     `toFixed(20)`으로 받아 십분위 아래를 문자열로 비교하고, **정확히 반일 때만** 짝수로
     보낸다(round-half-even). 랜덤 8000개로 Python과 대조했다(tests/js). */
  function pyRound1(x) {
    if (!isFinite(x) || Math.abs(x) >= 1e15) return Math.round(x * 10) / 10;
    const neg = x < 0, s = Math.abs(x).toFixed(20), dot = s.indexOf(".");
    const head = +s.slice(0, dot), frac = s.slice(dot + 1);
    let tenths = +frac[0];
    const rest = frac.slice(1), half = "5" + "0".repeat(rest.length - 1);
    if (rest > half) tenths += 1;                                  // 같은 길이 십진 문자열 비교
    else if (rest === half && tenths % 2 === 1) tenths += 1;        // 정확히 반 → 짝수로
    const out = +(head + tenths / 10).toFixed(1);
    return neg ? -out : out;
  }
  /* `unit="pt"`는 퍼센트 시리즈(평균 참여율)용 — 퍼센트의 증감은 퍼센트포인트이므로
     소수 1자리 `+2.9pt · 7d`로 쓴다(Python `strip_delta_html(unit="pt")`와 같은 문구). */
  function deltaLabel(d, pointCount, unit) {
    if (!d) return { text: `수집 ${pointCount}일차`, dir: "flat" };
    const pt = unit === "pt";
    const v = pt ? Math.round(d.delta * 10) / 10 : d.delta;
    const body = pt ? (v > 0 ? "+" : "") + v.toFixed(1) + "pt" : (v > 0 ? "+" : "") + fmtInt(v);
    if (v > 0) return { text: `${body} · ${d.span}d`, dir: "up" };
    if (v < 0) return { text: `${body} · ${d.span}d`, dir: "down" };
    return { text: `변동 없음 · ${d.span}d`, dir: "flat" };
  }
  /* 히어로 세그먼트 `일별`(§11.2): 누적 곡선의 전일 대비 증가분. 첫날은 기준이 없어 빠지므로
     날짜축도 `dates.slice(1)`을 써야 한다("수집 시점 차"라 sub 라벨도 같이 바뀐다). */
  function dailyDiff(values) {
    const out = [];
    for (let i = 1; i < values.length; i++) out.push(values[i] - values[i - 1]);
    return out;
  }
  /* Python `ui.CHANNEL_LABEL`·`ui.empty_state(...)`와 문자 단위로 같아야 한다(파이썬 패리티 테스트가 고정). */
  const CH_LABEL = { instagram: "인스타그램", blog: "블로그", cafe: "카페", community: "커뮤니티", youtube: "유튜브" };
  /* 채널별 모드는 채널 키를 `innerHTML`(`var(--ch-KEY)` · 범례 라벨)에 넣는다 — payload는
     서버가 만들지만, 아는 채널만 통과시켜 데이터에서 온 문자열이 마크업이 되는 길을 끊는다. */
  function knownChannels(names) { return names.filter((ch) => Object.prototype.hasOwnProperty.call(CH_LABEL, ch)); }
  /* charts.js areaChart의 축 라벨 선택 규칙을 그대로 옮긴 것(§11.2 multiLine이 같은 기하를 써야 한다):
     step = max(1, round(n/5))이고, step 배수 중 끝에서 step 이상 떨어진 것 + 마지막 하나. */
  function pickLabels(labels, n) {
    const step = Math.max(1, Math.round(n / 5)), last = n - 1, out = [];
    labels.forEach((t, i) => {
      if (!t) return;
      if ((i % step === 0 && last - i >= step) || i === last) out.push(i);
    });
    return out;
  }
  /* 표시 규칙의 단일 정본(스펙 §12.2) — 요소가 가진 `variant`/`depth`/`basis` 키가
     **전부** 현재 상태와 같을 때만 보인다. 한 축만 가진 요소(예: `.lead-block[data-basis]`,
     `.legend[data-depth]`)는 나머지 축을 따지지 않으므로 예전 동작이 그대로 유지된다.
     `data-spark-variant`는 호출부에서 `variant` 키로 넘긴다(셀렉터만 다른 같은 축). */
  const VIS_KEYS = ["variant", "depth", "basis"];
  function visibleUnder(state, attrs) {
    return VIS_KEYS.every((k) => attrs[k] === undefined || attrs[k] === state[k]);
  }
  // `_` 접두사는 "Python 정본이 아니라 포맷 재현용"이라는 뜻 — 노출은 node 테스트가 고정하기 위해서다.
  const RT = {
    combineSeries, combineRate, deltaOverDays, orderRows, avgRate, fmtInt, deltaLabel, dailyDiff, visibleUnder,
    _fmtG: fmtG, _pyRound: pyRound, _pyRound1: pyRound1, _safeLabel: safeLabel, _pickLabels: pickLabels,
    _knownChannels: knownChannels, _CH_LABEL: CH_LABEL,
  };
  root.RT = RT;
  if (typeof root.document === "undefined" || !root.frameElement) return;   // node 테스트·단독 열기 경로
  /* ================= DOM 글루(스펙 §6) — 프레임 안에서만 실행된다 ================= */
  root.__glueRan = true;
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.prototype.slice.call(r.querySelectorAll(s));
  const fe = root.frameElement;

  /* 높이: 부모 뷰포트 바닥까지 늘린다(스트림릿 iframe은 고정 height로 뜬다). */
  function fit() {
    try {
      const h = Math.max(320, root.parent.innerHeight - fe.getBoundingClientRect().top);
      fe.style.height = h + "px";
      fe.style.minHeight = "0";
    } catch (e) {}   // 부모 접근이 막히면 기본 높이로 둔다 — 나머지 글루는 계속 돈다
  }
  /* 테마: 부모 body 배경 밝기 → data-theme (v3 THEME_HOOK_HTML과 같은 공식). */
  function theme() {
    try {
      const m = root.parent.getComputedStyle(root.parent.document.body).backgroundColor.match(/\d+/g);
      if (!m || m.length < 3) return;
      const l = (0.2126 * +m[0] + 0.7152 * +m[1] + 0.0722 * +m[2]) / 255;
      const t = l < 0.5 ? "dark" : "light";
      if (document.documentElement.dataset.theme !== t) document.documentElement.dataset.theme = t;
    } catch (e) {}
  }
  fit();
  theme();

  /* 목업 CSS에 없던 규칙만 여기서 심는다(스펙 §4.1) — 꺼진 칩 무음 처리, 꺼진 채널의
     `.srow.ours` 강조 무력화, 그리고 `[hidden]`.

     `[hidden]`은 UA 스타일시트의 `display:none`이라 **author 스타일이면 무조건 진다** —
     목업 mix.css/page-exposure.css가 `.ch-row`·`.serp`·`.share-grid`에 `display:grid`를,
     테이블 행에 `display:table-row`를 직접 걸어두므로 `el.hidden = true`가 아무 효과가
     없었다(꺼진 채널 행·다른 키워드 SERP·가중 점유율 그리드가 그대로 보였다). 여기서
     `!important`로 한 번에 덮는다 — 요소 종류마다 규칙을 따로 쓰지 않는다. */
  const style = document.createElement("style");
  style.id = "rt-css";
  style.textContent =
    "[hidden]{display:none!important}" +
    " .chip[data-ch]:not(.on){color:var(--muted)} .chip[data-ch]:not(.on) .dot{opacity:.25}" +
    " .srow.ours.is-off{background:transparent;margin:0;padding-left:0;padding-right:0;border-bottom-color:var(--hair)}" +
    " .srow.ours.is-off .r,.srow.ours.is-off .t,.srow.ours.is-off .src{color:var(--ink-2);font-weight:500}" +
    " .beyond.is-off{opacity:.45} .detail.is-empty{position:static;padding-left:0;border-left:0}";
  document.head.appendChild(style);

  const EMPTY_HERO = '<div class="empty"><b>추이를 그릴 데이터가 아직 부족합니다</b>수집일이 3일 이상 쌓이면 곡선이 나타납니다.</div>';
  /* 모드에 따라 바뀌는 것은 범례 한 곳뿐이다(리뷰 3) — `.sec-h`의 sub 라벨은 세 모드 모두
     서버가 그린 그대로 두므로 JS에는 그 문구도, 그것을 잡는 훅도 없다(있으면 `일별`에서
     sub와 범례에 같은 문장이 두 번 찍힌다). 아래 두 문구는 Python
     `views.summary.HERO_LEGEND_CUM`·`HERO_DAILY` 정본과 글자 단위로 같아야 한다. */
  const HERO_LEGEND_CUM = '전체 누적';
  const HERO_DAILY = '일별 증가분(수집 시점 차)';
  const EMPTY_DETAIL = '<div class="empty"><b>표시할 콘텐츠가 없습니다</b>미수집 숨기기를 해제하면 다시 표시됩니다.</div>';
  const payload = (() => { try { return JSON.parse(($("#payload") || {}).textContent || "{}"); } catch (e) { return {}; } })();
  /* 초기 상태는 서버가 그린 마크업에서 읽는다 — 그래야 첫 applyState()가 화면을 바꾸지 않는다. */
  const pick = (sel, key, dflt) => { const el = $(sel); return el ? el.dataset[key] : dflt; };
  const state = {
    on: new Set($$(".chip[data-ch]").map((c) => c.dataset.ch)),
    sort: pick(".seg span.on[data-sort]", "sort", "value"),
    hideEmpty: !!$(".chip.on[data-toggle='hide-empty']"),
    kw: pick(".kw-chips .chip.on[data-kw]", "kw", null),
    variant: pick(".seg span.on[data-variant]", "variant", "slot"),
    depth: pick(".seg span.on[data-depth]", "depth", "10"),
    basis: pick(".seg span.on[data-basis]", "basis", "count"),
    hero: pick(".seg span.on[data-hero]", "hero", "cum"),
    selected: pick("tr.is-sel[data-cid]", "cid", null),
  };
  let booted = false;                       // 첫 applyState()는 등장 모션을 다시 재생하지 않는다
  let shownDetail = $("#detail") ? state.selected : null;   // 서버가 이미 그려둔 상세

  function rowsOf(table) {
    return $$("tbody tr[data-cid]", table).map((tr) => ({
      tr, cid: tr.dataset.cid, ch: tr.dataset.ch, pv: +tr.dataset.pv, comments: +tr.dataset.comments,
      rate: tr.dataset.rate === "" ? null : +tr.dataset.rate, release: tr.dataset.release, empty: tr.dataset.empty === "1",
    }));
  }
  function reEnter(el) { if (!el) return; el.classList.remove("enter"); void el.offsetWidth; el.classList.add("enter"); }
  function setBars(rows) {
    const max = Math.max(1, ...rows.map((r) => r.pv));
    rows.forEach((r) => {
      const i = $(".inline-bar i", r.tr);
      if (i) i.style.width = RT._fmtG(Math.max(0, Math.min(100, r.pv / max * 100))) + "%";
    });
  }
  /* `[data-stat]` 안의 단위 `<small>`(건·%)을 **키 단위로** 보존한다 — 요소 단위로 첫 호출에
     캐시하면, 값이 없어 서버가 단위 없이 그린 칸(`평균 참여율 —`)이 "단위 없음"으로 굳어
     나중에 값이 생겨도 `%`를 되찾지 못한다. 단위를 실제로 본 순간에만 캐시를 갱신하므로
     첫 렌더는 그대로다(서버가 그린 `<small>`을 떼고 같은 것을 다시 붙인다). */
  const units = new Map();
  function put(key, text, hasValue) {
    $$('[data-stat="' + key + '"]').forEach((el) => {
      const s = el.querySelector("small");
      if (s) units.set(key, s.cloneNode(true));
      el.textContent = text;
      const u = units.get(key);
      if (u && hasValue !== false) el.appendChild(u.cloneNode(true));
    });
  }
  function putMeta(key, text) { $$('[data-meta="' + key + '"]').forEach((el) => (el.textContent = text)); }

  /* 선택만 바뀌는 경로(행 클릭) — 스트립 등장 모션·차트 재렌더까지 다시 돌릴 이유가 없다.
     `#detail`은 `.detail`이고 template 안에도 `<aside class="detail">`가 통째로 들어 있으므로
     **안쪽 내용만** 옮긴다(그대로 넣으면 `.detail`이 중첩돼 패널이 40px 밀린다). */
  function applySelection() {
    $$(".list tbody tr[data-cid]").forEach((tr) => tr.classList.toggle("is-sel", tr.dataset.cid === state.selected));
    const aside = $("#detail");
    if (!aside || state.selected === shownDetail) return;
    const t = $$("template[data-detail]").filter((x) => x.dataset.detail === state.selected)[0];
    const src = t && (t.content.querySelector(".detail") || t.content.firstElementChild);
    aside.innerHTML = src ? src.innerHTML : EMPTY_DETAIL;
    aside.classList.toggle("is-empty", !src);   // 빈 상태는 sticky·왼쪽 헤어라인·패딩을 뗀다
    shownDetail = state.selected;
    reEnter(aside);
  }

  function applyState() {
    $$(".chip[data-ch]").forEach((c) => c.classList.toggle("on", state.on.has(c.dataset.ch)));
    /* --- 표: 요약 상위 8(tbl-perf) / 콘텐츠 성과 리스트(.list table) --- */
    const perf = $("table.tbl-perf"), list = $(".list table");
    let metaRows = null;
    if (perf) {
      const rows = rowsOf(perf), vis = rows.filter((r) => state.on.has(r.ch));
      rows.forEach((r) => (r.tr.hidden = true));
      vis.slice(0, 8).forEach((r) => (r.tr.hidden = false));
      setBars(vis.slice(0, 8));
      metaRows = vis;                       // 합계는 상위 8이 아니라 보이는 채널 전체 기준
    }
    if (list) {
      const rows = rowsOf(list);
      const vis = RT.orderRows(rows.filter((r) => state.on.has(r.ch) && !(state.hideEmpty && r.empty)), state.sort);
      const tb = $("tbody", list);
      rows.forEach((r) => (r.tr.hidden = true));
      vis.forEach((r) => { r.tr.hidden = false; tb.appendChild(r.tr); });
      setBars(vis);
      if (!vis.some((r) => r.cid === state.selected)) state.selected = vis.length ? vis[0].cid : null;
      applySelection();
      const hint = $("[data-hint]");
      if (hint) hint.textContent = state.hideEmpty ? "빈 데이터 숨김" : "데이터 없는 콘텐츠는 맨 아래";
      $$(".seg span[data-sort]").forEach((s) => s.classList.toggle("on", s.dataset.sort === state.sort));
      const he = $(".chip[data-toggle='hide-empty']");
      if (he) he.classList.toggle("on", state.hideEmpty);
      metaRows = vis;
    }
    /* --- 스트립·제목 메타 재계산(보이는 행 기준) --- */
    if (metaRows) {
      const nonIg = metaRows.filter((r) => r.ch !== "instagram"), ig = metaRows.filter((r) => r.ch === "instagram");
      put("contents", String(metaRows.length));                                  // Python도 콤마 없이 그린다
      put("views", RT.fmtInt(nonIg.reduce((a, r) => a + r.pv, 0)));
      put("likes", RT.fmtInt(ig.reduce((a, r) => a + r.pv, 0)));
      put("comments", String(metaRows.reduce((a, r) => a + r.comments, 0)));
      const ar = RT.avgRate(metaRows.map((r) => r.rate));
      put("rate", ar == null ? "—" : ar.toFixed(1), ar != null);                  // 없으면 단위 `%`도 떼야 한다
      putMeta("contents", String(metaRows.length));
      putMeta("channels", String(new Set(metaRows.map((r) => r.ch)).size));
      const bc = $('[data-meta="by-channel"]');
      if (bc) {
        const cnt = {};
        metaRows.forEach((r) => (cnt[r.ch] = (cnt[r.ch] || 0) + 1));
        bc.textContent = Object.keys(cnt).map((c) => [c, cnt[c]]).sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
          .map((e) => (CH_LABEL[e[0]] || e[0]) + " " + e[1]).join(" · ");
      }
      if (booted) reEnter($(".strip"));
    }
    /* --- 채널 분포(요약, data-n 있음) · 채널별 네이버 노출(상위노출, data-n 없음) --- */
    const chRows = $$(".ch-row[data-ch]");
    if (chRows.length) {
      chRows.forEach((r) => (r.hidden = !state.on.has(r.dataset.ch)));
      const vis = chRows.filter((r) => state.on.has(r.dataset.ch));
      if (vis.length && vis.every((r) => r.dataset.n !== undefined)) {
        const tot = vis.reduce((a, r) => a + +r.dataset.n, 0) || 1;
        vis.forEach((r) => {
          const p = RT._pyRound(+r.dataset.n / tot * 100);
          const bar = $(".hbar i", r);
          if (bar) bar.style.width = p + "%";
          const small = $(".v small", r);
          if (small) small.textContent = p + "%";
        });
      }
    }
    /* --- 상위노출: 키워드 칩 · 점유율 변형 · 파급력 기준 · 꺼진 채널의 ours 강조 --- */
    $$(".kw-chips .chip[data-kw]").forEach((c) => c.classList.toggle("on", c.dataset.kw === state.kw));
    $$(".serp[data-kw]").forEach((b) => (b.hidden = b.dataset.kw !== state.kw));
    /* 변형(슬롯/가중)·깊이(10/30/50)·파급력 기준(건수/조회수)은 같은 규칙으로 켜고 끈다 —
       요소가 가진 축이 전부 맞아야 보인다(`RT.visibleUnder`). 점유율 스파크만 셀렉터가
       `data-spark-variant`로 갈라져 있어(Python `spark_variants_html` 주석 참고) 여기서
       `variant` 축으로 되돌려 넘긴다. */
    $$("[data-variant],[data-depth],[data-basis],[data-spark-variant]").forEach((el) => {
      const d = el.dataset, attrs = {};
      if (d.variant !== undefined) attrs.variant = d.variant;
      if (d.sparkVariant !== undefined) attrs.variant = d.sparkVariant;
      if (d.depth !== undefined) attrs.depth = d.depth;
      if (d.basis !== undefined) attrs.basis = d.basis;
      const on = RT.visibleUnder(state, attrs);
      if (el.matches(".seg span")) el.classList.toggle("on", on);
      else el.hidden = !on;
    });
    $$("[data-depth-label]").forEach((el) => (el.textContent = state.depth));
    $$(".srow.ours[data-ch], .beyond[data-ch]").forEach((el) => el.classList.toggle("is-off", !state.on.has(el.dataset.ch)));
    renderCharts();
  }

  /* charts.js의 `pathLength`와 같은 방식 — 임시 SVG를 붙여 getTotalLength로 실측한다.
     `.draw` 애니메이션이 stroke-dashoffset을 0으로 몰기 때문에 dasharray/offset을
     **속성으로** 심어야 한다(inline style은 애니메이션에 진다). */
  function pathLength(d) {
    const ns = "http://www.w3.org/2000/svg";
    const svg = document.createElementNS(ns, "svg"), path = document.createElementNS(ns, "path");
    path.setAttribute("d", d);
    svg.appendChild(path);
    document.body.appendChild(svg);
    const len = path.getTotalLength();
    svg.remove();
    return len;
  }
  /* 히어로 `채널별` 모드(§11.2): 선택 채널마다 한 줄. charts.js `areaChart`와 같은 기하
     (padL 8 · padT 14 · padB 26/10 · 격자 3줄 · 축 라벨 규칙)를 쓰되 워시는 없고, y축은
     모든 선을 함께 담는 하나의 스케일이며 선 끝에 채널 라벨을 붙인다.
     `seriesByName`·`colorsByName`의 키는 `knownChannels`를 통과한 채널만 들어온다. */
  function multiLine(el, dates, seriesByName, colorsByName, opt) {
    opt = opt || {};
    const w = opt.w || 1140, h = opt.h || 230, padL = 8, padT = 14;
    const padR = opt.padR == null ? 60 : opt.padR, padB = opt.labels ? 26 : 10;
    const names = Object.keys(seriesByName);
    const all = names.reduce((acc, n) => acc.concat(seriesByName[n]), []);
    const min = Math.min.apply(null, all), max = Math.max.apply(null, all);
    const iw = w - padL - padR, ih = h - padT - padB, span = (max - min) || 1;
    const base = h - padB;
    const X = (i) => padL + iw * i / ((dates.length - 1) || 1);
    const Y = (v) => padT + ih - (v - min) / span * ih;
    const grid = [0.0, 0.5, 1.0].map((t) => padT + (base - padT) * t)
      .map((gy) => `<line class="grid-l" x1="${padL}" x2="${w - padR}" y1="${gy.toFixed(1)}" y2="${gy.toFixed(1)}"/>`).join("");
    let labels = "";
    if (opt.labels) {
      RT._pickLabels(opt.labels, dates.length).forEach((i) => {
        const anchor = i === dates.length - 1 ? "end" : "middle";
        labels += `<text class="axis-t" x="${X(i).toFixed(1)}" y="${h - 6}" text-anchor="${anchor}">${opt.labels[i]}</text>`;
      });
    }
    let lines = "";
    names.forEach((name) => {
      const vals = seriesByName[name];
      const d = vals.map((v, i) => (i ? " L" : "M") + X(i).toFixed(1) + " " + Y(v).toFixed(1)).join("");
      const len = pathLength(d).toFixed(0);
      const color = colorsByName[name];
      const lx = X(vals.length - 1), ly = Y(vals[vals.length - 1]);
      lines += `<path class="ln draw" style="stroke:${color}" d="${d}" stroke-dasharray="${len}" stroke-dashoffset="${len}"/>`
        + `<circle class="end fade-late" style="fill:${color}" cx="${lx.toFixed(1)}" cy="${ly.toFixed(1)}" r="4.5"/>`
        + `<text class="lbl fade-late" style="fill:${color}" x="${(lx + 10).toFixed(1)}" y="${(ly + 4).toFixed(1)}">${CH_LABEL[name]}</text>`;
    });
    /* areaChart는 오른쪽 여백(padR)에 최대·최소값을 쓰지만 여기서는 쓰지 않는다 — 그 자리는
       선 끝 채널 라벨이 쓰고, 맨 위 선의 라벨이 최대값 숫자와 정확히 같은 높이에 겹친다
       (실측 확인). 여백은 한쪽만 쓸 수 있어서, 채널별 모드는 "어느 선이 어느 채널인지"를
       택했다 — 값의 크기는 `누적` 모드가 보여준다. */
    el.innerHTML = `<svg viewBox="0 0 ${w} ${h}" preserveAspectRatio="none" style="aspect-ratio:${w}/${h}">`
      + `${grid}${lines}${labels}</svg>`;
  }
  /* payload.series는 두 페이지 모두 **종류별 사전**이다(v4.1 §11.3) —
     요약 `{views, contents, comments}`, 콘텐츠 성과 `{views, likes, comments, rate}`.
     상위노출은 payload 자체가 없다(스파크 두 벌을 Python이 미리 그려둔다). */
  function series(kind) {
    const s = payload.series;
    return s ? (s[kind] || null) : null;
  }
  const axisLabels = (dates) => dates.map((d) => RT._safeLabel(d.slice(5).replace("-", ".")));
  /* 세그먼트 3모드(§11.2). 채널 필터와 독립이라 둘을 조합한다.
     남은 SVG를 두면 꺼진 채널·다른 모드의 곡선이 화면에 남으므로 그릴 수 없을 때는 반드시 `.empty`. */
  function renderHero(hero, sv) {
    if (state.hero === "channel") {
      const names = RT._knownChannels(Object.keys(sv.by_channel)).filter((ch) => state.on.has(ch));
      if (!names.length || sv.dates.length < 3) return void (hero.innerHTML = EMPTY_HERO);
      const byName = {}, colors = {};
      names.forEach((ch) => { byName[ch] = sv.by_channel[ch]; colors[ch] = "var(--ch-" + ch + ")"; });
      return multiLine(hero, sv.dates, byName, colors, { w: 1140, h: 230, padR: 64, labels: axisLabels(sv.dates) });
    }
    let dates = sv.dates, vals = RT.combineSeries(sv.dates, sv.by_channel, state.on);
    if (state.hero === "daily") { vals = RT.dailyDiff(vals); dates = sv.dates.slice(1); }
    if (vals.length >= 3 && root.areaChart) {
      root.areaChart(hero, vals, { w: 1140, h: 230, ink: true, padR: 64, labels: axisLabels(dates) });
    } else if (vals.length < 3) {
      hero.innerHTML = EMPTY_HERO;
    }
  }
  /* 범례만 모드에 따라 바뀐다 — 채널별 모드는 선 색을 읽을 수 있어야 하므로
     `전체 누적` 점 하나를 선택 채널 점들로 교체한다. */
  function renderHeroLabels() {
    $$(".seg span[data-hero]").forEach((sp) => sp.classList.toggle("on", sp.dataset.hero === state.hero));
    const legend = $("[data-hero-legend]");
    if (!legend) return;
    if (state.hero === "channel") {
      const sv = series("views") || { by_channel: {} };
      const names = RT._knownChannels(Object.keys(sv.by_channel)).filter((ch) => state.on.has(ch));
      legend.innerHTML = names
        .map((ch) => '<i class="dot" style="background:var(--ch-' + ch + ')"></i> ' + CH_LABEL[ch])
        .join(" ");
    } else {
      legend.innerHTML = '<i class="dot" style="background:var(--ink)"></i> '
        + (state.hero === "daily" ? HERO_DAILY : HERO_LEGEND_CUM);
    }
  }
  function renderCharts() {
    const hero = $('[data-chart="hero"]'), sv = series("views");
    if (hero && sv) {
      renderHero(hero, sv);
      renderHeroLabels();
    }
    /* 스트립 스파크: 페이지에 실제로 있는 `[data-spark]`만, 같은 키의 payload 시리즈로 채운다.
       상위노출의 `data-spark="keywords"`처럼 payload에 없는 키는 Python이 그려둔 SVG를 그대로 둔다. */
    $$("[data-spark]").forEach((box) => {
      const k = box.dataset.spark, s = series(k);
      if (!s) return;
      let dates = s.dates, vals, unit = "";
      if (k === "rate") {
        const pts = RT.combineRate(s.dates, s.by_channel, state.on);
        dates = pts.map((p) => p[0]);
        vals = pts.map((p) => p[1]);
        unit = "pt";
      } else {
        vals = RT.combineSeries(s.dates, s.by_channel, state.on);
      }
      if (vals.length >= 2 && root.sparkline) root.sparkline(box, vals, { ink: true, w: 112, h: 30 });
      else if (vals.length < 2) box.innerHTML = "";
      const d = $('[data-delta="' + k + '"]');
      if (!d) return;
      if (vals.length >= 2) {
        const lab = RT.deltaLabel(RT.deltaOverDays(dates, vals, 7), vals.length, unit);
        d.textContent = lab.text;
        d.className = "delta " + lab.dir;
      } else if (d.dataset.static) {
        // 2점 미만이면 Python이 쓰던 정적 캡션으로 되돌린다(§11.3) — 문구는 서버가 심어준다.
        d.textContent = d.dataset.static;
        d.className = "delta flat";
      }
    });
  }

  function bindControls() {
    document.addEventListener("click", (e) => {
      const t = e.target;
      if (!t || !t.closest) return;
      const chip = t.closest(".chip[data-ch]");
      if (chip) {
        const ch = chip.dataset.ch;
        if (state.on.has(ch)) { if (state.on.size > 1) state.on.delete(ch); }   // 마지막 하나는 끌 수 없다(§4.1)
        else state.on.add(ch);
        return applyState();
      }
      const sort = t.closest(".seg span[data-sort]");
      if (sort) { state.sort = sort.dataset.sort; return applyState(); }
      if (t.closest(".chip[data-toggle='hide-empty']")) { state.hideEmpty = !state.hideEmpty; return applyState(); }
      const kw = t.closest(".kw-chips .chip[data-kw]");
      if (kw) { state.kw = kw.dataset.kw; return applyState(); }
      const v = t.closest(".seg span[data-variant]");
      if (v) { state.variant = v.dataset.variant; return applyState(); }
      const dp = t.closest(".seg span[data-depth]");
      if (dp) { state.depth = dp.dataset.depth; return applyState(); }
      const b = t.closest(".seg span[data-basis]");
      if (b) { state.basis = b.dataset.basis; return applyState(); }
      const hero = t.closest(".seg span[data-hero]");
      if (hero) {
        state.hero = hero.dataset.hero;
        return renderCharts();          // 히어로만 바뀐다 — 표·스트립을 다시 계산할 이유가 없다
      }
      const tr = t.closest(".list tbody tr[data-cid]");
      if (tr) {
        if (tr.dataset.cid === state.selected) return;
        state.selected = tr.dataset.cid;
        return applySelection();
      }
      const nav = t.closest("a[data-nav]");
      if (nav) {
        e.preventDefault();
        const name = nav.dataset.nav;
        try {
          const a = $$('a[data-testid="stPageLink-NavLink"]', root.parent.document)
            .filter((x) => (x.innerText || "").trim() === name)[0];
          if (a) a.click();
          else root.parent.location.href = "/" + encodeURIComponent(name.replace(/\s+/g, ""));
        } catch (err) {}
        return;
      }
      const ex = t.closest("[data-export]");
      if (ex && !ex.hasAttribute("aria-disabled")) {
        const md = $("#export-md");
        if (!md) return;
        // frame.py가 `</`를 `<\/`로 막아 심었으므로 되돌린다.
        const blob = new Blob([md.textContent.replace(/<\\\//g, "</")], { type: "text/markdown;charset=utf-8" });
        const a = document.createElement("a");
        a.href = URL.createObjectURL(blob);
        a.download = md.dataset.filename || "리포트.md";
        document.body.appendChild(a);
        a.click();
        a.remove();
        setTimeout(() => URL.revokeObjectURL(a.href), 1000);
      }
    });
  }

  bindControls();
  applyState();
  booted = true;
  /* 스트림릿 레이아웃이 늦게 자리를 잡으므로 높이를 몇 번 더 맞춘다(스펙 §6). */
  root.addEventListener("load", fit);
  try { root.parent.addEventListener("resize", fit); } catch (e) {}
  setTimeout(fit, 500);
  setTimeout(fit, 1500);
  setInterval(theme, 400);
})(typeof window !== "undefined" ? window : globalThis);
