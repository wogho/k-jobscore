/* k-jobs 웹 화면 — 외부 라이브러리 없이. 점수·판정은 서버(/api/jobs)가 지금 설정으로 계산하고, 화면은 거르기·정렬·표시만 한다. */
"use strict";

const $ = (s, el = document) => el.querySelector(s);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const num = (n) => Number(n || 0).toLocaleString("ko-KR");
const store = {
  get(k, d) { try { const v = localStorage.getItem("kj." + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem("kj." + k, JSON.stringify(v)); } catch { /* 저장 못 해도 화면은 동작 */ } },
};

async function api(path, body) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const d = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
  return d;
}

const SIDO = { 경상남도: "경남", 경상북도: "경북", 전라남도: "전남", 전라북도: "전북", 충청남도: "충남", 충청북도: "충북" };
function region(loc) {
  const w = (loc || "").trim().split(/\s+/)[0] || "";
  if (!w) return "기타";
  if (SIDO[w]) return SIDO[w];
  return w.replace(/전체$/, "").replace(/특별자치시$|특별자치도$|특별시$|광역시$|도$/, "") || "기타";
}
function due(d) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(d || "")) return { text: d === "채용시" ? "채용 시 마감" : "상시", days: null };
  const days = Math.ceil((new Date(d + "T23:59:59").getTime() - Date.now()) / 86400000);
  const [, m, dd] = d.split("-").map(Number);
  return { text: days < 0 ? "마감" : days === 0 ? "오늘 마감" : `${m}월 ${dd}일 마감`, days };
}
const isNew = (j) => Date.now() - new Date(j.first_seen).getTime() < 24 * 3600 * 1000;
const EDU_LABEL = { 미표기: "학력 표시 없음", 무관: "학력 무관" };
const CAREER = [["all", "전체"], ["new", "신입·경력 무관"], ["intern", "인턴"], ["exp", "경력 있음(설정 범위 안)"]];
const DUE = [["all", "전체"], ["week", "7일 안에 마감"], ["open", "상시·채용 시 마감"]];
const STAGE = { detail: "제목과 상세(이미지 글자 포함)를 반영한 점수", pending: "제목만 반영한 점수, 상세 확인 전", title_minus: "제목에 감점 단어가 있어 상세는 보지 않음",
  veto: "즉시 제외 단어가 있음", must_missing: "필수 단어가 없음" };
const VTXT = { career: { ok: "경력 조건 맞음", fail: "경력 조건 불일치", none: "경력 표기 없음" }, edu: { ok: "학력 조건 맞음", fail: "학력 조건 불일치", none: "학력 표기 없음" } };
const PAGE = 50;

const S = {
  data: null, err: "", page: 1, per: store.get("per", 4), panel: false,
  f: { q: "", sites: null, roles: null, career: "all", edu: null, due: "all", regs: [], sort: "score", min: 0, hideDrop: true, holdOnly: false },
};

/* ── 목록 ── */
function filtered() {
  const f = S.f, s = f.q.trim().toLowerCase();
  const out = S.data.items.filter((j) => {
    if (!f.sites.includes(j.source) || !f.edu.includes(j.edu) || !j.cats.some((c) => f.roles.includes(c))) return false;
    if (f.career === "new" && !/신입|무관/.test(j.career)) return false;
    if (f.career === "intern" && !/인턴/.test(j.title + j.emp_type)) return false;
    if (f.career === "exp" && !((j.career_min ?? 0) >= 1)) return false;
    const x = due(j.deadline).days;
    if (f.due === "week" && !(x !== null && x >= 0 && x <= 7)) return false;
    if (f.due === "open" && x !== null) return false;
    if (f.regs.length && !f.regs.includes(region(j.location))) return false;
    if (j.score < f.min) return false;
    if (f.hideDrop && (j.verdict === "drop" || j.stage === "veto" || j.stage === "must_missing")) return false;
    if (f.holdOnly && j.verdict !== "hold") return false;
    return !s || `${j.title} ${j.company} ${j.location}`.toLowerCase().includes(s);
  });
  if (f.sort === "due") out.sort((a, b) => (due(a.deadline).days ?? 9999) - (due(b.deadline).days ?? 9999));
  if (f.sort === "score") out.sort((a, b) => b.score - a.score || (b.stage === "detail") - (a.stage === "detail"));
  return out;
}

function ring(j) {
  const r = 19, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, j.score));
  return `<span class="kj-ring kj-ring--${{ high: "hi", mid: "mid", low: "low", bad: "bad" }[j.tier]} ${j.stage === "pending" ? "is-pending" : ""}" title="적합도 ${v}점 · ${esc(STAGE[j.stage])}" aria-label="적합도 ${v}점">
    <svg viewBox="0 0 48 48" aria-hidden="true"><circle class="kj-ring__track" cx="24" cy="24" r="${r}"/>
    <circle class="kj-ring__bar" cx="24" cy="24" r="${r}" stroke-dasharray="${(c * v) / 100} ${c}" transform="rotate(-90 24 24)"/></svg>
    <span class="kj-ring__n">${v}</span></span>`;
}

function why(j) {
  const chips = [];
  for (const h of j.hits || []) {
    if (h.where === "missing") { chips.push(`<span class="kj-kw kj-kw--must" title="필수 단어">필수 없음: ${esc(h.word)}</span>`); continue; }
    if (h.kind === "veto") { chips.push(`<span class="kj-kw kj-kw--veto" title="즉시 제외 단어">제외: ${esc(h.found || h.word)}</span>`); continue; }
    const plus = h.pts >= 0, cls = `kj-kw kj-kw--${plus ? "plus" : "minus"}${h.where === "title" ? " is-title" : ""}`;
    chips.push(`<span class="${cls}" title="${h.where === "title" ? "제목" : "상세"} ${plus ? "+" : ""}${h.pts}점">${plus ? "+" : "−"}${esc(h.found || h.word)}</span>`);
  }
  if (j.stage === "detail") {
    for (const k of ["career", "edu"]) {
      const v = k === "career" ? j.career_v : j.edu_v;
      if (v) chips.push(`<span class="kj-v kj-v--${v}" title="${esc(v === "fail" ? j.v_note : "")}">${v === "ok" ? "✓ " : v === "fail" ? "✕ " : ""}${VTXT[k][v]}</span>`);
    }
    if ((j.v_note || "").includes("전공 필수")) chips.push(`<span class="kj-v kj-v--hold">전공 필수</span>`);
    if (j.verdict === "hold") chips.push(`<span class="kj-v kj-v--hold" title="설정에서 '보류'로 정한 경우">보류</span>`);
    if (j.d_images > 0) chips.push(`<span class="kj-v">이미지 ${j.d_images}장 글자 확인</span>`);
  }
  if (j.stage === "pending") chips.push(`<span class="kj-v">상세 확인 전</span>`);
  if (j.stage === "title_minus") chips.push(`<span class="kj-v">제목 감점, 상세 생략</span>`);
  let ai = "";
  if (j.ai) {
    const flags = [j.ai.low_confidence ? "근거 부족" : "", j.ai.suspicious ? "공고에 지시문 같은 글 있음" : ""].filter(Boolean).join(", ");
    ai = `<p class="kj-ai"><b>AI ${j.ai.fit}점</b> ${esc(j.ai.summary)}${flags ? ` · ${esc(flags)}` : ""}${j.ai.strategy ? `<br>지원 전략: ${esc(j.ai.strategy)}` : ""}</p>`;
  }
  return `<p class="kj-why">${chips.join("")}</p>${ai}`;
}

function row(j) {
  const dd = due(j.deadline), roles = S.data.roles;
  return `<li><a class="kj-row" href="${esc(j.url)}" target="_blank" rel="noreferrer">${ring(j)}
    <div class="kj-row__main"><p class="kj-row__title">${esc(j.title)}</p>
      <p class="kj-row__meta">${esc(j.company)}${j.location ? `<span> · ${esc(j.location)}</span>` : ""}</p>
      <p class="kj-row__tags"><span class="kj-row__job">${esc(j.cats.map((c) => roles[c] || c).join(", "))}</span>${j.career ? `<span>${esc(j.career)}</span>` : ""}
        <span>${esc(EDU_LABEL[j.edu] || j.edu)}</span>${j.emp_type ? `<span>${esc(j.emp_type)}</span>` : ""}</p>${why(j)}</div>
    <div class="kj-row__side"><span class="kj-row__due ${dd.days !== null && dd.days <= 3 ? "is-soon" : ""}">${esc(dd.text)}</span>
      <span class="kj-row__src">${isNew(j) ? `<span class="kj-dot" aria-label="새 공고"></span>` : ""}${esc(S.data.sites[j.source])}</span></div></a></li>`;
}

function check(type, name, value, on, label, note, count) {
  return `<label class="kj-check"><input type="${type}" name="${name}" value="${esc(value)}" ${on ? "checked" : ""}>
    <span class="kj-check__label">${esc(label)}${note ? `<span class="kj-check__note">${esc(note)}</span>` : ""}</span>${count !== undefined ? `<span class="kj-check__n">${count}</span>` : ""}</label>`;
}

function renderShell() {
  const d = S.data, items = d.items;
  const last = d.runs.map((r) => r.at).sort().pop();
  const fresh = items.filter(isNew).length;
  $("#kj-app").innerHTML = `
    <header class="kj-head"><h1>신입·주니어 채용 공고</h1>
      <p class="kj-fact">공고 ${num(items.length)}건을 ${Object.values(d.sites).join(", ")}에서 모았습니다.${fresh ? ` 최근 24시간에 ${num(fresh)}건이 새로 올라왔습니다.` : ""}
      상세(이미지 글자 포함)를 확인한 공고는 ${num(d.checked)}건입니다.${last ? ` <span class="kj-muted">마지막 수집 ${esc(last.slice(5, 16).replace("T", " "))}</span>` : ""}</p></header>
    <div class="kj-sites" id="kj-sites" role="group" aria-label="채용 사이트"></div>
    <div class="kj-layout">
      <aside class="kj-filters" id="kj-filters" aria-label="필터"></aside>
      <section class="kj-results" aria-label="공고 목록">
        <div class="kj-bar">
          <input class="kj-search" id="kj-q" type="search" placeholder="직무, 회사, 지역으로 찾기" aria-label="공고 검색">
          <button class="kj-btn kj-btn--secondary kj-bar__filters" id="kj-open-filters" type="button">필터</button>
          <select class="kj-select kj-per" id="kj-per" aria-label="한 번에 보이는 공고 수">${[4, 6, 8, 10, 20].map((n) => `<option value="${n}" ${n === S.per ? "selected" : ""}>${n}개씩 보기</option>`).join("")}</select>
          <select class="kj-select" id="kj-sort" aria-label="정렬"><option value="score">적합도 순</option><option value="new">최신 순</option><option value="due">마감 임박 순</option></select>
        </div>
        <p class="kj-count" id="kj-count"></p>
        <div class="kj-scroll" id="kj-scroll"><ul class="kj-rows" id="kj-rows"></ul></div>
        <nav class="kj-pages" id="kj-pages" aria-label="페이지"></nav>
        <p class="kj-empty" id="kj-empty" hidden>조건에 맞는 공고가 없습니다. 필터를 줄여 보세요.</p>
      </section>
    </div>`;
  $("#kj-q").addEventListener("input", (e) => { S.f.q = e.target.value; S.page = 1; renderList(); });
  $("#kj-per").addEventListener("change", (e) => { S.per = Number(e.target.value); store.set("per", S.per); fit(); });
  $("#kj-sort").addEventListener("change", (e) => { S.f.sort = e.target.value; S.page = 1; renderList(); });
  $("#kj-open-filters").addEventListener("click", () => { S.panel = true; renderFilters(); });
  $("#kj-sites").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-site]"); if (!b) return;
    toggle(S.f.sites, b.dataset.site); S.page = 1; renderSites(); renderList();
  });
  $("#kj-pages").addEventListener("click", (e) => {
    const b = e.target.closest("button[data-page]"); if (!b || b.disabled) return;
    S.page = Number(b.dataset.page); renderList(); $("#kj-count").scrollIntoView({ block: "nearest" });
  });
  bindFilters();
  renderSites(); renderFilters(); renderList();
}

function toggle(arr, v) { const i = arr.indexOf(v); if (i >= 0) { if (arr.length > 1) arr.splice(i, 1); } else arr.push(v); }

function renderSites() {
  const items = S.data.items;
  $("#kj-sites").innerHTML = Object.entries(S.data.sites).map(([s, name]) => {
    const on = S.f.sites.includes(s);
    return `<button type="button" class="kj-site ${on ? "is-on" : ""}" aria-pressed="${on}" data-site="${s}"><span class="kj-site__check" aria-hidden="true">${on ? "✓" : ""}</span>
      <span class="kj-site__name">${esc(name)}</span><span class="kj-site__n">${items.filter((j) => j.source === s).length}</span></button>`;
  }).join("");
}

function renderFilters() {
  const d = S.data, f = S.f, items = d.items;
  const regions = Object.entries(items.reduce((c, j) => { const r = region(j.location); c[r] = (c[r] || 0) + 1; return c; }, {})).sort((a, b) => b[1] - a[1]).slice(0, 12);
  const drops = items.filter((j) => j.verdict === "drop" || j.stage === "veto" || j.stage === "must_missing").length;
  const holds = items.filter((j) => j.verdict === "hold").length;
  const edus = [...new Set(items.map((j) => j.edu))].sort();
  const el = $("#kj-filters");
  el.classList.toggle("is-open", S.panel);
  el.innerHTML = `<div class="kj-filters__top"><h2>필터</h2><button class="kj-link" type="button" data-act="reset">초기화</button></div>
    <fieldset><legend>적합도</legend>
      <label class="kj-range"><span>최소 점수 <b id="kj-min-v">${f.min}점</b></span><input type="range" min="0" max="100" step="5" value="${f.min}" data-f="min" aria-label="최소 적합도 점수"></label>
      ${check("checkbox", "hideDrop", "1", f.hideDrop, "조건 불일치·제외 숨기기", `상세 확인 불일치·즉시 제외·필수 없음 ${drops}건`)}
      ${check("checkbox", "holdOnly", "1", f.holdOnly, "보류만 보기", `표기 없음 등 보류 ${holds}건`)}
      <button class="kj-btn kj-btn--secondary kj-set-btn" type="button" data-act="settings">점수·조건 설정</button></fieldset>
    <fieldset><legend>직무</legend>${Object.entries(d.roles).map(([k, l]) => check("checkbox", "roles", k, f.roles.includes(k), l, "", items.filter((j) => j.cats.includes(k)).length)).join("")}</fieldset>
    <fieldset><legend>경력</legend>${CAREER.map(([k, l]) => check("radio", "career", k, f.career === k, l)).join("")}</fieldset>
    <fieldset><legend>마감</legend>${DUE.map(([k, l]) => check("radio", "due", k, f.due === k, l)).join("")}</fieldset>
    <fieldset><legend>지역</legend>${regions.map(([r, n]) => check("checkbox", "regs", r, f.regs.includes(r), r, "", n)).join("")}<p class="kj-hint">아무것도 고르지 않으면 전체 지역입니다.</p></fieldset>
    <fieldset><legend>학력 표기</legend>${edus.map((e) => check("checkbox", "edu", e, f.edu.includes(e), EDU_LABEL[e] || e)).join("")}</fieldset>
    <button class="kj-btn kj-btn--primary kj-filters__done" type="button" data-act="done">공고 보기</button>`;
}

function bindFilters() {
  const el = $("#kj-filters");
  el.addEventListener("input", (e) => {
    if (e.target.dataset.f === "min") { S.f.min = Number(e.target.value); $("#kj-min-v").textContent = `${S.f.min}점`; S.page = 1; renderList(); }
  });
  el.addEventListener("change", (e) => {
    const t = e.target, f = S.f;
    if (t.name === "hideDrop" || t.name === "holdOnly") f[t.name] = t.checked;
    else if (t.name === "career" || t.name === "due") f[t.name] = t.value;
    else if (t.name === "regs") f.regs = t.checked ? [...f.regs, t.value] : f.regs.filter((x) => x !== t.value);
    else if (t.name === "roles" || t.name === "edu") toggle(f[t.name], t.value);
    else return;
    S.page = 1; renderFilters(); renderList();
  });
  el.addEventListener("click", (e) => {
    const a = e.target.closest("[data-act]")?.dataset.act;
    if (a === "reset") { resetFilters(); renderSites(); renderFilters(); renderList(); }
    if (a === "settings") openSettings();
    if (a === "done") { S.panel = false; renderFilters(); }
  });
}

function resetFilters() {
  const d = S.data;
  Object.assign(S.f, { sites: Object.keys(d.sites), roles: Object.keys(d.roles), edu: [...new Set(d.items.map((j) => j.edu))], career: "all", due: "all", regs: [], min: 0, hideDrop: true, holdOnly: false });
}

function renderList() {
  const shown = filtered(), pages = Math.max(1, Math.ceil(shown.length / PAGE));
  if (S.page > pages) S.page = pages;
  const from = Math.max(1, Math.min(S.page - 4, pages - 9));
  $("#kj-count").textContent = `공고 ${num(shown.length)}건` + (pages > 1 ? ` · ${(S.page - 1) * PAGE + 1}~${Math.min(S.page * PAGE, shown.length)}번째` : "");
  $("#kj-rows").innerHTML = shown.slice((S.page - 1) * PAGE, S.page * PAGE).map(row).join("");
  $("#kj-scroll").scrollTop = 0;
  $("#kj-empty").hidden = shown.length > 0;
  $("#kj-open-filters").textContent = "필터";
  $("#kj-pages").innerHTML = pages > 1 ? [`<button class="kj-page" type="button" data-page="${S.page - 1}" ${S.page === 1 ? "disabled" : ""} aria-label="이전 페이지">‹</button>`,
    ...Array.from({ length: Math.min(10, pages) }, (_, i) => from + i).map((n) => `<button class="kj-page" type="button" data-page="${n}" ${n === S.page ? 'aria-current="page"' : ""}>${n}</button>`),
    `<button class="kj-page" type="button" data-page="${S.page + 1}" ${S.page === pages ? "disabled" : ""} aria-label="다음 페이지">›</button>`].join("") : "";
  fit();
}

/* 안쪽 상자 높이 = 앞 n줄의 실제 높이 합(제목이 두 줄이어도 정확히 n개가 보이게) */
function fit() {
  const el = $("#kj-scroll"); if (!el) return;
  const rows = [...el.querySelectorAll(":scope > ul > li")].slice(0, S.per);
  el.style.height = rows.length ? `${rows.reduce((h, r) => h + r.getBoundingClientRect().height, 0) + 2}px` : "";
}
window.addEventListener("resize", fit);

/* ── 설정 ── */
let D = null;   // 고치는 중인 설정(저장 전)
const TABS = [["score", "점수·단어"], ["cond", "조건"], ["collect", "수집"], ["ai", "AI 판단"]];
let tab = "score", META = null, sel = -1;   // sel: 세부 설정을 펼친 단어(칩을 누르면 펼침)

async function openSettings() {
  try { META = await api("/api/config"); } catch (e) { alert(`설정을 불러오지 못했습니다. ${e.message}`); return; }
  D = JSON.parse(JSON.stringify(META.cfg)); sel = -1;
  renderModal("");
}
const close = () => { $("#kj-modal-root").innerHTML = ""; D = null; };

function field(path, label, hint, type = "number", extra = "") {
  const v = path.split(".").reduce((o, k) => o[k], D);
  if (type === "checkbox") return `<label class="kj-inline kj-wide"><input type="checkbox" data-path="${path}" ${v ? "checked" : ""}> ${esc(label)}${hint ? ` <small>${esc(hint)}</small>` : ""}</label>`;
  if (type === "list") return `<label class="kj-wide">${esc(label)}<small>${esc(hint)}</small><textarea data-path="${path}" data-type="list">${esc((v || []).join(", "))}</textarea></label>`;
  return `<label>${esc(label)}${hint ? `<small>${esc(hint)}</small>` : ""}<input type="${type}" data-path="${path}" value="${esc(v)}" ${extra}></label>`;
}
function choice(path, label, hint, opts) {
  const v = path.split(".").reduce((o, k) => o[k], D);
  return `<label>${esc(label)}${hint ? `<small>${esc(hint)}</small>` : ""}<select data-path="${path}">${opts.map(([k, l]) => `<option value="${esc(k)}" ${k === v ? "selected" : ""}>${esc(l)}</option>`).join("")}</select></label>`;
}
const HANDLE = [["keep", "통과"], ["hold", "보류(남기고 표시)"], ["drop", "제외"]];
const GROUPS = [["plus", "가점 단어", ""], ["minus", "감점 단어", ""], ["veto", "즉시 제외 단어", "있으면 0점"], ["must", "필수 단어", "제목·상세 어디에도 없으면 0점"]];
const wtext = (w) => (Array.isArray(w.word) ? w.word.join("·") : w.word);
const custom = (w) => w.title !== undefined || w.body !== undefined || (w.where && w.where !== "both") || (w.match && w.match !== "auto");

/* 단어 묶음 — 평소에는 칩만, 칩을 누르면 그 단어의 세부 설정이 아래에 펼쳐진다 */
function wordGroup(kind, label, note) {
  const items = D.score.words.map((w, i) => [w, i]).filter(([w]) => w.kind === kind);
  const open = items.find(([, i]) => i === sel);
  const opt = (k, v, list) => list.map(([x, l]) => `<option value="${x}" ${(v || list[0][0]) === x ? "selected" : ""}>${l}</option>`).join("");
  let panel = "";
  if (open) {
    const [w, i] = open, fixed = w.kind === "veto" || w.kind === "must";
    panel = `<div class="kj-wedit" data-i="${i}">
      <label class="kj-wide">단어<small>쉼표로 같은 뜻 묶기</small><input data-w="word" value="${esc(Array.isArray(w.word) ? w.word.join(", ") : w.word)}"></label>
      <label>종류<select data-w="kind">${opt("kind", w.kind, [["plus", "가점"], ["minus", "감점"], ["veto", "즉시 제외"], ["must", "필수"]])}</select></label>
      <label>보는 곳<select data-w="where">${opt("where", w.where, [["both", "제목·상세 둘 다"], ["title", "제목만"], ["body", "상세만"]])}</select></label>
      ${fixed ? "" : `<label>제목 점수<small>비우면 기본</small><input type="number" data-w="title" value="${w.title ?? ""}" placeholder="기본"></label>
      <label>상세 점수<small>비우면 기본</small><input type="number" data-w="body" value="${w.body ?? ""}" placeholder="기본"></label>`}
      <label>찾는 방식<select data-w="match">${opt("match", w.match, [["auto", "자동"], ["contains", "포함"], ["word", "낱말 단위"], ["regex", "정규식"]])}</select></label>
      <button type="button" class="kj-link" data-act="unsel">접기</button></div>`;
  }
  return `<div class="kj-words"><p class="kj-words__label">${label} <span>${items.length}개${note ? ` · ${note}` : ""}</span></p>
    ${items.length ? `<div class="kj-words__list">${items.map(([w, i]) => `<span class="kj-kw kj-kw--${kind} ${i === sel ? "is-sel" : ""}">
      <button type="button" class="kj-kw__name" data-act="pick" data-i="${i}" title="세부 설정">${esc(wtext(w))}${custom(w) ? " ⚙" : ""}</button>
      <button type="button" data-act="del" data-i="${i}" aria-label="${esc(wtext(w))} 빼기">×</button></span>`).join("")}</div>` : ""}
    ${panel}
    <div class="kj-words__add"><input id="kj-new-${kind}" data-kind="${kind}" placeholder="단어 입력 후 Enter" aria-label="${label} 추가">
      <button type="button" class="kj-btn kj-btn--secondary" data-act="add" data-kind="${kind}">추가</button></div></div>`;
}

function tabBody() {
  if (tab === "score") {
    const num = (path, label, hint, extra = "") => `<label class="kj-num"><span>${esc(label)}<small>${esc(hint)}</small></span>
      <input type="number" data-path="${path}" value="${esc(path.split(".").reduce((o, k) => o[k], D))}" ${extra}></label>`;
    return `<div class="kj-nums">
        ${num("score.base", "시작 점수", "모든 공고", 'min="0" max="100"')}${num("score.defaults.plus_title", "제목 가점", "단어 하나당", 'min="0" max="100"')}
        ${num("score.defaults.minus_title", "제목 감점", "단어 하나당", 'min="-100" max="0"')}${num("score.defaults.plus_body", "상세 가점", "단어 하나당", 'min="0" max="50"')}
        ${num("score.defaults.minus_body", "상세 감점", "단어 하나당", 'min="-50" max="0"')}${num("score.body_cap", "상세 점수 한도", "상세 합계 ±", 'min="0" max="100"')}</div>
      ${GROUPS.map(([kind, label, note]) => wordGroup(kind, label, note)).join("")}
      <p class="kj-hint">단어를 누르면 그 단어만의 점수·보는 곳·찾는 방식을 정할 수 있습니다. 쉼표로 여러 단어를 한 번에 넣으면 같은 뜻으로 묶여 한 번만 셉니다.
        영문 4자 이하(OP, IDC, k8s 등)는 낱말 단위로만 찾습니다.</p>
      <details class="kj-more"><summary>점수 색 기준·상세 생략</summary><div class="kj-form">
        ${field("score.tiers.high", "높음 기준", "파란 원")}${field("score.tiers.mid", "보통 기준", "검은 원")}${field("score.tiers.low", "낮음 기준", "주황 원, 그 아래는 빨강")}
        ${field("score.title_minus_skips_detail", "제목에 감점 단어가 있으면 상세를 보지 않기", "끄면 모든 공고의 상세를 읽습니다(느려짐)", "checkbox")}</div></details>`;
  }
  if (tab === "cond") return `<div class="kj-form">
      ${choice("conditions.education.my_level", "내 학력", "이보다 높은 학력을 요구하면 불일치", META.levels.map((l) => [l, l === "무관" ? "학력 없음/무관" : l]))}
      ${choice("conditions.education.unlabeled", "학력 표기가 없을 때", "", HANDLE)}
      ${choice("conditions.education.major_required", "'관련 전공 필수'일 때", "", HANDLE)}
      ${field("conditions.education.equivalent_ok", "'학사 이상 또는 이에 준하는 경험'은 학력 필수가 아닌 것으로 보기", "", "checkbox")}
      ${field("conditions.career.max_required_years", "허용할 요구 경력", "이 연수 이하를 요구하는 공고까지(0 = 신입만)", "number", 'min="0" max="30"')}
      ${choice("conditions.career.unlabeled", "경력 표기가 없을 때", "", HANDLE)}
      ${field("conditions.career.include_intern", "인턴 공고 포함", "", "checkbox")}
      ${field("conditions.open_days", "상시 공고 보관 일수", "마감일 없는 공고를 처음 본 뒤 며칠까지", "number", 'min="1" max="365"')}
      ${field("conditions.employment_exclude", "제외할 고용형태·단어", "쉼표로 구분(예: 파견, 아르바이트)", "list")}
      ${field("conditions.regions", "지역 제한", "비우면 전체(예: 서울, 경기)", "list")}
      ${field("conditions.companies_exclude", "제외할 회사", "쉼표로 구분, 이름 일부만 써도 됩니다", "list")}
      ${field("conditions.companies_only", "이 회사만", "비우면 제한 없음", "list")}
      <p class="kj-hint kj-wide">조건 중 경력·학력 표기·고용형태·지역·회사는 다음 수집부터 적용되고, 상세 판정(불일치·보류)은 저장하는 즉시 반영됩니다.</p></div>`;
  if (tab === "collect") return `<div class="kj-form">
      ${Object.entries(META.sites).map(([s, n]) => `<label class="kj-inline"><input type="checkbox" data-path="sources.${s}" ${D.sources[s] ? "checked" : ""}> ${esc(n)}</label>`).join("")}
      ${field("queries", "검색어(사람인·잡코리아·리멤버)", "쉼표로 구분", "list")}
      ${field("wanted_queries", "원티드 검색어", "쉼표로 구분", "list")}
      ${field("pages", "검색어당 최대 쪽 수", "최신 순, 이미 본 공고가 많으면 일찍 멈춤", "number", 'min="1" max="20"')}
      ${field("network.delay_sec", "요청 간격(초)", "사이트에 부담을 주지 않게 3초 이상 권장", "number", 'min="1" max="60"')}
      ${field("detail.enabled", "상세 확인(본문 + 이미지 글자)", "", "checkbox")}
      ${choice("detail.ocr", "이미지 글자 읽기", "tesseract와 한국어 데이터가 필요", [["tesseract", "tesseract"], ["none", "읽지 않음"]])}
      ${field("detail.images_max", "공고당 읽을 이미지 수", "큰 것부터", "number", 'min="0" max="12"')}
      <p class="kj-hint kj-wide">직무 분류(roles)와 프록시는 config.json에서 고칩니다. 직무를 바꾼 뒤에는 <code>k-jobs reclassify</code>를 실행하세요.</p></div>`;
  return `<div class="kj-form">
      ${field("ai.enabled", "AI 판단 켜기", "기본은 꺼짐. 단어 규칙을 통과한 공고만 보냅니다", "checkbox")}
      ${choice("ai.provider", "AI 종류", "", [["cli", "설치된 AI 명령어(키 없음)"], ["openai", "OpenAI 호환(OpenAI·Ollama·OpenRouter 등)"], ["anthropic", "Anthropic"]])}
      ${choice("ai.cli", "AI 명령어", "AI 종류가 '설치된 AI 명령어'일 때", [["auto", "자동(찾은 것)"], ["claude", "claude"], ["codex", "codex"], ["gemini", "gemini"]])}
      ${field("ai.base_url", "주소", "API 방식일 때. Ollama 예: http://localhost:11434/v1", "text")}
      ${field("ai.model", "모델 이름", "", "text")}
      ${field("ai.api_key_env", "API 키 환경변수 이름", "키 자체는 여기에 넣지 않습니다", "text")}
      ${field("ai.weight", "AI 점수 비중", "0~1, 최종 = 규칙×(1-비중) + AI×비중", "number", 'min="0" max="1" step="0.05"')}
      ${field("ai.min_rule_score", "보낼 최소 규칙 점수", "비용 제어", "number", 'min="0" max="100"')}
      ${field("ai.max_per_run", "한 번에 보낼 최대 건수", "", "number", 'min="0" max="500"')}
      ${field("ai.profile_file", "내 이력 요약 파일 경로", "연락처 등 개인정보는 빼 두세요", "text")}
      <label class="kj-wide">추가 판단 기준<small>예: 재택 가능하면 좋음, 스타트업보다 공공기관 선호</small><textarea data-path="ai.rubric">${esc(D.ai.rubric)}</textarea></label>
      <p class="kj-hint kj-wide">설정 없이 쓰려면: 이 저장소를 AI 에이전트(Claude Code·Codex·Gemini CLI 등)로 열고 "공고 판정해 줘"라고 하면 그 AI가 직접 판정합니다(AGENTS.md).
        AI는 공고 원문을 인용해야 하고, 인용이 원문에 없으면 그 판단은 버립니다. 즉시 제외·학력/경력 불일치는 AI가 뒤집지 못합니다.</p></div>`;
}

function renderModal(msg) {
  $("#kj-modal-root").innerHTML = `<div class="kj-modal" role="dialog" aria-modal="true" aria-labelledby="kj-set-h"><div class="kj-modal__box">
    <div class="kj-modal__head"><h2 id="kj-set-h">점수·조건 설정</h2><button class="kj-link" type="button" data-act="close">닫기</button></div>
    <ol class="kj-steps"><li>제목에서 단어를 먼저 봅니다. 즉시 제외 단어가 있으면 0점, 감점 단어가 있으면 상세를 보지 않습니다.</li>
      <li>나머지 공고는 상세 글과 이미지 속 글자까지 읽어 경력·학력 조건을 확인하고 점수를 더합니다.</li>
      <li>저장하면 모든 공고 점수에 바로 반영됩니다.</li></ol>
    <div class="kj-tabs" role="tablist">${TABS.map(([k, l]) => `<button type="button" class="kj-tab" role="tab" aria-selected="${tab === k}" data-tab="${k}">${l}</button>`).join("")}</div>
    <div id="kj-tab-body">${tabBody()}</div>
    ${msg ? `<p class="kj-msg" role="status">${esc(msg)}</p>` : ""}
    <div class="kj-modal__foot"><select class="kj-select" id="kj-preset" aria-label="프리셋">${Object.entries(META.presets).map(([k, l]) => `<option value="${k}" ${k === D.preset ? "selected" : ""}>${esc(l)}</option>`).join("")}</select>
      <button class="kj-link" type="button" data-act="reset">이 프리셋으로 되돌리기</button>
      <button class="kj-btn kj-btn--secondary" type="button" data-act="close">취소</button><button class="kj-btn kj-btn--primary" type="button" data-act="save">저장</button></div>
  </div></div>`;
}

function setPath(path, v) { const ks = path.split("."); let o = D; ks.slice(0, -1).forEach((k) => { o = o[k]; }); o[ks.at(-1)] = v; }
function addWord(kind) {
  const inp = $(`#kj-new-${kind}`), v = inp.value.trim(); if (!v) return;
  const parts = v.split(",").map((x) => x.trim()).filter(Boolean);
  D.score.words.push({ word: parts.length > 1 ? parts : parts[0], kind });
  renderModal("");
  $(`#kj-new-${kind}`).focus();
}

document.addEventListener("change", (e) => {
  if (!D) return;
  const t = e.target;
  if (t.dataset.path) {
    const v = t.type === "checkbox" ? t.checked : t.dataset.type === "list" ? t.value.split(",").map((x) => x.trim()).filter(Boolean)
      : t.type === "number" ? Number(t.value) : t.value;
    setPath(t.dataset.path, v);
  } else if (t.dataset.w) {
    const w = D.score.words[Number(t.closest("[data-i]").dataset.i)], k = t.dataset.w;
    if (k === "word") { const parts = t.value.split(",").map((x) => x.trim()).filter(Boolean); w.word = parts.length > 1 ? parts : parts[0] || ""; }
    else if (k === "title" || k === "body") { if (t.value === "") delete w[k]; else w[k] = Number(t.value); }
    else w[k] = t.value;
    renderModal("");
  }
});
document.addEventListener("keydown", (e) => {
  if (!D) return;
  if (e.key === "Escape") close();
  if (e.key === "Enter" && e.target.dataset.kind) { e.preventDefault(); addWord(e.target.dataset.kind); }
});
document.addEventListener("click", async (e) => {
  if (e.target.id === "kj-open-set") return openSettings();
  if (!D) return;
  if (e.target.classList.contains("kj-modal")) return close();
  const tb = e.target.closest("[data-tab]"); if (tb) { tab = tb.dataset.tab; renderModal(""); return; }
  const a = e.target.closest("[data-act]")?.dataset.act;
  if (a === "close") close();
  const el = e.target.closest("[data-act]");
  if (a === "add") addWord(el.dataset.kind);
  if (a === "pick") { const i = Number(el.dataset.i); sel = sel === i ? -1 : i; renderModal(""); }
  if (a === "unsel") { sel = -1; renderModal(""); }
  if (a === "del") { const i = Number(el.dataset.i); D.score.words.splice(i, 1); sel = -1; renderModal(""); }
  if (a === "save" || a === "reset") {
    if (a === "reset" && !confirm("선택한 프리셋 기본값으로 되돌릴까요? 지금 설정은 사라집니다.")) return;
    try {
      const r = await api("/api/config", a === "reset" ? { reset: $("#kj-preset").value } : D);
      D = JSON.parse(JSON.stringify(r.cfg)); META.cfg = r.cfg;
      renderModal("저장했습니다. 점수에 바로 반영됩니다.");
      await load(true);
    } catch (err) { renderModal(`저장하지 못했습니다. ${err.message}`); }
  }
});

async function load(keep) {
  try {
    S.data = await api("/api/jobs");
    if (!keep || !S.f.sites) resetFilters();
    else { S.f.roles = S.f.roles.filter((r) => r in S.data.roles); if (!S.f.roles.length) S.f.roles = Object.keys(S.data.roles); }
    if (keep && $("#kj-rows")) { renderSites(); renderFilters(); renderList(); } else renderShell();
  } catch (e) {
    $("#kj-app").innerHTML = `<p class="kj-error" role="alert">공고를 불러오지 못했습니다. ${esc(e.message)}</p>`;
  }
}
load(false);
