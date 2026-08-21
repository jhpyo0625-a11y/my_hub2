'use strict';
/* =========================================================================
   renderer.js — [3] 동적 HTML 렌더링
   -------------------------------------------------------------------------
   Report 데이터(JS 객체) 하나를 받아 완성된 HTML 문자열을 돌려줍니다.
   마크업은 src/app.js 의 renderReport / renderHeader / renderCard /
   renderIntake / renderRecommend / renderIssues / renderSummary 와
   **클래스명·구조가 같습니다.** styles.css 를 그대로 쓰기 때문에 한 글자만
   달라져도 레이아웃이 어긋납니다. 고칠 때는 app.js 쪽도 함께 보세요.

   이 파일이 지키는 두 가지 약속
     · 데이터가 비어도 화면이 깨지지 않습니다 — 모든 값에 기본값이 있습니다.
     · 색과 기하값은 데이터가 아니라 여기서 정합니다 — tone 이름만 받습니다.
   ========================================================================= */

const fs = require('fs');
const path = require('path');

/* =========================================================================
   [A] 화면 토큰 — app.js 의 TONE · LEVEL · LAYOUT 과 같은 값입니다.
   ========================================================================= */
const TONE = {
  green : {fg:'#15803D', bg:'#EAF6EE', bd:'#C3E5CE', ink:'#14532D'},
  orange: {fg:'#C2410C', bg:'#FFF1E8', bd:'#FBD3B8', ink:'#9A3412'},
  red   : {fg:'#DC2626', bg:'#FDECEC', bd:'#F7D4D4', ink:'#991B1B'},
  crit  : {fg:'#991B1B', bg:'#FDECEC', bd:'#F7D4D4', ink:'#991B1B'},
  blue  : {fg:'#1E3A8A', bg:'#EAEFF9', bd:'#CBD8F0', ink:'#1E3A8A'},
  gray  : {fg:'#6B7280', bg:'#F3F4F6', bd:'#E5E7EB', ink:'#4B5563'},
};

const LEVEL = {
  over   : {tone:'crit'  , text:'매우 과다', rank:5},
  near   : {tone:'orange', text:'상한 근접', rank:4},
  low    : {tone:'blue'  , text:'부족'    , rank:3},
  none   : {tone:'blue'  , text:'미섭취'  , rank:2},
  unknown: {tone:'gray'  , text:'확인 불가', rank:1},
  met    : {tone:'green' , text:'충족'    , rank:0},
};

const LAYOUT = {maxCols:4, gaugeArc:163.4};   // 반원 길이 = π×52

/* =========================================================================
   [B] 유틸 — 값이 없을 때를 전제로 만든 작은 부품들
   ========================================================================= */
const esc = s => String(s ?? '').replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

/** 숫자 서식. 숫자가 아니면 '—' 를 돌려줍니다(NaN 이 화면에 찍히지 않도록). */
const fmt = v => Number.isFinite(Number(v))
  ? Number(v).toLocaleString('ko-KR', {maximumFractionDigits:1})
  : '—';

const S = (v, d = '') => (v === undefined || v === null || v === '') ? d : String(v);
const N = v => Number.isFinite(Number(v)) ? Number(v) : null;
const NUM = (v, d = 0) => Number.isFinite(Number(v)) ? Number(v) : d;
const A = v => Array.isArray(v) ? v : [];
const O = v => (v && typeof v === 'object' && !Array.isArray(v)) ? v : {};
const B = (v, d = false) => typeof v === 'boolean' ? v : d;

/** 모르는 tone 이 와도 회색으로 살아납니다. */
const toneOf  = t => TONE[t] || TONE.gray;
const levelOf = l => LEVEL[l] || LEVEL.unknown;

function gaugeSize(label){
  const digits = (String(label).match(/\d/g) || []).length;
  if(!digits) return 24;
  return digits === 1 ? 32 : digits === 2 ? 30 : digits === 3 ? 26 : 24;
}

const chip = (text, tone) => {
  const t = toneOf(tone);
  return `<span class="chip" style="background:${t.bg};color:${t.fg};border-color:${t.bd}">${esc(text)}</span>`;
};
const tag = (text, tone) => {
  const t = toneOf(tone);
  return `<span class="tag" style="background:${t.bg};color:${t.fg};border-color:${t.bd}">${esc(text)}</span>`;
};
const bigchip = (text, tone) => {
  const t = toneOf(tone);
  return `<span class="bigchip" style="background:${t.bg};color:${t.fg};border-color:${t.bd}">${esc(text)}</span>`;
};

const emptyCard = (title, desc, link, plain, to) =>
  `<div class="empty${plain ? ' plain' : ''}">
     <span class="empty-t">${esc(title)}</span>
     <span class="empty-d">${esc(desc)}</span>
     ${link ? `<a class="link" href="#"${to ? ` data-act="edit" data-to="${to}"` : ''}>${esc(link)}</a>` : ''}
   </div>`;

const editLink = (to, text) =>
  `<a class="link edit" href="#" data-act="edit" data-to="${to}">${esc(text)}</a>`;

/** 조사 — 앞말의 받침에 따라 은/는, 이/가, 을/를 을 고릅니다. */
const JONG = {'0':1,'1':1,'3':1,'6':1,'7':1,'8':1,'2':0,'4':0,'5':0,'9':0,
              'l':1,'m':1,'n':1,'r':1,'L':1,'M':1,'N':1,'R':1};
function josa(word, withJong, without){
  const c = String(word || '').trim().slice(-1);
  if(!c) return String(word || '');
  const code = c.charCodeAt(0);
  let has;
  if(code >= 0xAC00 && code <= 0xD7A3) has = (code - 0xAC00) % 28 !== 0;
  else if(c in JONG)                   has = !!JONG[c];
  else                                 has = false;
  return word + (has ? withJong : without);
}
const eun = w => josa(w, '은', '는');
const ga  = w => josa(w, '이', '가');

/* =========================================================================
   [C] 정규화 — 빠진 값을 채우고, 기하값을 계산합니다.
       LLM 은 '뜻'만 채우고, 좌표는 여기서 만듭니다.
   ========================================================================= */

/** app.js 의 levelOf() 와 같은 구간 규칙 */
function deriveLevel(n){
  const hasStd = n.rda != null || n.ul != null;
  if(!hasStd) return 'unknown';
  if(!(n.total > 0)) return 'none';
  if(n.ul != null && n.ulAmount > n.ul)        return 'over';
  if(n.ul != null && n.ulAmount >= n.ul * 0.7) return 'near';
  if(n.rda != null && n.total >= n.rda)        return 'met';
  return 'low';
}

/** app.js 의 막대 기준 길이 계산과 같은 식 — 눈금 뒤에 늘 여유를 둡니다. */
function deriveBar(n){
  const scale = Math.max(...[
    (n.total || 0) * 1.15, (n.ulAmount || 0) * 1.15,
    n.rda != null ? n.rda * 1.6  : 0,
    n.ul  != null ? n.ul  * 1.25 : 0,
  ].filter(v => v > 0), 1) || 1;

  return {
    supp   : Math.min(n.supp / scale, 1) * 100,
    meal   : Math.max(0, Math.min(n.meal / scale, 1 - n.supp / scale)) * 100,
    rdaMark: (n.rda != null && n.rda <= scale) ? n.rda / scale * 100 : null,
    ulMark : (n.ul  != null && n.ul  <= scale) ? n.ul  / scale * 100 : null,
  };
}

function deriveGauge(n){
  return {
    rda: n.rda ? n.total / n.rda : (n.ul ? n.total / n.ul : null),
    ul : n.ul  ? n.ulAmount / n.ul : (n.rda ? n.total / n.rda : null),
  };
}

function deriveBasis(n){
  if(!n.hasStd) return '표준 기준 미등록';
  if(n.rda != null && n.ul != null)
    return `권장 ${fmt(n.rda)} · 상한 ${fmt(n.ul)}${n.unit}${n.ulSuppOnly ? ' (영양제 기준)' : ''}`;
  if(n.ul  != null) return `상한 ${fmt(n.ul)}${n.unit}`;
  if(n.rda != null) return `권장 ${fmt(n.rda)}${n.unit} 이상`;
  return '기준 없음';
}

function deriveCaption(n){
  /* 제품 이름이 없는데 영양제분만 있는 경우 — 데이터가 덜 채워진 상태입니다.
     '식사 추정 0mg' 이라고 적으면 거짓말이 되므로 있는 그대로 씁니다. */
  if(!n.sources.length && n.supp > 0)
    return `영양제 ${fmt(n.supp)}${n.unit}` +
           (n.meal ? ` + 식사 ${fmt(n.meal)}${n.unit}` : '') + ' · 제품명 미입력';
  if(!n.sources.length) return `식사 평균 추정 ${fmt(n.meal)}${n.unit} · 등록한 제품 없음`;
  return n.sources.join(' · ') +
    (n.supp > 0 ? ` · 영양제 ${fmt(n.supp)}${n.unit}` : '') +
    (n.meal    ? ` + 식사 ${fmt(n.meal)}${n.unit}`   : '');
}

/** 코멘트가 비어 왔을 때의 대체 문장 — 카드 아래가 텅 비지 않게 */
function deriveNote(n){
  return {
    over : {title:'상한 초과.',
            body:`${n.ulSuppOnly ? '영양제로만 ' : ''}${fmt(n.ulAmount)}${n.unit}, 상한 ${fmt(n.ul)}${n.unit}을 넘었습니다. 제품 수를 줄이거나 함량이 낮은 제품으로 바꿔 보세요.`},
    near : {title:'상한 근접.', body:'여기에 같은 성분이 든 제품을 더하면 초과할 수 있습니다.'},
    met  : {title:'충분합니다.', body:'현재 구성을 유지해도 괜찮습니다.'},
    low  : n.sources.length
             ? {title:'권장량에 못 미칩니다.', body:'식사에서 보충하거나 제품의 함량을 확인해 보세요.'}
             : {title:'식사만으로는 모자랍니다.',
                body:`권장량 ${fmt(n.rda)}${n.unit}까지 ${fmt(Math.max(0, (n.rda || 0) - n.total))}${n.unit}이 부족합니다.`},
    none : {title:'섭취량이 없습니다.', body:'등록한 제품에 이 성분이 들어 있지 않습니다.'},
    unknown: {title:'기준값이 없습니다.',
              body: n.unmapped.length
                ? `${n.unmapped.join(', ')} — 이 단위는 환산 규칙이 없어 합산하지 않았습니다.`
                : '기준표에 없는 성분이라 합산량만 표시합니다.'},
  }[n.level] || {title:'', body:''};
}

function normalizeNutrient(raw){
  const r = O(raw);
  const n = {
    key : S(r.key, S(r.name, 'nut')),
    name: S(r.name, '이름 없는 성분'),
    unit: S(r.unit, ''),
    supp: NUM(r.supp, 0),
    meal: NUM(r.meal, 0),
    rda : N(r.rda),
    ul  : N(r.ul),
    ulSuppOnly: B(r.ulSuppOnly),
    sources : A(r.sources).map(x => S(x)).filter(Boolean),
    unmapped: A(r.unmapped).map(x => S(x)).filter(Boolean),
  };
  n.total    = Number.isFinite(Number(r.total)) ? Number(r.total) : n.supp + n.meal;
  n.hasStd   = typeof r.hasStd === 'boolean' ? r.hasStd : (n.rda != null || n.ul != null);
  n.ulAmount = Number.isFinite(Number(r.ulAmount)) ? Number(r.ulAmount)
             : (n.ulSuppOnly ? n.supp : n.total);
  n.level    = LEVEL[r.level] ? r.level : deriveLevel(n);
  n.basis    = S(r.basis, deriveBasis(n));
  n.caption  = S(r.caption, deriveCaption(n));

  const note = O(r.note);
  n.note = (S(note.title) || S(note.body))
    ? {title:S(note.title), body:S(note.body)}
    : deriveNote(n);

  const bar = O(r.bar);
  n.bar = Number.isFinite(Number(bar.supp))
    ? {supp:NUM(bar.supp), meal:NUM(bar.meal), rdaMark:N(bar.rdaMark), ulMark:N(bar.ulMark)}
    : deriveBar(n);

  const g = O(r.gauge);
  n.gauge = (g.rda !== undefined || g.ul !== undefined)
    ? {rda:N(g.rda), ul:N(g.ul)}
    : deriveGauge(n);

  return n;
}

function normalizeExamRow(raw){
  const r = O(raw);
  const j = O(r.judge);
  return {
    key  : S(r.key),
    name : S(r.name, '항목'),
    ref  : S(r.ref, '—'),
    value: S(r.value, '—'),
    judge: {
      code  : ['A', 'B', 'D'].includes(j.code) ? j.code : '',
      text  : S(j.text, '미입력'),
      tone  : TONE[j.tone] ? j.tone : 'gray',
      advice: S(j.advice),
    },
  };
}

function normalizeExam(raw){
  const e = O(raw);
  const groups = A(e.groups).map(g => ({
    group: S(O(g).group, '기타'),
    rows : A(O(g).rows).map(normalizeExamRow),
  }));

  /* rows 를 안 줬으면 groups 를 펼쳐 씁니다(그 반대도 마찬가지). */
  let rows = A(e.rows).map(normalizeExamRow);
  if(!rows.length) rows = groups.flatMap(g => g.rows);
  if(!groups.length && rows.length) groups.push({group:'검사 항목', rows});

  const counts = O(e.counts);
  const c = {A:NUM(counts.A, 0), B:NUM(counts.B, 0), D:NUM(counts.D, 0)};
  if(!c.A && !c.B && !c.D) rows.forEach(r => { if(r.judge.code) c[r.judge.code]++; });

  const filled = Number.isFinite(Number(e.filled))
    ? Number(e.filled) : (c.A + c.B + c.D);

  const ov = O(e.overall);
  const overall = {
    label: S(ov.label, filled ? '판정 없음' : '미입력'),
    tone : TONE[ov.tone] ? ov.tone : 'gray',
    desc : S(ov.desc, filled ? '' : '검진 결과를 입력하면 종합 판정을 계산합니다.'),
  };

  let abnormal = A(e.abnormal).map(normalizeExamRow);
  if(!abnormal.length)
    abnormal = rows.filter(r => r.judge.code === 'D' || r.judge.code === 'B');

  return {groups, rows, counts:c, filled, overall, abnormal};
}

function normalizeInput(raw){
  const s = O(raw);
  return {
    name : S(s.name),
    age  : S(s.age),
    sex  : S(s.sex),
    date : S(s.date),
    countMeal: B(s.countMeal),
    chronic  : A(s.chronic).map(x => S(x)).filter(Boolean),
    products : A(s.products).map(p => ({
      name : S(O(p).name, '이름 없는 제품'),
      items: A(O(p).items).map(i => ({
        name  : S(O(i).name, '성분'),
        amount: NUM(O(i).amount, 0),
        unit  : S(O(i).unit, ''),
      })),
    })),
    meds: A(s.meds).map(m => ({name:S(O(m).name, '이름 없는 약'), desc:S(O(m).desc)})),
    exam: O(s.exam),
  };
}

function normalizeRecommend(raw){
  if(raw === null || raw === undefined) return null;   /* 없으면 섹션을 통째로 뺍니다 */
  const r = O(raw);
  const items = A(r.items).map(it => ({
    name   : S(O(it).name, '성분'),
    amount : S(O(it).amount),
    reason : S(O(it).reason),
    caution: S(O(it).caution),
    tone   : TONE[O(it).tone] ? O(it).tone : 'blue',
  }));
  return {
    title   : S(r.title, items.length ? '이런 성분을 더 챙겨 보세요' : '지금은 더 챙길 성분이 없습니다'),
    desc    : S(r.desc, items.length ? '' : '지금은 더 챙길 성분이 없습니다.'),
    advice  : S(r.advice),
    items,
    more    : NUM(r.more, 0),
    moreText: S(r.moreText),
    note    : S(r.note),
  };
}

/** 배지가 비어 왔을 때 입력에서 만들어 냅니다 — 헤더가 허전해 보이지 않게 */
function deriveBadges(m){
  const b = [];
  if(m.exam.filled)             b.push({text:m.exam.overall.label, tone:m.exam.overall.tone});
  if(m.input.meds.length)       b.push({text:`복약 ${m.input.meds.length}건`, tone:'orange'});
  if(m.input.products.length)   b.push({text:`영양제 ${m.input.products.length}종`, tone:'green'});
  else if(m.hasSupp)            b.push({text:'식사 기준', tone:'gray'});
  if(m.worst === 'over')        b.push({text:'성분 상한 초과', tone:'red'});
  if(m.recommend && m.recommend.items.length)
    b.push({text:`보충 권장 ${m.recommend.items.length}`, tone:'blue'});
  if(!b.length)                 b.push({text:'입력 대기', tone:'gray'});
  return b;
}

/** 소견이 비어 왔을 때의 대체 문장 */
function deriveSummary(m){
  const pick = lv => m.nutrients.filter(n => lv.includes(n.level));
  const over = pick(['over']), near = pick(['near']),
        low  = pick(['low', 'none']), met = pick(['met']);
  const names = list => {
    const a = list.map(x => x.name);
    return a.length > 3 ? `${a.slice(0, 3).join(', ')} 외 ${a.length - 3}개` : a.join(', ');
  };

  const parts = [];
  if(m.exam.filled) parts.push(`건강검진 종합 판정은 '${m.exam.overall.label}' 입니다.`);
  if(!m.hasSupp){
    parts.push('계산할 성분이 없습니다. 영양제를 넣거나 식사 평균 추정치 계산을 켜 주세요.');
  } else {
    parts.push(m.mealOnly
      ? `식사 평균 추정치를 기준으로 ${m.nutrients.length}개 성분을 살펴봤습니다.`
      : `등록한 ${m.input.products.length}개 제품${m.input.countMeal ? '과 식사 평균 추정치' : ''}에서 ${m.nutrients.length}개 성분을 확인했습니다.`);
    if(over.length) parts.push(`${eun(names(over))} 상한을 넘어 조정이 필요합니다.`);
    if(near.length) parts.push(`${eun(names(near))} 상한에 가까워 추가 섭취에 주의가 필요합니다.`);
    if(low.length)  parts.push(`${eun(names(low))} 권장량에 미치지 못합니다.`);
    if(met.length)  parts.push(`나머지 ${met.length}개 성분은 권장 범위 안에 있습니다.`);
    if(m.issues.length) parts.push(`점검에서 ${m.issues.length}건이 확인됐습니다.`);
  }

  const chips = [];
  if(over.length) chips.push({text:`상한 초과 ${over.length}`, tone:'red'});
  if(near.length) chips.push({text:`상한 근접 ${near.length}`, tone:'orange'});
  if(met.length)  chips.push({text:`적정 ${met.length}`,      tone:'green'});
  if(low.length)  chips.push({text:`부족 ${low.length}`,      tone:'blue'});
  if(!chips.length) chips.push({text:'데이터 없음', tone:'gray'});

  return {text:parts.join(' '), chips};
}

/**
 * 어떤 모양으로 와도 렌더러가 다룰 수 있는 형태로 바꿉니다.
 * 빠진 값은 여기서 전부 메워지므로, 아래 render* 함수들은 존재 검사를 하지
 * 않아도 됩니다.
 */
function normalizeReport(raw){
  const d = O(raw);
  const meta = O(d.meta);

  const m = {
    meta: {
      generatedAt: S(meta.generatedAt, new Date().toISOString()),
      source     : S(meta.source, 'server'),
      engine     : S(meta.engine, ''),
    },
    input    : normalizeInput(d.input),
    exam     : normalizeExam(d.exam),
    nutrients: A(d.nutrients).map(normalizeNutrient),
    issues   : A(d.issues).map(i => ({
      kind: S(O(i).kind, '점검'),
      tone: TONE[O(i).tone] ? O(i).tone : 'gray',
      text: S(O(i).text),
      med : S(O(i).med),
    })),
    recommend: normalizeRecommend(d.recommend),
  };

  m.hasSupp  = typeof d.hasSupp  === 'boolean' ? d.hasSupp  : m.nutrients.length > 0;
  m.mealOnly = typeof d.mealOnly === 'boolean' ? d.mealOnly : m.input.products.length === 0;
  m.cols     = Number.isFinite(Number(d.cols))
    ? Math.min(Math.max(Number(d.cols), 1), LAYOUT.maxCols)
    : Math.min(Math.max(m.nutrients.length, 1), LAYOUT.maxCols);
  m.worst    = LEVEL[d.worst] ? d.worst
    : m.nutrients.reduce((w, n) => levelOf(n.level).rank > levelOf(w).rank ? n.level : w, 'met');

  const badges = A(d.badges)
    .map(b => ({text:S(O(b).text), tone:TONE[O(b).tone] ? O(b).tone : 'gray'}))
    .filter(b => b.text);
  m.badges = badges.length ? badges : deriveBadges(m);

  const sum = O(d.summary);
  const chips = A(sum.chips)
    .map(c => ({text:S(O(c).text), tone:TONE[O(c).tone] ? O(c).tone : 'gray'}))
    .filter(c => c.text);
  const fallback = (!S(sum.text) || !chips.length) ? deriveSummary(m) : null;
  m.summary = {
    text : S(sum.text, fallback ? fallback.text : ''),
    chips: chips.length ? chips : (fallback ? fallback.chips : [{text:'데이터 없음', tone:'gray'}]),
  };

  return m;
}

/* =========================================================================
   [D] 렌더 — app.js 의 마크업을 그대로 옮겼습니다.
   ========================================================================= */

/* ---- [블록 1] 프로필 헤더 ------------------------------------------------ */
function renderHeader(m){
  const s = m.input;
  const ex = m.exam;
  const tags = m.badges.map(b => chip(b.text, b.tone));

  const examCol = !ex.filled
    ? emptyCard('검진 결과가 없습니다',
                '건강검진 결과를 입력하면 별표 4 기준으로 항목별 판정을 계산합니다.')
    : `<div class="rows">
         <div class="row">
           <div class="row-l"><span class="row-t">${esc(ex.overall.label)}</span>
             <span class="row-d">${esc(ex.overall.desc)}</span></div>
         </div>
         <div class="row">
           <div class="row-l"><span class="row-t">항목별 판정</span>
             <span class="row-d">${ex.filled}개 항목 입력됨</span></div>
           <div class="tags">
             ${ex.counts.D ? tag(`질환의심 ${ex.counts.D}`, 'red') : ''}
             ${ex.counts.B ? tag(`경계 ${ex.counts.B}`, 'orange') : ''}
             ${ex.counts.A ? tag(`정상A ${ex.counts.A}`, 'green') : ''}
           </div>
         </div>
         ${ex.rows.filter(r => r.judge.advice).map(r => `<div class="row top"
             style="border-color:${TONE.red.bd};background:${TONE.red.bg}">
             <div class="row-l"><span class="row-t" style="color:${TONE.red.ink}">${esc(r.name)} · ${esc(r.judge.text)}</span>
               <span class="row-d" style="color:${TONE.red.ink}">${esc(r.judge.advice)}</span></div>
           </div>`).join('')}
         ${ex.abnormal.slice(0, 3).map(r => `<div class="row">
            <div class="row-l"><span class="row-t">${esc(r.name)}</span>
              <span class="row-d">${esc(r.value)} · 기준 ${esc(r.ref)}</span></div>
            ${tag(r.judge.text, r.judge.tone)}
          </div>`).join('')}
         ${ex.abnormal.length > 3
            ? `<div class="row"><div class="row-l"><span class="row-d">이 밖에 ${ex.abnormal.length - 3}개 항목이 기준을 벗어났습니다.</span></div></div>`
            : ''}
       </div>`;

  const filledGroups = ex.groups
    .map(g => ({...g, rows: g.rows.filter(r => r.judge.code)}))
    .filter(g => g.rows.length);
  const blank = Math.max(0, ex.rows.length - ex.filled);
  const examTable = !ex.filled ? '' : `<details class="exam" data-k="ex">
      <summary class="ix-sum" style="border-bottom:none;padding:12px 0 0">
        <span class="h3">검진 결과 전체 · ${ex.filled}개 항목</span>
        <span class="toggle"><span class="on">접기</span><span class="off">펼치기</span></span>
      </summary>
      <div class="tbl" style="margin-top:12px">
        <div class="tr th"><span>검사 항목</span><span>내 수치</span><span>판정 기준</span><span class="right">판정</span></div>
        ${filledGroups.map(g => `<div class="tr gp"><span>${esc(g.group)}</span><span></span><span></span><span></span></div>` +
          g.rows.map(r => `<div class="tr">
            <span>${esc(r.name)}</span>
            <span class="b">${esc(r.value)}</span>
            <span class="rf">${esc(r.ref)}</span>
            <span class="right">${tag(r.judge.text, r.judge.tone)}</span>
          </div>`).join('')).join('')}
      </div>
      ${blank ? `<div class="note-s" style="padding-top:8px">미입력 ${blank}개 항목은 표시하지 않았습니다.</div>` : ''}
    </details>`;

  const medsCol = !s.meds.length
    ? emptyCard('등록된 약이 없습니다',
                '복용 중인 약을 입력하면 영양제와의 상호작용을 함께 점검합니다.')
    : `<div class="rows">${s.meds.map(md => {
         const hits = m.issues.filter(i => i.med && i.med === md.name);
         return `<div class="row">
           <div class="row-l"><span class="row-t">${esc(md.name)}</span>
             <span class="row-d">${esc(md.desc || '설명 없음')}</span></div>
           ${hits.length ? tag(`주의 ${hits.length}건`, hits.some(h => h.tone === 'red') ? 'red' : 'orange')
                         : tag('점검 완료', 'gray')}
         </div>`;
       }).join('')}</div>`;

  const suppCol = !s.products.length
    ? emptyCard('등록된 영양제가 없습니다',
                '제품명과 성분을 입력하면 성분별 합산량을 계산해 드립니다.')
    : `<div class="rows">${s.products.map(p => {
         const nm   = p.name || '이름 없는 제품';
         const over = m.nutrients.some(n => n.level === 'over' && n.sources.includes(nm));
         const desc = p.items.length
           ? p.items.map(i => `${i.name} ${fmt(i.amount || 0)}${i.unit}`).join(' · ')
           : '성분 미입력';
         return `<div class="row top">
           <div class="row-l"><span class="row-t">${esc(nm)}</span><span class="row-d">${esc(desc)}</span></div>
           ${over ? tag('상한 초과', 'red') : p.items.length ? tag(`성분 ${p.items.length}`, 'gray') : tag('미입력', 'gray')}
         </div>`;
       }).join('')}</div>`;

  return `<details class="card hd" data-k="hd" open>
    <summary class="hd-sum">
      <div class="hd-left">
        <div class="avatar">${esc((s.name || '?').trim().charAt(0) || '?')}</div>
        <div class="hd-info">
          <div class="hd-name">
            <span class="nm">${esc(s.name || '이름 미입력')}</span>
            <span class="mt">${esc(s.age || '—')}세 · ${esc(s.sex || '—')} · ${esc(s.date || '—')}</span>
          </div>
          <div class="tags">${tags.join('')}</div>
        </div>
      </div>
      <span class="toggle"><span class="on">접기</span><span class="off">펼치기</span></span>
    </summary>
    <div class="hd-body">
      <div class="hd-grid">
        <div class="hd-col">
          <div class="hd-col-t">검진 결과${editLink('exam', ex.filled ? '수정' : '입력')}</div>${examCol}</div>
        <div class="hd-col">
          <div class="hd-col-t">복약 정보${editLink('meds', s.meds.length ? '수정' : '입력')}</div>${medsCol}</div>
        <div class="hd-col">
          <div class="hd-col-t">등록한 영양제${editLink('products', '수정')}</div>${suppCol}</div>
      </div>
      ${examTable}
      <div class="hd-links"><a class="link" href="#">판정기준 출처 보기</a></div>
    </div>
  </details>`;
}

/* ---- [블록 2] 성분 카드 하나 --------------------------------------------- */
function renderCard(n){
  const lv = levelOf(n.level), t = toneOf(lv.tone);

  const pct = n.gauge.rda;
  let label = '—', arc = 0;
  const arcColor = t.fg;
  if(pct != null && n.level !== 'unknown'){
    label = Math.round(pct * 100) + '%';
    arc   = LAYOUT.gaugeArc * Math.min(pct, 1);
  }
  const track = `<path d="M8,60 A52,52 0 0 1 112,60" fill="none" stroke="#EEF0F3" stroke-width="12" stroke-linecap="round"/>`;
  const fill  = arc > 0
    ? `<path d="M8,60 A52,52 0 0 1 112,60" fill="none" stroke="${arcColor}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${arc.toFixed(1)} 200"/>`
    : '';

  const over = n.level === 'over';
  const bar = `<div class="bar">
         <div style="width:${n.bar.supp.toFixed(2)}%;background:${over ? TONE.crit.fg : '#1E3A8A'}"></div>
         <div style="width:${n.bar.meal.toFixed(2)}%;background:${over ? '#F3B4B4' : '#D8DBE0'}"></div>
       </div>`;

  const rm = n.bar.rdaMark, um = (n.hasStd && n.ul != null) ? n.bar.ulMark : null;
  const mark = (pos, kind, text) => pos == null ? '' :
    `<i class="mk mk-${kind}" style="left:${pos.toFixed(2)}%"></i>` +
    (text ? `<b class="mkl mkl-${kind}" style="left:${pos.toFixed(2)}%">${text}</b>` : '');

  const merged = rm != null && um != null && Math.abs(um - rm) < 9;
  const marks = merged
    ? mark(rm, 'rda', '') + mark(um, 'ul', '권장·상한')
    : mark(rm, 'rda', '권장') + mark(um, 'ul', '상한');

  const cap  = n.caption || n.sources.join(' · ');
  const note = n.note || {title:'', body:''};

  const srcTag = n.sources.length
    ? tag(`${n.sources.length}개 제품`, lv.tone)
    : tag(n.supp > 0 ? '제품명 미입력' : '식사 추정', 'gray');

  return `<div class="nc">
  <div class="nc-head"><span class="nc-name">${esc(n.name)}</span>${srcTag}</div>
  <div><span class="nc-cap" style="background:${TONE.gray.bg};color:${TONE.gray.fg}">${esc(cap)}</span></div>
  <svg class="gauge" viewBox="0 0 120 70">${track}${fill}<text x="60" y="54" text-anchor="middle" style="font:800 ${gaugeSize(label)}px var(--ff);fill:${arcColor}">${esc(label)}</text></svg>
  <div class="nc-level" style="color:${arcColor}">${esc(lv.text)}</div>
  <div class="barwrap">${bar}${marks}</div>
  <div class="nc-vals"><span class="b">${n.supp > 0 || n.meal > 0 ? fmt(n.total) + n.unit : '—'}</span><span>${esc(n.basis || '')}</span></div>
  <div class="nc-note" style="background:${t.bg};border-color:${t.bd};color:${t.ink}"><b>${esc(note.title)}</b> ${esc(note.body)}</div>
</div>`;
}

/* ---- [블록 2] 섭취량 섹션 ------------------------------------------------ */
function renderIntake(m){
  const title = !m.hasSupp ? '아직 계산할 섭취량이 없습니다'
              : m.mealOnly ? '식사 평균 추정치 기준 섭취량'
              : '표준 기준 대비 내 섭취량';
  const desc  = !m.hasSupp
        ? '영양제를 등록하거나 식사 평균 추정치 계산을 켜면 이 자리에 성분별 카드가 나타납니다.'
        : m.mealOnly
        ? '복용 중인 영양제를 넣지 않으셔서, 일반적인 식사에서 섭취하는 평균 추정치만으로 권장량과 비교했습니다. 실제 식사 내용에 따라 다를 수 있습니다.'
        : `등록한 ${m.input.products.length}개 제품의 성분을 합산하고, ${m.input.countMeal ? '식사 평균 추정치를 더해 ' : ''}권장·상한과 비교했습니다.`;

  const head = `<div class="in-head">
      <div class="in-head-l">
        <span class="h2">${esc(title)}</span>
        <span class="sub">${esc(desc)}</span>
      </div>
      <div class="legend">
        <span><i class="sw" style="background:#1E3A8A"></i>영양제</span>
        <span><i class="sw" style="background:#D8DBE0"></i>식사 평균 추정</span>
        <span><i class="ln" style="background:${TONE.green.fg}"></i>권장</span>
        <span><i class="ln" style="background:${TONE.red.fg}"></i>상한</span>
      </div>
    </div>`;

  if(!m.hasSupp){
    return `<section class="intake">${head}
      <div class="pane always">${emptyCard('계산할 섭취량이 없습니다',
        '영양제를 입력하거나 식사 평균 추정치 계산을 켜면 이 자리에 표시됩니다.',
        '입력 수정하기', true, 'products')}</div>
    </section>`;
  }

  return `<section class="intake">${head}
  <div class="pane always">
    <div class="grid" data-cols="${m.cols}">${m.nutrients.map(renderCard).join('')}</div>
  </div>
</section>`;
}

/* ---- [블록 2-B] 추천 영양제 ---------------------------------------------- */
function renderRecommend(m){
  const r = m.recommend;
  if(!r) return '';

  const body = r.items && r.items.length
    ? `<div class="rc-grid">${r.items.map(it => {
        const t = toneOf(it.tone);
        return `<div class="rc-item" style="border-left-color:${t.fg}">
          <div class="rc-top">
            <span class="rc-name">${esc(it.name)}</span>
            ${it.amount ? `<span class="rc-amt" style="color:${t.fg}">${esc(it.amount)}</span>` : ''}
          </div>
          <p class="rc-why">${esc(it.reason || '')}</p>
          ${it.caution ? `<div class="rc-caution">${esc(it.caution)}</div>` : ''}
        </div>`;
      }).join('')}</div>`
    : `<div class="rc-none">${esc(r.desc || '지금은 더 챙길 성분이 없습니다.')}</div>`;

  return `<section class="card rc">
    <div class="rc-head">
      <span class="h2">${esc(r.title || '추천')}</span>
      ${r.items && r.items.length ? `<span class="sub">${esc(r.desc || '')}</span>` : ''}
    </div>
    ${r.advice ? `<div class="rc-advice">${esc(r.advice)}</div>` : ''}
    ${body}
    ${r.moreText ? `<span class="rc-note" style="color:#6B7280">${esc(r.moreText)}</span>` : ''}
    ${r.note ? `<span class="rc-note">${esc(r.note)}</span>` : ''}
  </section>`;
}

/* ---- [블록 3] 상호작용 · 중복 점검 --------------------------------------- */
function renderIssues(m){
  const body = m.issues.length
    ? m.issues.map(i => {
        const t = toneOf(i.tone);
        return `<div class="ix-row">
        <span class="ix-kind" style="background:${t.bg};color:${t.fg}">${esc(i.kind)}</span>
        <span class="ix-text">${esc(i.text)}</span>
        <a class="link" href="#">자세히</a>
      </div>`;
      }).join('')
    : emptyCard('점검된 항목이 없습니다',
                '등록한 제품과 약 사이에서 겹치거나 부딪히는 성분이 발견되지 않았습니다.', null, true);

  return `<details class="card" data-k="ix" open>
    <summary class="ix-sum">
      <span class="h3">상호작용 · 성분 중복 점검${m.issues.length ? ` · ${m.issues.length}건` : ''}</span>
      <span class="toggle"><span class="on">접기</span><span class="off">펼치기</span></span>
    </summary>
    <div>${body}</div>
  </details>`;
}

/* ---- [블록 4] 종합 소견 -------------------------------------------------- */
function renderSummary(m){
  const chips = m.summary.chips.map(c => bigchip(c.text, c.tone));
  return `<section class="card sm">
    <span class="h3">종합 소견</span>
    <p class="sm-text">${esc(m.summary.text)}</p>
    <div class="sm-keys"><span class="sm-keys-l">핵심</span><div class="sm-keys-r">${chips.join('')}</div></div>
  </section>`;
}

/* ---- [블록 5] 푸터 ------------------------------------------------------- */
const renderFooter = m => `<footer class="ft">
  ${m.meta.source === 'mock'
    ? '<p>이 화면의 기준값과 상호작용 규칙은 검증되지 않은 예시입니다. 실제 판단에 사용하지 마세요.</p>'
    : ''}
  <p>이 리포트는 입력하신 내용을 바탕으로 한 참고 자료이며, 진단이나 처방이 아닙니다.
     건강 상태나 복약에 대한 판단은 반드시 의사·약사와 상의하시기 바랍니다.</p>
</footer>`;

const mockBanner = m => m.meta.source !== 'mock' ? '' :
  `<div class="banner warn">
     <span><b>예시 기준값으로 계산 중입니다.</b>
       성분 기준값과 상호작용 규칙이 아직 검증되지 않았습니다. 실제 판단에 사용하지 마세요.</span>
   </div>`;

const sampleBanner = () =>
  `<div class="banner info">
     <span><b>샘플 리포트입니다.</b> 예시로 만든 가상의 입력으로 만든 화면입니다.</span>
     <button type="button" class="btn-line" data-act="fresh">내 정보로 시작하기</button>
   </div>`;

/* ---- 전체 조립 ----------------------------------------------------------- */
const renderReport = (m, {sample = false} = {}) =>
  `<div class="page">
    ${sample ? sampleBanner() : mockBanner(m)}
    <div class="rp-top">
      <div><span class="h2">영양제 섭취 리포트</span>
        <span class="sub" style="display:block">${esc(m.input.date || '')} 기준 · 입력하신 내용으로 분석했습니다.</span></div>
      <div class="rp-acts">
        <button type="button" class="btn-line" data-act="print">인쇄 · PDF 저장</button>
        <button type="button" class="rp-back" data-act="edit">입력 수정</button>
      </div>
    </div>
    ${renderHeader(m)}${renderRecommend(m)}${renderIntake(m)}${renderIssues(m)}${renderSummary(m)}${renderFooter(m)}</div>`;

/* 상단바 — app.js 의 paintTopbar() 가 그리는 것과 같은 마크업(로그아웃 상태) */
const renderTopbar = () => `<div class="tb-inner">
    <button type="button" class="tb-logo-btn" data-act="home" title="메인 화면으로 이동">MyHerb</button>
    <div class="tb-guest">
      <button type="button" class="btn-line sm" data-act="login">로그인</button>
      <button type="button" class="btn-solid sm" data-act="signup">회원가입</button>
    </div>
  </div>`;

/* =========================================================================
   [E] 문서 조립 — report.html 의 뼈대를 그대로 씁니다.
   ========================================================================= */
const FONT_CDN = 'https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css';

/** styles.css 를 찾습니다 — src → static 순. 없으면 null. */
function findStyles(){
  const cands = [
    path.join(__dirname, '..', 'src', 'styles.css'),
    path.join(__dirname, '..', 'static', 'styles.css'),
  ];
  return cands.find(p => fs.existsSync(p)) || null;
}

/** 정적 파일이라 app.js 가 없으므로, 인쇄 버튼만 살려 둡니다. */
const ENHANCE_SCRIPT = `<script>
document.addEventListener('click', function(e){
  var t = e.target;
  var b = (t && t.closest) ? t.closest('[data-act="print"]') : null;
  if(b){ e.preventDefault(); window.print(); }
});
</script>`;

/**
 * Report 데이터를 완성된 HTML 문서 문자열로 만듭니다.
 *
 * @param {object|string} data  Report 객체(또는 JSON 문자열)
 * @param {object} [opts]
 *   outFile   {string}  주면 그 경로에 저장합니다. 예) 'out/output.html'
 *   title     {string}  <title>. 기본 'MyHerb'
 *   cssHref   {string}  styles.css 를 <link> 로 걸 때의 경로.
 *                       주지 않으면 styles.css 를 찾아 <style> 로 심습니다.
 *   inlineCss {boolean} 기본 true(파일 하나로 완결). false + cssHref 조합 권장.
 *   topbar    {boolean} 상단바를 넣을지. 기본 true.
 *   sample    {boolean} '샘플 리포트' 파란 띠. 기본 false.
 *   fragment  {boolean} true 면 <html> 없이 리포트 조각만 돌려줍니다.
 *   enhance   {boolean} 인쇄 버튼용 작은 스크립트. 기본 true.
 * @returns {string} HTML
 */
function renderHtmlFromData(data, opts = {}){
  const {
    outFile, title = 'MyHerb', cssHref, inlineCss = true,
    topbar = true, sample = false, fragment = false, enhance = true,
  } = opts;

  const parsed = (typeof data === 'string') ? JSON.parse(data) : data;
  const m = normalizeReport(parsed);
  const body = renderReport(m, {sample});

  let html;
  if(fragment){
    html = body;
  } else {
    /* 스타일 — 인라인(기본)이면 파일 하나로 어디서나 열립니다. */
    let styleTag = '';
    if(cssHref && !inlineCss){
      styleTag = `<link rel="stylesheet" href="${esc(cssHref)}">`;
    } else {
      const p = findStyles();
      if(p) styleTag = `<style>\n${fs.readFileSync(p, 'utf8')}\n</style>`;
      else  styleTag = `<link rel="stylesheet" href="${esc(cssHref || 'styles.css')}">`;
    }

    html = `<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)}</title>
<link rel="stylesheet" href="${FONT_CDN}">
${styleTag}
</head>
<body>
<!-- 이 파일은 pipeline/renderer.js 가 만들어 낸 정적 리포트입니다.
     직접 고치지 말고 데이터(.json)를 고친 뒤 다시 렌더하세요. -->
<header id="topbar"${topbar ? '' : ' hidden'}>${topbar ? renderTopbar() : ''}</header>
<div id="app">${body}</div>
<div id="authModal"></div>
${enhance ? ENHANCE_SCRIPT : ''}
</body>
</html>
`;
  }

  if(outFile){
    const out = path.resolve(outFile);
    fs.mkdirSync(path.dirname(out), {recursive: true});
    fs.writeFileSync(out, html, 'utf8');
  }
  return html;
}

module.exports = {
  renderHtmlFromData,
  normalizeReport,
  renderReport, renderHeader, renderCard, renderIntake,
  renderRecommend, renderIssues, renderSummary, renderFooter,
  TONE, LEVEL, LAYOUT, esc, fmt,
};
