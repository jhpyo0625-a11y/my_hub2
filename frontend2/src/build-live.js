#!/usr/bin/env node
'use strict';
/* =========================================================================
   build-live.js — 개발용 파일로 실서버용 파일을 만듭니다.
   -------------------------------------------------------------------------
     $ node build-live.js

       app.js       →  live-app.js     (목업 블록을 빼고 서버를 보게 함)
       report.html  →  Live.html       (live-app.js 를 불러오게 함)

   styles.css 는 손대지 않습니다 — 두 화면이 같은 파일을 함께 씁니다.

   app.js 나 report.html 을 고친 뒤 이 한 줄만 실행하면 실서버용 파일이 다시
   만들어집니다. Live.html 과 live-app.js 는 자동 생성물이므로 직접 고치지
   마세요. 다음 실행 때 덮어써집니다.
   ========================================================================= */

const fs = require('fs');
const path = require('path');

const DIR = __dirname;                                 /* 원본이 있는 곳 (src/) */
const OUT = path.join(__dirname, '..', 'static');      /* 서버가 내려줄 곳 (static/) */
fs.mkdirSync(OUT, {recursive: true});

const read  = f => fs.readFileSync(path.join(DIR, f), 'utf8');
const write = (f, s) => fs.writeFileSync(path.join(OUT, f), s);

let js = read('app.js');

/** 반드시 한 번만 바뀌어야 하는 치환. 안 바뀌면 곧바로 알려 줍니다
    (조용히 넘어가면 겉보기엔 멀쩡한데 실제로는 목업으로 도는 파일이 나옵니다). */
function replaceOnce(from, to, label){
  const i = js.indexOf(from);
  if(i < 0) throw new Error(`[build-live] '${label}' 를 찾지 못했습니다. app.js 가 바뀌었나요?`);
  if(js.indexOf(from, i + from.length) >= 0)
    throw new Error(`[build-live] '${label}' 가 여러 번 나옵니다. 더 구체적으로 찾아야 합니다.`);
  js = js.slice(0, i) + to + js.slice(i + from.length);
}


/* ---- 1) 목업 블록 삭제 --------------------------------------------------- */
const B = '/* ###########################################################################\n   ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼  [E] 목업 블록 — 시작';
const E = '▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲  [E] 목업 블록 — 끝  ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲\n   ########################################################################### */';
const b = js.indexOf(B), e = js.indexOf(E);
if(b < 0 || e < 0) throw new Error('[build-live] 목업 블록 경계를 찾지 못했습니다.');
js = js.slice(0, b) +
`/* [E] 목업 블록은 이 파일에 없습니다 — 판정은 전부 서버가 합니다.
   (목업으로 확인하고 싶으면 report.html 을 여세요.) */` +
js.slice(e + E.length);


/* ---- 2) 목업 대신 서버를 보게 만들기 -------------------------------------- */
replaceOnce(
  "const USE_MOCK = true;      /* ← 백엔드가 준비되면 false 로 */\nconst API_BASE = '';        /* ← 예: 'https://api.myherb.co.kr' */",
`const USE_MOCK = false;     /* 이 파일은 실제 서버에 붙습니다 */
/* 같은 주소에서 화면과 서버가 함께 돌면 '' 그대로 두면 됩니다.
   (server.js 가 이 화면을 http://localhost:3000 에서 내려 줍니다)
   다른 주소의 서버에 붙일 때만 예: 'https://api.myherb.co.kr' 처럼 적으세요. */
const API_BASE = '';`,
  'USE_MOCK / API_BASE');

/* MOCK.* 를 부르던 자리는 이 파일에 목업이 없으므로 지웁니다.
   (USE_MOCK 이 false 라 실행되지는 않지만, 없는 이름을 남겨 두면 읽는
    사람이 목업이 어딘가 있는 줄 압니다.) */
js = js.replace(/^\s*if\(USE_MOCK\) return MOCK\.[a-zA-Z]+\([^)]*\);\n/gm, '');


/* ---- 3) '검증되지 않은 기준값' 경고 띠를 서버 응답에 맡기기 ---------------- */
replaceOnce(
  "  /** 지금 목업으로 도는 중인지. 화면 맨 위 경고 띠가 이 값을 봅니다. */\n  get source(){ return USE_MOCK ? 'mock' : 'server'; },",
`  /** 화면 맨 위 경고 띠가 이 값을 봅니다.
      서버가 /api/bootstrap 에서 unverified:true 를 내려보내는 동안은
      (= 판정 기준값이 아직 검증 전이라는 뜻) 목업일 때와 똑같이 경고 띠를
      띄웁니다. 검증된 기준으로 바꾼 뒤 서버에서 false 로 내려 주면
      경고 띠가 사라집니다. */
  get source(){ return APP.unverified ? 'mock' : 'server'; },`,
  'API.source');

replaceOnce('const APP = {hints: []};',
            'const APP = {hints: [], unverified: false};', 'APP');

replaceOnce('      APP.hints = (boot && boot.nutHints) || [];',
`      APP.hints = (boot && boot.nutHints) || [];
      APP.unverified = !!(boot && boot.unverified);`, 'bootstrap 처리');


/* ---- 4) 목업을 전제로 쓰인 안내 문구를 이 파일에 맞게 고치기 --------------- */
replaceOnce(
`   ---------------------------------------------------------------------------
   백엔드 연결할 때 할 일 (요약)
   ---------------------------------------------------------------------------
     1. [D] 의 USE_MOCK 을 false 로 바꿉니다.
     2. [D] 의 API_BASE 에 서버 주소를 적습니다.
     3. [E] 목업 블록 전체를 지웁니다. (시작·끝 표시가 있습니다)
     4. 끝. 화면 코드는 손대지 않습니다.

   주고받는 데이터의 정확한 형태는 함께 드린 '백엔드 연동 규격서'에
   예시 JSON 과 함께 정리해 두었습니다.

   ---------------------------------------------------------------------------
   ※ 주의 — 지금 목업에 들어 있는 값 중
     - 검진 판정기준은 국가 건강검진 실시기준 [별표 4] 를 옮긴 것입니다.
     - 성분 기준값과 상호작용 규칙은 예시입니다. 실제 서비스에 그대로
       쓰면 안 됩니다. USE_MOCK 이 true 인 동안에는 화면 맨 위에
       경고 띠가 자동으로 뜹니다.`,
`   ---------------------------------------------------------------------------
   이 파일은 '서버에 붙은 상태' 입니다
   ---------------------------------------------------------------------------
     · USE_MOCK 은 false 이고, [E] 목업 블록은 들어 있지 않습니다.
     · 판정은 전부 서버(/api/analyze)가 합니다. 이 파일은 계산하지 않습니다.
     · 서버 주소는 [D] 의 API_BASE 하나로 정합니다.

   주고받는 데이터의 정확한 형태는 함께 드린 '백엔드 연동 규격서'에
   예시 JSON 과 함께 정리해 두었습니다.

   ---------------------------------------------------------------------------
   ※ 주의 — 붙어 있는 서버가 아직 예시 기준값으로 계산하는 동안에는
     /api/bootstrap 이 unverified:true 를 내려보내고, 그때는 화면 맨 위에
     '예시 기준값' 경고 띠가 그대로 뜹니다. 검증된 기준으로 바꾼 뒤
     서버에서 false 로 내려 주면 경고 띠가 사라집니다.`,
  '머리말 안내');

replaceOnce(
`   ── 백엔드 연결하는 법 (세 단계) ───────────────────────────────────────
     1. 바로 아래 USE_MOCK 을 false 로 바꿉니다.
     2. API_BASE 에 서버 주소를 적습니다. (같은 도메인이면 '' 그대로 두세요)
     3. [E] 목업 블록을 통째로 지웁니다.
     끝입니다. 이 아래 화면 코드는 한 줄도 건드리지 않습니다.

   ── 서버가 제공해야 하는 것 네 가지 ────────────────────────────────────
     GET  /api/bootstrap   화면 열 때 한 번. 성분 이름 추천 목록 등.
     GET  /api/draft       로그인한 사용자가 저장해 둔 입력값 불러오기
     PUT  /api/draft       입력값 저장 (사용자가 입력하는 동안 자동으로)
     POST /api/analyze     ★ 핵심. 입력을 보내고 AI 판정 결과를 받습니다.`,
`   ── 서버가 제공해야 하는 것 ────────────────────────────────────────────
     GET  /api/bootstrap    화면 열 때 한 번. 성분 이름 추천 목록 등.
     GET  /api/me           지금 로그인되어 있는지
     POST /api/signup       회원가입      POST /api/login   로그인
     POST /api/logout       로그아웃
     GET  /api/draft        저장해 둔 입력값 불러오기
     PUT  /api/draft        입력값 저장 (입력하는 동안 자동으로)
     POST /api/analyze      ★ 핵심. 입력을 보내고 판정 결과를 받습니다.
     GET  /api/reports      지난 리포트 목록
     GET  /api/reports/:id  지난 리포트 하나

   함께 드린 server.js 가 이 아홉 개를 그대로 구현한 예시 서버입니다.`,
  'API 경계 안내');

replaceOnce(
  '/** 목업으로 도는 중이라는 경고. 실서비스(USE_MOCK=false)에서는 나오지 않습니다. */',
`/** 판정 기준값이 아직 검증되지 않았다는 경고.
    서버가 unverified:true 를 내려보내는 동안에만 뜹니다. */`,
  'mockBanner 주석');


/* ---- 5) 파일 머리말 갈아 끼우기 ------------------------------------------- */
replaceOnce(
`/* =========================================================================
   app.js — MyHerb 화면 동작 (목업 포함 · 개발용)
   -------------------------------------------------------------------------
   report.html 이 이 파일을 불러 씁니다.

   ★ 이 파일에는 백엔드가 없는 동안 브라우저 안에서 판정을 흉내 내는
     [E] 목업 블록이 들어 있습니다. 실제 서버에 붙일 때는 이 파일을 지우는
     것이 아니라, 목업 블록만 빠진 live-app.js 를 쓰면 됩니다.
     (node build-live.js 가 이 파일로부터 자동으로 만들어 줍니다)`,
`/* =========================================================================
   live-app.js — MyHerb 화면 동작 (실서버 연결용)
   -------------------------------------------------------------------------
   ※ 이 파일은 build-live.js 가 app.js 로 만들어 낸 것입니다.
     직접 고치지 말고 app.js 를 고친 뒤 'node build-live.js' 를 실행하세요.

   Live.html 이 이 파일을 불러 씁니다.
   app.js 와 같은 코드에서 [E] 목업 블록만 빠져 있습니다. 판정은 하지 않고,
   [D] API 경계를 통해 서버에 물어본 결과를 그리기만 합니다.`,
  '파일 머리말');


/* ---- 6) Live.html — 뼈대에서 부르는 스크립트만 바꿉니다 -------------------- */
let shell = read('report.html');
const swap = (from, to, label) => {
  if(!shell.includes(from)) throw new Error(`[build-live] report.html 에서 '${label}' 를 찾지 못했습니다.`);
  shell = shell.split(from).join(to);
};
swap('<script src="app.js"></script>', '<script src="live-app.js"></script>', 'script 태그');
swap(`<!-- 목업(브라우저 안에서 판정을 흉내 내는 코드)이 들어 있는 개발용입니다.
     실제 서버에 붙인 화면은 Live.html + live-app.js 입니다. -->`,
`<!-- 이 파일은 build-live.js 가 report.html 로 만들어 낸 것입니다.
     직접 고치지 말고 src/report.html 을 고친 뒤 'node build-live.js' 를 실행하세요.
     실행법:  uv run server.py  →  http://localhost:3000 -->`, '안내 주석');
swap('  ※ 세 파일(report.html · styles.css · app.js)은 같은 폴더에 함께 있어야',
     '  ※ 세 파일(Live.html · styles.css · live-app.js)은 같은 폴더에 함께 있어야', '파일 목록 주석');

write('live-app.js', js);
write('Live.html', shell);

/* styles.css 는 고칠 것이 없으므로 그대로 복사만 합니다. 두 화면이 같은
   파일을 쓴다는 원칙은 그대로이고, static/ 안에도 한 벌 있어야 서버가
   내려줄 수 있어서 옮겨 둡니다. */
fs.copyFileSync(path.join(DIR, 'styles.css'), path.join(OUT, 'styles.css'));

const n = s => s.split('\n').length;
console.log('실서버용 파일을 만들었습니다.  →  ' + path.relative(process.cwd(), OUT) + '/');
console.log(`  Live.html    ${String(n(shell)).padStart(5)}줄`);
console.log(`  live-app.js  ${String(n(js)).padStart(5)}줄  (app.js 에서 목업 블록 제외)`);
console.log(`  styles.css   원본에서 복사`);
console.log(`\n  uv run server.py  로 띄운 뒤 http://localhost:3000 을 열어 보세요.`);
