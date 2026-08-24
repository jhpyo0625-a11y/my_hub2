/* =========================================================================
   app.js — MyHerb 화면 동작 (목업 포함 · 개발용)
   -------------------------------------------------------------------------
   report.html 이 이 파일을 불러 씁니다.

   ★ 이 파일에는 백엔드가 없는 동안 브라우저 안에서 판정을 흉내 내는
     [E] 목업 블록이 들어 있습니다. 실제 서버에 붙일 때는 이 파일을 지우는
     것이 아니라, 목업 블록만 빠진 live-app.js 를 쓰면 됩니다.
     (node build-live.js 가 이 파일로부터 자동으로 만들어 줍니다)

   구성 — 아래 순서대로 들어 있습니다.
     [A] 화면 토큰    색·수준 이름표
     [B] 유틸         이스케이프 · 숫자 서식 · 조사 처리
     [C] 입력 폼 정의 검진 항목 · 만성질환 목록
     [D] ★ API 경계 ★ 서버와 만나는 유일한 지점. 여기만 고칩니다.
     [E] ▼ 목업 블록 ▼ 백엔드 대신 계산하는 임시 코드 (실서버에서는 빠집니다)
     [F] 렌더         Report 를 받아 화면을 그립니다
     [G] 화면 전환    불러오는 중 / 입력 / 분석 중 / 리포트 / 실패
     [H] 이벤트·시작
   ========================================================================= */
/* ###########################################################################

   MyHerb — 영양제 섭취 리포트 (프론트엔드)

   ---------------------------------------------------------------------------
   이 파일이 하는 일과 하지 않는 일
   ---------------------------------------------------------------------------
   판정(어떤 성분이 과다한지, 어떤 약과 부딪히는지)은 백엔드의 AI 가 합니다.
   이 파일은 두 가지만 합니다.

     1) 사용자에게서 입력을 받는다        → Input
     2) 백엔드가 돌려준 판정 결과를 그린다 → Report

   그래서 이 파일에는 원래 '계산 코드'가 없어야 합니다.
   지금은 백엔드가 아직 없어서, 임시로 브라우저에서 계산하는 코드가
   [목업 블록] 안에 들어 있습니다. 백엔드가 준비되면 그 블록을 통째로
   지우면 됩니다. 다른 코드는 한 줄도 건드리지 않습니다.

   ---------------------------------------------------------------------------
   파일 순서 — Ctrl+F 로 대괄호 이름을 검색하면 바로 찾아갑니다
   ---------------------------------------------------------------------------
   [A] 화면 토큰      색·수준 라벨. 화면 생김새를 정합니다.          (계속 사용)
   [B] 유틸           이스케이프·숫자 서식·조사 처리.                (계속 사용)
   [C] 입력 폼 정의   검진 항목·만성질환 목록. 입력칸을 만듭니다.    (계속 사용)
   [D] ★ API 경계 ★  백엔드와 만나는 유일한 지점. 여기만 고칩니다.
   [E] ▼ 목업 블록 ▼  백엔드 대신 브라우저에서 계산하는 임시 코드.
                      백엔드 연결 후 통째로 삭제.
   [F] 렌더           Report 를 받아 화면을 그립니다.                (계속 사용)
   [G] 화면 전환      불러오는 중 / 입력 / 분석 중 / 리포트 / 실패.  (계속 사용)
   [H] 이벤트·시작                                                   (계속 사용)

   ---------------------------------------------------------------------------
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
       경고 띠가 자동으로 뜹니다.

   ########################################################################### */


/* =========================================================================
   [B] 유틸 — 문자열 이스케이프와 자주 쓰는 작은 부품들
   ========================================================================= */
const esc = s => String(s ?? '').replace(/[&<>"]/g,
  c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

const fmt = n => Number(n).toLocaleString('ko-KR', {maximumFractionDigits:1});

/** 게이지 가운데 숫자의 글자 크기 — 자릿수가 늘면 글자를 줄입니다.
    화면 생김새에 관한 것이므로 서버가 아니라 여기서 정합니다. */
function gaugeSize(label){
  const digits = (String(label).match(/\d/g) || []).length;
  if(!digits) return 24;
  return digits === 1 ? 32 : digits === 2 ? 30 : digits === 3 ? 26 : 24;
}

/** 색이 필요한 부품은 전부 토큰(TONE)에서 색을 받아 갑니다. */
const chip = (text, tone) => {
  const t = TONE[tone];
  return `<span class="chip" style="background:${t.bg};color:${t.fg};border-color:${t.bd}">${esc(text)}</span>`;
};
const tag = (text, tone) => {
  const t = TONE[tone];
  return `<span class="tag" style="background:${t.bg};color:${t.fg};border-color:${t.bd}">${esc(text)}</span>`;
};
const bigchip = (text, tone) => {
  const t = TONE[tone];
  return `<span class="bigchip" style="background:${t.bg};color:${t.fg};border-color:${t.bd}">${esc(text)}</span>`;
};

/** 데이터가 없을 때 그 자리에 대신 들어가는 카드 */
const emptyCard = (title, desc, link, plain, to) =>
  `<div class="empty${plain ? ' plain' : ''}">
     <span class="empty-t">${esc(title)}</span>
     <span class="empty-d">${esc(desc)}</span>
     ${link ? `<a class="link" href="#"${to ? ` data-act="edit" data-to="${to}"` : ''}>${esc(link)}</a>` : ''}
   </div>`;

/** 입력 화면의 해당 섹션으로 이동하는 링크.
    to 는 'profile' | 'exam' | 'meds' | 'products' 입니다. */
const editLink = (to, text) =>
  `<a class="link edit" href="#" data-act="edit" data-to="${to}">${esc(text)}</a>`;

/** 조사 — 앞말의 받침에 따라 은/는, 이/가, 을/를 을 고릅니다. */
const JONG = {'0':1,'1':1,'3':1,'6':1,'7':1,'8':1,'2':0,'4':0,'5':0,'9':0,
              'l':1,'m':1,'n':1,'r':1,'L':1,'M':1,'N':1,'R':1};
function josa(word, withJong, without){
  const c = String(word || '').trim().slice(-1);
  const code = c.charCodeAt(0);
  let has;
  if(code >= 0xAC00 && code <= 0xD7A3) has = (code - 0xAC00) % 28 !== 0;  // 한글
  else if(c in JONG)                   has = !!JONG[c];                   // 숫자·영문 발음
  else                                 has = false;
  return word + (has ? withJong : without);
}
const eun = w => josa(w, '은', '는');
const ga  = w => josa(w, '이', '가');
const eul = w => josa(w, '을', '를');


/* =========================================================================
   [A] 화면 토큰 — 색 TONE
   화면의 모든 색이 여기서 나옵니다. HTML 에 색을 직접 쓰지 않으므로
   여기 한 줄만 바꾸면 배지·막대·게이지·코멘트가 한꺼번에 바뀝니다.
     fg  글자와 선 색   bg  배경색   bd  테두리색   ink  긴 문장의 글자색

   ※ 백엔드는 색 이름(green/orange/red/crit/blue/gray)만 내려보냅니다.
     실제 색값은 이 파일이 정합니다. 서버가 #15803D 같은 색을 직접
     내려보내지 않도록 하세요. 디자인을 바꿀 때 서버까지 고쳐야 합니다.
   ========================================================================= */
const TONE = {
  green : {fg:'#15803D', bg:'#EAF6EE', bd:'#C3E5CE', ink:'#14532D'},
  orange: {fg:'#C2410C', bg:'#FFF1E8', bd:'#FBD3B8', ink:'#9A3412'},
  red   : {fg:'#DC2626', bg:'#FDECEC', bd:'#F7D4D4', ink:'#991B1B'},
  crit  : {fg:'#991B1B', bg:'#FDECEC', bd:'#F7D4D4', ink:'#991B1B'},
  blue  : {fg:'#1E3A8A', bg:'#EAEFF9', bd:'#CBD8F0', ink:'#1E3A8A'},
  gray  : {fg:'#6B7280', bg:'#F3F4F6', bd:'#E5E7EB', ink:'#4B5563'},
};

/* -------------------------------------------------------------------------
   [A] 화면 토큰 — 섭취 수준 LEVEL
   백엔드는 level 로 아래 여섯 개 키 중 하나만 내려보냅니다
   (over · near · low · none · unknown · met).
   그 키를 무슨 색·무슨 글자로 보여 줄지는 이 표가 정합니다.
     text  카드에 나오는 이름
     rank  카드 정렬 순서. 숫자가 클수록 앞에 옵니다.
   ------------------------------------------------------------------------- */
const LEVEL = {
  over   : {tone:'crit'  , text:'매우 과다', rank:5},
  near   : {tone:'orange', text:'상한 근접', rank:4},
  /* '부족'과 '미섭취'는 파랑입니다. 빨강은 '상한을 넘었다'는 위험 신호에만
     씁니다. 식사 기준으로 보면 대부분의 성분이 부족으로 나오는데, 이걸
     전부 빨강으로 칠하면 화면이 경고로 뒤덮여 진짜 위험이 묻힙니다.
     또 권장량의 92%를 빨강으로 보여 주면 위험한 상태로 오해하게 됩니다.
     되돌리시려면 이 두 줄의 tone 을 'red' 로 바꾸면 됩니다. */
  low    : {tone:'blue'  , text:'부족'    , rank:3},
  none   : {tone:'blue'  , text:'미섭취'  , rank:2},
  unknown: {tone:'gray'  , text:'확인 불가', rank:1},
  met    : {tone:'green' , text:'충족'    , rank:0},
};

const LAYOUT = {maxCols:4, gaugeArc:163.4};   // 반원 길이 = π×52

/* =========================================================================
   [C] 입력 폼 정의
   -------------------------------------------------------------------------
   사용자에게 무엇을 물어볼지 정합니다. '판정'과는 상관이 없습니다.
   (판정은 백엔드가 합니다. 아래 EXAM 안에 판정 함수가 아직 붙어 있는데,
    그건 백엔드가 없는 동안 목업이 쓰는 것입니다. 자세한 설명은 EXAM 위에.)
   ========================================================================= */

/* 영양제 함량 입력칸의 단위 선택지 */
const UNITS = ['mg','µg','g','IU','mL','억CFU'];

/* -------------------------------------------------------------------------
   검진 판정에 쓰는 작은 부품들 — EXAM 의 ref·show·judge 가 이 이름들을 씁니다.
   ※ 원래 목업 블록 안에 있었지만, 대화형 입력에서 "방금 넣으신 값" 을 다시
     읽어 줄 때 show() 를 쓰기 때문에 목업을 지워도 남아 있어야 합니다.
     그래서 목업 블록 밖(여기)으로 옮겨 두었습니다.
   ------------------------------------------------------------------------- */
/* =========================================================================
   1-B. 건강검진 판정기준
        출처: 건강검진 실시기준 [별표 4] 및 [별표 4의 별첨] 검사항목별 판정기준
        판정 코드  A = 정상A   B = 정상B(경계)   D = 질환의심   '' = 미입력
        각 항목은 입력칸(inputs) 여러 개를 묶어 하나의 판정을 냅니다.
   ========================================================================= */
const JUDGE = {
  A: {code:'A', text:'정상A',   tone:'green'},
  B: {code:'B', text:'경계',    tone:'orange'},
  D: {code:'D', text:'질환의심', tone:'red'},
  N: {code:'',  text:'미입력',   tone:'gray'},
};
/** 코드에 다른 문구를 붙이고 싶을 때 (예: 청력 '정상', 우울증 '가벼운 우울증상') */
const J = (code, text) => ({...JUDGE[code], text: text || JUDGE[code].text});

const num = v => (v === '' || v == null || Number.isNaN(Number(v))) ? null : Number(v);
const isMale = ctx => ctx.sex === '남성';

/** 키·몸무게로 BMI 를 계산합니다. 여러 곳에서 씁니다. */
function bmiOf(v){
  const h = num(v.height), w = num(v.weight);
  if(!h || !w) return null;
  return w / ((h / 100) ** 2);
}


/* -------------------------------------------------------------------------
   검진 항목 EXAM — 입력 화면을 만드는 설계도
   -------------------------------------------------------------------------
   여기 배열의 순서가 그대로 입력 화면의 접이식 그룹 순서이고,
   리포트 표의 구분줄 순서입니다. 항목을 지우면 입력칸도 같이 사라집니다.

   ★ 이 배열은 지금 두 가지 일을 겸하고 있습니다.
       group · name · inputs  →  입력칸을 만드는 데 씁니다.   (계속 필요)
       ref · show · judge     →  판정에 씁니다.               (목업 전용)

     백엔드가 판정을 맡게 되면 ref · show · judge 는 아무도 부르지 않는
     죽은 코드가 됩니다. 그때 지우셔도 되고 그냥 두셔도 동작에는 지장이
     없습니다. (지우실 거라면 [E] 목업 블록을 지우는 김에 함께 지우세요.)

     입력칸 정의까지 서버에서 내려받고 싶다면 /api/bootstrap 응답에
     examSchema 를 담아 이 배열 대신 쓰면 됩니다. 다만 검진 항목은
     자주 바뀌지 않으므로 지금처럼 파일에 두는 편이 단순합니다.

   항목 한 개 추가하는 방법 —
     {key:'ua', name:'요산',
      inputs:[{key:'ua', unit:'mg/dL'}],          // 입력칸. key 가 저장 이름
      ref:() => '7.0 이하',                        // 표의 '판정 기준' 칸 문구
      show:v => num(v.ua) == null ? '—' : `${v.ua} mg/dL`,   // '내 수치' 칸
      judge:v => {                                 // 판정
        const x = num(v.ua);
        return x == null ? JUDGE.N : x > 7.0 ? JUDGE.D : JUDGE.A;
      }},

   칸 설명 —
     inputs  입력칸 목록. 여러 개를 묶어 하나로 판정할 수 있습니다
             (혈압 = 수축기+이완기, BMI = 키+몸무게, 폐기능 = 세 값).
             type:'select' 와 options 를 주면 숫자 대신 선택 상자가 됩니다.
     ref     성별에 따라 기준이 다르면 ctx 를 씁니다.
             예: ctx => isMale(ctx) ? '90 미만' : '85 미만'
     judge   반환값은 JUDGE.A(정상A) / JUDGE.B(경계) / JUDGE.D(질환의심) /
             JUDGE.N(미입력) 중 하나입니다.
             문구를 바꾸고 싶으면 J('D', '중간정도 우울증 의심') 처럼 씁니다.
             advice 를 붙이면 리포트 요약에 안내 문구가 강조되어 나옵니다.

   ※ 지금 값은 국가 건강검진 실시기준 [별표 4] 를 옮긴 것입니다.
     고시가 개정되면 이 배열만 고치면 됩니다.
   ------------------------------------------------------------------------- */
const EXAM = [
  {group:'폐결핵·기타흉부질환', items:[
    {key:'cxr', name:'흉부방사선촬영',
     inputs:[{key:'cxr', type:'select', options:['', '정상', '비활동성 폐결핵', '그 외 소견']}],
     ref:() => '정상',
     show:v => v.cxr || '—',
     judge:v => !v.cxr ? JUDGE.N
              : v.cxr === '정상' ? JUDGE.A
              : v.cxr === '비활동성 폐결핵' ? JUDGE.B : JUDGE.D},
  ]},

  {group:'고혈압', items:[
    {key:'bp', name:'혈압',
     inputs:[{key:'sbp', name:'수축기', unit:'mmHg'}, {key:'dbp', name:'이완기', unit:'mmHg'}],
     ref:() => '120/80 미만',
     show:v => (num(v.sbp) == null && num(v.dbp) == null) ? '—' : `${v.sbp || '—'}/${v.dbp || '—'}`,
     judge:v => {
       const s = num(v.sbp), d = num(v.dbp);
       if(s == null || d == null) return JUDGE.N;
       if(s >= 140 || d >= 90) return JUDGE.D;          // 140 이상 또는 90 이상
       if(s < 120 && d < 80)   return JUDGE.A;          // 120 미만 이며 80 미만
       return JUDGE.B;                                   // 120-139 또는 80-89
     }},
  ]},

  {group:'비만', items:[
    {key:'bmi', name:'체질량지수(BMI)',
     inputs:[{key:'height', name:'키', unit:'cm'}, {key:'weight', name:'몸무게', unit:'kg'}],
     ref:() => '18.5~24.9',
     show:v => {
       const b = bmiOf(v);
       return b == null ? '—' : `${b.toFixed(1)} kg/m²`;
     },
     judge:v => {
       const b = bmiOf(v);
       if(b == null) return JUDGE.N;
       if(b < 18.5 || b >= 30) return JUDGE.D;
       if(b <= 24.9) return JUDGE.A;
       return JUDGE.B;                                   // 25 ~ 29.9
     }},
    {key:'waist', name:'허리둘레',
     inputs:[{key:'waist', unit:'cm'}],
     ref:ctx => isMale(ctx) ? '90 미만' : '85 미만',
     show:v => num(v.waist) == null ? '—' : `${v.waist} cm`,
     judge:(v, ctx) => {
       const w = num(v.waist);
       if(w == null) return JUDGE.N;
       return w < (isMale(ctx) ? 90 : 85) ? JUDGE.A : JUDGE.B;   // 질환의심 구분 없음
     }},
  ]},

  {group:'빈혈', items:[
    {key:'hb', name:'혈색소',
     inputs:[{key:'hb', unit:'g/dL'}],
     ref:ctx => isMale(ctx) ? '13.0~16.5' : '12.0~15.5',
     show:v => num(v.hb) == null ? '—' : `${v.hb} g/dL`,
     judge:(v, ctx) => {
       const h = num(v.hb);
       if(h == null) return JUDGE.N;
       if(isMale(ctx)){
         if(h < 12.0) return JUDGE.D;
         if(h < 13.0) return JUDGE.B;
         return h <= 16.5 ? JUDGE.A : JUDGE.B;   // 상한 초과는 기준표에 없어 경계로 둡니다
       }
       if(h < 10.0) return JUDGE.D;
       if(h < 12.0) return JUDGE.B;
       return h <= 15.5 ? JUDGE.A : JUDGE.B;
     }},
  ]},

  {group:'당뇨병', items:[
    {key:'glu', name:'공복혈당',
     inputs:[{key:'glu', unit:'mg/dL'}],
     ref:() => '100 미만',
     show:v => num(v.glu) == null ? '—' : `${v.glu} mg/dL`,
     judge:v => {
       const g = num(v.glu);
       if(g == null) return JUDGE.N;
       return g >= 126 ? JUDGE.D : g >= 100 ? JUDGE.B : JUDGE.A;
     }},
  ]},

  {group:'이상지질혈증', items:[
    {key:'tc', name:'총콜레스테롤', inputs:[{key:'tc', unit:'mg/dL'}], ref:() => '200 미만',
     show:v => num(v.tc) == null ? '—' : `${v.tc} mg/dL`,
     judge:v => {const x = num(v.tc); return x == null ? JUDGE.N : x >= 240 ? JUDGE.D : x >= 200 ? JUDGE.B : JUDGE.A;}},
    {key:'hdl', name:'HDL 콜레스테롤', inputs:[{key:'hdl', unit:'mg/dL'}], ref:() => '60 이상',
     show:v => num(v.hdl) == null ? '—' : `${v.hdl} mg/dL`,
     judge:v => {const x = num(v.hdl); return x == null ? JUDGE.N : x < 40 ? JUDGE.D : x < 60 ? JUDGE.B : JUDGE.A;}},
    {key:'tg', name:'중성지방', inputs:[{key:'tg', unit:'mg/dL'}], ref:() => '150 미만',
     show:v => num(v.tg) == null ? '—' : `${v.tg} mg/dL`,
     judge:v => {const x = num(v.tg); return x == null ? JUDGE.N : x >= 200 ? JUDGE.D : x >= 150 ? JUDGE.B : JUDGE.A;}},
    {key:'ldl', name:'LDL 콜레스테롤', inputs:[{key:'ldl', unit:'mg/dL'}], ref:() => '130 미만',
     show:v => num(v.ldl) == null ? '—' : `${v.ldl} mg/dL`,
     judge:v => {const x = num(v.ldl); return x == null ? JUDGE.N : x >= 160 ? JUDGE.D : x >= 130 ? JUDGE.B : JUDGE.A;}},
  ]},

  {group:'간장질환', items:[
    {key:'ast', name:'AST(SGOT)', inputs:[{key:'ast', unit:'U/L'}], ref:() => '40 이하',
     show:v => num(v.ast) == null ? '—' : `${v.ast} U/L`,
     judge:v => {const x = num(v.ast); return x == null ? JUDGE.N : x >= 51 ? JUDGE.D : x >= 41 ? JUDGE.B : JUDGE.A;}},
    {key:'alt', name:'ALT(SGPT)', inputs:[{key:'alt', unit:'U/L'}], ref:() => '35 이하',
     show:v => num(v.alt) == null ? '—' : `${v.alt} U/L`,
     judge:v => {const x = num(v.alt); return x == null ? JUDGE.N : x >= 46 ? JUDGE.D : x >= 36 ? JUDGE.B : JUDGE.A;}},
    {key:'ggt', name:'γ-GTP', inputs:[{key:'ggt', unit:'U/L'}],
     ref:ctx => isMale(ctx) ? '11~63' : '8~35',
     show:v => num(v.ggt) == null ? '—' : `${v.ggt} U/L`,
     judge:(v, ctx) => {
       const x = num(v.ggt);
       if(x == null) return JUDGE.N;
       if(isMale(ctx)) return x >= 78 ? JUDGE.D : x >= 64 ? JUDGE.B : x >= 11 ? JUDGE.A : JUDGE.B;
       return x >= 46 ? JUDGE.D : x >= 36 ? JUDGE.B : x >= 8 ? JUDGE.A : JUDGE.B;
     }},
  ]},

  {group:'신장질환', items:[
    {key:'upro', name:'요단백',
     inputs:[{key:'upro', type:'select', options:['', '음성(-)', '약양성(±)', '양성(+1) 이상']}],
     ref:() => '음성(-)',
     show:v => v.upro || '—',
     judge:v => !v.upro ? JUDGE.N : v.upro === '음성(-)' ? JUDGE.A : v.upro === '약양성(±)' ? JUDGE.B : JUDGE.D},
    {key:'cr', name:'혈청크레아티닌', inputs:[{key:'cr', unit:'mg/dL'}], ref:() => '1.5 이하',
     show:v => num(v.cr) == null ? '—' : `${v.cr} mg/dL`,
     judge:v => {const x = num(v.cr); return x == null ? JUDGE.N : x > 1.5 ? JUDGE.D : JUDGE.A;}},
    {key:'egfr', name:'신사구체여과율(e-GFR)', inputs:[{key:'egfr', unit:'mL/min'}], ref:() => '60 이상',
     show:v => num(v.egfr) == null ? '—' : `${v.egfr} mL/min/1.73m²`,
     judge:v => {const x = num(v.egfr); return x == null ? JUDGE.N : x < 60 ? JUDGE.D : JUDGE.A;}},
  ]},

  {group:'골다공증', items:[
    {key:'tscore', name:'골밀도 T-score', inputs:[{key:'tscore', unit:'T'}], ref:() => '-1 이상',
     show:v => num(v.tscore) == null ? '—' : `${v.tscore}`,
     judge:v => {const x = num(v.tscore); return x == null ? JUDGE.N : x <= -2.5 ? JUDGE.D : x >= -1 ? JUDGE.A : JUDGE.B;}},
    {key:'bmd', name:'골밀도(정량)', inputs:[{key:'bmd', unit:'mg/㎤'}], ref:() => '120 초과',
     show:v => num(v.bmd) == null ? '—' : `${v.bmd} mg/㎤`,
     judge:v => {const x = num(v.bmd); return x == null ? JUDGE.N : x < 80 ? JUDGE.D : x > 120 ? JUDGE.A : JUDGE.B;}},
  ]},

  {group:'노인 신체기능', items:[
    {key:'leg', name:'하지기능', inputs:[{key:'leg', unit:'초'}], ref:() => '10초 이내',
     show:v => num(v.leg) == null ? '—' : `${v.leg}초`,
     judge:v => {const x = num(v.leg); return x == null ? JUDGE.N : x >= 20 ? JUDGE.D : x > 10 ? JUDGE.B : JUDGE.A;}},
    {key:'balC', name:'평형성(눈 감은 상태)', inputs:[{key:'balC', unit:'초'}], ref:() => '15초 이상',
     show:v => num(v.balC) == null ? '—' : `${v.balC}초`,
     judge:v => {const x = num(v.balC); return x == null ? JUDGE.N : x <= 5 ? JUDGE.D : x < 15 ? JUDGE.B : JUDGE.A;}},
    {key:'balO', name:'평형성(눈 뜬 상태)', inputs:[{key:'balO', unit:'초'}], ref:() => '20초 이상',
     show:v => num(v.balO) == null ? '—' : `${v.balO}초`,
     judge:v => {const x = num(v.balO); return x == null ? JUDGE.N : x <= 9 ? JUDGE.D : x < 20 ? JUDGE.B : JUDGE.A;}},
  ]},

  {group:'정신건강·인지', items:[
    {key:'phq9', name:'우울증(PHQ-9)',
     inputs:[{key:'phq9', name:'총점', unit:'점'},
             {key:'phq9q9', type:'select', name:'9번 문항', options:['', '0점', '1점 이상']}],
     ref:() => '0~4점',
     show:v => num(v.phq9) == null ? '—' : `${v.phq9}점`,
     judge:v => {
       const x = num(v.phq9);
       if(x == null) return JUDGE.N;
       const care = '가까운 정신건강의학과나 지역 정신건강복지센터에서 상담받아 보시기를 권합니다.';
       if(x >= 20 || v.phq9q9 === '1점 이상')
         return {...J('D', '심한 우울증 의심'), advice:'되도록 빠른 시일 안에 전문가와 상담하시기 바랍니다. ' + care};
       if(x >= 10) return {...J('D', '중간정도 우울증 의심'), advice: care};
       if(x >= 5)  return J('B', '가벼운 우울증상');
       return J('A', '우울증상 없음');
     }},
    {key:'cape', name:'조기정신증(CAPE-15)',
     inputs:[{key:'capeF', name:'빈도 총점', unit:'점'}, {key:'capeD', name:'고통 총점', unit:'점'}],
     ref:() => '각 0~5점',
     show:v => (num(v.capeF) == null && num(v.capeD) == null) ? '—' : `빈도 ${v.capeF || '—'} · 고통 ${v.capeD || '—'}`,
     judge:v => {
       const f = num(v.capeF), d = num(v.capeD);
       if(f == null && d == null) return JUDGE.N;
       return ((f ?? 0) >= 6 || (d ?? 0) >= 6)
         ? {...J('D', '전문의 진단 필요'), advice:'정신건강의학과 전문의의 진단이 필요한 결과입니다.'}
         : J('A', '특이소견 없음');
     }},
    {key:'kdsq', name:'인지기능(KDSQ-C)', inputs:[{key:'kdsq', unit:'점'}], ref:() => '0~5점',
     show:v => num(v.kdsq) == null ? '—' : `${v.kdsq}점`,
     judge:v => {const x = num(v.kdsq);
       return x == null ? JUDGE.N
            : x >= 6 ? {...J('D', '인지기능 저하 의심'), advice:'치매안심센터나 신경과 진료를 통한 정밀검사를 권합니다.'}
            : J('A', '특이소견 없음');}},
  ]},

  {group:'청력', items:[
    {key:'pta', name:'순음청력검사', inputs:[{key:'pta', unit:'dB'}], ref:() => '40dB 미만',
     show:v => num(v.pta) == null ? '—' : `${v.pta} dB`,
     judge:v => {const x = num(v.pta); return x == null ? JUDGE.N : x >= 40 ? J('D', '질환의심') : J('A', '정상');}},
    {key:'whisper', name:'귓속말 검사',
     inputs:[{key:'whisper', type:'select', options:['', '양쪽 3개 이상 정확', '한쪽이라도 3개 미만']}],
     ref:() => '양쪽 3개 이상',
     show:v => v.whisper || '—',
     judge:v => !v.whisper ? JUDGE.N : v.whisper === '양쪽 3개 이상 정확' ? J('A', '정상') : J('D', '정밀검사 의뢰')},
  ]},

  {group:'만성폐쇄성폐질환', items:[
    {key:'spiro', name:'폐기능검사',
     inputs:[{key:'ratio', name:'FEV1/FVC', unit:'%'}, {key:'fev1', name:'FEV1', unit:'%'}, {key:'fvc', name:'FVC', unit:'%'}],
     ref:() => 'FEV1/FVC 70 이상',
     show:v => (num(v.ratio) == null) ? '—' : `FEV1/FVC ${v.ratio}%`,
     judge:v => {
       const r = num(v.ratio), e = num(v.fev1), f = num(v.fvc);
       if(r == null) return JUDGE.N;
       if(r < 70) return J('D', 'COPD 의심');
       if((e != null && e < 80) || (f != null && f < 80)) return J('B', '기타 폐기능 이상');
       return JUDGE.A;
     }},
  ]},

  {group:'구강', items:[
    {key:'caries',  name:'우식치아',   inputs:[{key:'caries',  type:'select', options:['', '없음', '있음']}],
     ref:() => '없음', show:v => v.caries || '—',
     judge:v => !v.caries ? JUDGE.N : v.caries === '없음' ? J('A', '양호') : J('D', '치료필요')},
    {key:'suspect', name:'우식의심치아', inputs:[{key:'suspect', type:'select', options:['', '없음', '있음']}],
     ref:() => '없음', show:v => v.suspect || '—',
     judge:v => !v.suspect ? JUDGE.N : v.suspect === '없음' ? J('A', '양호') : J('D', '질환의심')},
    {key:'filled',  name:'수복치아',   inputs:[{key:'filled',  type:'select', options:['', '없음', '있음']}],
     ref:() => '없음', show:v => v.filled || '—',
     judge:v => !v.filled ? JUDGE.N : v.filled === '없음' ? J('A', '양호') : J('B', '주의')},
    {key:'lost',    name:'상실치아',   inputs:[{key:'lost',    type:'select', options:['', '없음', '있음']}],
     ref:() => '없음', show:v => v.lost || '—',
     judge:v => !v.lost ? JUDGE.N : v.lost === '없음' ? J('A', '양호') : J('D', '치료필요')},
    {key:'gingiva', name:'치은염증',   inputs:[{key:'gingiva', type:'select', options:['', '없음', '경증', '중증']}],
     ref:() => '없음', show:v => v.gingiva || '—',
     judge:v => !v.gingiva ? JUDGE.N : v.gingiva === '없음' ? J('A', '양호') : v.gingiva === '경증' ? J('D', '질환의심') : J('D', '치료필요')},
    {key:'calculus',name:'치석',       inputs:[{key:'calculus',type:'select', options:['', '없음', '경증', '중증']}],
     ref:() => '없음', show:v => v.calculus || '—',
     judge:v => !v.calculus ? JUDGE.N : v.calculus === '없음' ? J('A', '양호') : v.calculus === '경증' ? J('D', '질환의심') : J('D', '치료필요')},
    {key:'plaque',  name:'치면세균막검사', inputs:[{key:'plaque', unit:'점'}], ref:() => '1점 미만',
     show:v => num(v.plaque) == null ? '—' : `${v.plaque}점`,
     judge:v => {const x = num(v.plaque); return x == null ? JUDGE.N : x >= 3 ? J('D', '개선요망') : x >= 1 ? J('B', '보통') : J('A', '우수');}},
  ]},
];

/* [교체지점 3-2] 종합 판정에 쓰이는 목록 두 개.
   CHRONIC 은 입력 화면의 '진단 후 약물 치료 중인 질환' 선택지이자
   '유질환자' 판정의 근거이고, HTN_DM_LIPID 는 어떤 항목이 질환의심일 때
   '고혈압·당뇨병·이상지질혈증 질환의심' 으로 올릴지 정합니다.
   HTN_DM_LIPID 에는 EXAM 항목의 key 를 적습니다. */
const CHRONIC = ['고혈압','당뇨병','이상지질혈증','폐결핵','우울증','조기정신증','C형간염','만성폐쇄성폐질환'];


/* =========================================================================
   [D] ★ API 경계 ★  — 백엔드와 만나는 유일한 지점
   -------------------------------------------------------------------------
   이 파일에서 서버와 이야기하는 곳은 여기 하나뿐입니다.
   화면을 그리는 코드는 아래 API.* 만 부르고, 서버 주소도 응답 형태도
   모릅니다. 그래서 서버가 바뀌어도 화면 코드는 그대로입니다.

   ── 백엔드 연결하는 법 (세 단계) ───────────────────────────────────────
     1. 바로 아래 USE_MOCK 을 false 로 바꿉니다.
     2. API_BASE 에 서버 주소를 적습니다. (같은 도메인이면 '' 그대로 두세요)
     3. [E] 목업 블록을 통째로 지웁니다.
     끝입니다. 이 아래 화면 코드는 한 줄도 건드리지 않습니다.

   ── 서버가 제공해야 하는 것 네 가지 ────────────────────────────────────
     GET  /api/bootstrap   화면 열 때 한 번. 성분 이름 추천 목록 등.
     GET  /api/draft       로그인한 사용자가 저장해 둔 입력값 불러오기
     PUT  /api/draft       입력값 저장 (사용자가 입력하는 동안 자동으로)
     POST /api/analyze     ★ 핵심. 입력을 보내고 AI 판정 결과를 받습니다.

   주고받는 JSON 의 정확한 형태는 함께 드린 '백엔드 연동 규격서'에
   예시와 함께 정리되어 있습니다.
   ========================================================================= */

const USE_MOCK = false;      /* ← 백엔드가 준비되면 false 로 */
const API_BASE = 'http://localhost:8000';        /* ← 예: 'https://api.myherb.co.kr' */

/** 서버 오류를 화면이 알아들을 수 있는 형태로 감쌉니다.
    code 로 무엇이 잘못됐는지 구분하고, message 는 사용자에게 보여 줍니다. */
class ApiError extends Error {
  constructor(code, message, detail){
    super(message);
    this.code = code;             // LOGIN_REQUIRED · TIMEOUT · NETWORK · HTTP_500 ...
    this.detail = detail || '';   // 개발자용 원문 (화면 하단에 작게 표시)
  }
}

/** 모든 서버 호출이 지나가는 통로. 인증 쿠키·시간초과·오류 변환을 한곳에서.
    surfaceMessage: true 면 서버가 보낸 message 를 화면에 그대로 보여 줍니다.
    로그인·회원가입 폼처럼 '왜 실패했는지'가 사용자에게 중요한 경우에만 켜세요.
    그 밖의 요청은 서버 메시지를 detail(개발자용)에만 남기고, 화면에는
    두루뭉술한 문구를 보여 주는 게 안전합니다(문구가 사용자 안내로
    다듬어져 있다는 보장이 없으므로). */
async function call(path, {method = 'GET', body, raw, form, timeout = 60000, surfaceMessage = false} = {}){
  const ctrl  = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout);
  try {
    /* raw 는 JSON 이 아닌 것을 그대로 보낼 때 씁니다(검진표 사진 한 장).
       파일 하나뿐이라 multipart 로 감싸지 않고 바이트를 그대로 실어 보냅니다
       — 그 편이 서버도 훨씬 단순합니다. */
    /* form(FormData) 으로 보낼 때는 Content-Type 을 우리가 정하면 안 됩니다.
       multipart 는 헤더에 boundary 가 들어가야 하는데, 그 값은 브라우저만
       알고 있습니다. 직접 적으면 boundary 가 빠져서 서버가 못 읽습니다. */
    const headers = form ? {}
                  : raw  ? (raw.type ? {'Content-Type': raw.type} : {})
                         : {'Content-Type': 'application/json'};

    const res = await fetch(API_BASE + path, {
      method,
      headers,
      credentials: 'include',        /* 로그인 쿠키를 함께 보냅니다 */
      body       : form ? form : (raw ? raw : (body ? JSON.stringify(body) : undefined)),
      signal     : ctrl.signal,
    });

    /* ★ 401/403 은 이 서비스 전체에서 '로그인 세션이 없거나 끊겼다'는
       뜻으로만 씁니다. 로그인·회원가입 요청 자체가 거절된 경우(비밀번호
       틀림, 이메일 중복 등)는 서버가 401/403 이 아닌 다른 코드(예: 400)로
       내려줘야 여기서 재로그인 모달로 잘못 넘어가지 않습니다. */
    if(res.status === 401 || res.status === 403)
      throw new ApiError('LOGIN_REQUIRED', '로그인이 필요합니다.');

    if(!res.ok){
      let detail = '';
      try { const j = await res.json(); detail = j.message || JSON.stringify(j); }
      catch(_){ detail = await res.text().catch(() => ''); }
      const fallback = res.status >= 500 ? '서버에 문제가 생겼습니다.' : '요청을 처리하지 못했습니다.';
      throw new ApiError('HTTP_' + res.status, (surfaceMessage && detail) ? detail : fallback, detail);
    }
    return await res.json();

  } catch(e){
    if(e instanceof ApiError) throw e;
    if(e.name === 'AbortError')
      throw new ApiError('TIMEOUT', '응답이 너무 오래 걸립니다. 잠시 후 다시 시도해 주세요.');
    throw new ApiError('NETWORK', '서버에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.', String(e && e.message || e));
  } finally {
    clearTimeout(timer);
  }
}

const API = {
  /** 지금 목업으로 도는 중인지. 화면 맨 위 경고 띠가 이 값을 봅니다. */
  get source(){ return USE_MOCK ? 'mock' : 'server'; },

  /** 화면을 열 때 한 번 — 성분 이름 추천 목록 등 */
  bootstrap(){
    if(USE_MOCK) return MOCK.bootstrap();
    return call('/api/bootstrap', {timeout:15000});
  },

  /** 저장해 둔 입력값 불러오기. 없으면 null.
      로그인이 안 되어 있어도 화면은 그냥 열려야 하므로 null 로 넘깁니다. */
  async loadDraft(){
    if(USE_MOCK) return MOCK.loadDraft();
    try { return await call('/api/draft', {timeout:15000}); }
    catch(e){
      if(e.code === 'LOGIN_REQUIRED' || e.code === 'HTTP_404') return null;
      console.warn('[draft] 불러오기 실패 — 빈 화면으로 시작합니다.', e);
      return null;
    }
  },

  /** 입력값 저장. 실패해도 입력을 막지 않습니다(표시만 합니다). */
  saveDraft(input){
    if(USE_MOCK) return MOCK.saveDraft(input);
    return call('/api/draft', {method:'PUT', body:input, timeout:15000});
  },

  /** ★ 판정 요청. AI 가 처리하므로 수십 초가 걸립니다.
      검진표 사진을 올렸다면 그 사진도 함께 보냅니다 — 서버가 사진을
      보관하지 않으므로, 분석할 때마다 브라우저가 다시 실어 보냅니다. */
  analyze(input){
    if(USE_MOCK) return MOCK.analyze(input);
    const file = CHAT.examFile;
    if(file){
      const fd = new FormData();
      fd.append('input', JSON.stringify(input));
      fd.append('file', file, file.name || 'exam');
      return call('/api/analyze', {method:'POST', form:fd, timeout:180000});
    }
    return call('/api/analyze', {method:'POST', body:input, timeout:180000});
  },

  /* -----------------------------------------------------------------------
     인증 — 로그인 전에는 이 서비스를 쓸 수 없으므로, 화면을 열 때마다
     가장 먼저 me() 로 로그인 상태를 확인합니다.
     ----------------------------------------------------------------------- */

  /** 지금 로그인되어 있는지. 되어 있으면 {name, email}, 아니면 LOGIN_REQUIRED 예외. */
  me(){
    if(USE_MOCK) return MOCK.me();
    return call('/api/me', {timeout:15000});
  },

  login(email, password){
    console.log(USE_MOCK)
    if(USE_MOCK) return MOCK.login(email, password);
    const formData = new URLSearchParams();
    formData.append('id', email);
    formData.append('pwd', password);
    return call('/api/login', {method:'POST', body:formData, timeout:15000, surfaceMessage:true});
  },

  signup(name, email, password){
    if(USE_MOCK) return MOCK.signup(name, email, password);
    const formData = new URLSearchParams();
    formData.append('id', email);
    formData.append('pwd', password);
    formData.append('name', name);
    return call('/api/signup', {method:'POST', body:formData, timeout:15000, surfaceMessage:true});
  },

  logout(){
    if(USE_MOCK) return MOCK.logout();
    return call('/api/logout', {method:'POST', timeout:15000});
  },

  /* -----------------------------------------------------------------------
     지난 리포트 — 로그인한 사용자가 예전에 분석했던 결과를 다시 봅니다.
     ----------------------------------------------------------------------- */

  /** 목록은 가벼운 요약만. 전체 성분·소견은 리포트를 열 때(getReport) 받습니다. */
  listReports(){
    if(USE_MOCK) return MOCK.listReports();
    return call('/api/reports', {timeout:15000});
  },

  /** 리포트 하나의 전체 내용. analyze() 의 응답과 같은 Report 모양입니다. */
  getReport(id){
    if(USE_MOCK) return MOCK.getReport(id);
    return call('/api/reports/' + encodeURIComponent(id), {timeout:15000});
  },

  /** 리포트 하나 지우기. 되돌릴 수 없으므로 화면에서 한 번 더 확인받습니다. */
  deleteReport(id){
    if(USE_MOCK) return MOCK.deleteReport(id);
    return call('/api/reports/' + encodeURIComponent(id), {method:'DELETE', timeout:15000});
  },

  /** ★ 검진표 사진 한 장을 보내 검진값을 읽어 옵니다.
      판독은 서버가 합니다 — 화면은 사진을 그대로 넘기고 결과를 받아 채우기만
      합니다. 응답 모양은 vision.py 의 read_exam_image() 주석에 있습니다.
      사람이 읽는 모델을 거치므로 analyze 와 같은 60초를 기다립니다. */
  readExamImage(file){
    if(USE_MOCK) return MOCK.readExamImage(file);
    return call('/api/exam-image', {method:'POST', raw:file, timeout:60000});
  },
};


/* ###########################################################################
   ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼  [E] 목업 블록 — 시작  ▼▼▼▼▼▼▼▼▼▼▼▼▼▼▼

   백엔드가 없는 동안, 브라우저 안에서 판정을 흉내 내는 임시 코드입니다.
   실제 서비스에서는 이 일을 전부 서버의 AI 가 합니다.

   ★ 백엔드 연결이 끝나면 이 줄부터 '[E] 목업 블록 — 끝' 줄까지를
     통째로 지우고, [D] 의 USE_MOCK 을 false 로 바꾸면 됩니다.
     이 블록 밖의 코드는 여기 있는 어떤 이름도 직접 부르지 않습니다.
     (유일한 연결점은 [D] 의 MOCK.* 호출 네 군데뿐입니다.)

   ※ 여기 들어 있는 성분 기준값과 상호작용 규칙은 검증되지 않은 예시입니다.
     USE_MOCK 이 true 인 동안에는 화면 맨 위에 경고 띠가 자동으로 뜹니다.
   ########################################################################### */

/** 서버 응답을 기다리는 느낌을 내기 위한 지연 */
const nap = ms => new Promise(r => setTimeout(r, ms));

/* 단위 환산표 — 사용자가 무슨 단위로 적든 기준값의 단위로 바꿉니다.
   질량은 mg 를 축으로, IU 는 성분마다 계수가 달라 기준표에 iu 가
   있는 성분만 환산합니다. */
const MASS = {g:1000, mg:1, 'µg':0.001, ug:0.001, mcg:0.001};


/* =========================================================================
   [교체지점 1] 성분 기준표 STD_LIST
   -------------------------------------------------------------------------
   이 표 하나가 성분 카드의 게이지·막대·판정·문구를 전부 결정합니다.

   한 줄 추가하는 방법 —
     {name:'코엔자임Q10', unit:'mg', rda:100, ul:300, meal:5,
      alias:['coq10','코큐텐','유비퀴놀']},

   칸 설명 —
     name    화면에 나오는 이름. 여러 표기를 이 이름으로 모읍니다.
     unit    기준값의 단위. 사용자가 다른 단위로 넣어도 이 단위로 환산합니다.
     rda     권장섭취량. null 이면 '권장 대비' 비율을 계산하지 않습니다.
     ul      상한섭취량. null 이면 상한 마커와 초과 판정이 생략됩니다.
     meal    식사에서 섭취하는 평균 추정치. 막대의 회색 구간입니다.
             근거가 없으면 0 으로 두세요.
     alias   사용자가 다르게 적어도 같은 성분으로 묶을 표기들.
             공백·하이픈·괄호·대소문자는 자동으로 무시하므로
             '비타민 C' 를 넣을 필요 없이 '비타민c' 한 번이면 됩니다.
     ulBasis 'supp' 를 넣으면 상한을 영양제 섭취량만으로 비교합니다.
             마그네슘·엽산처럼 보충제 기준 상한이 있는 성분에 씁니다.
             생략하면 식사분까지 더한 값으로 비교합니다.
     iu      1 IU 가 몇 unit 인지. 이 값이 없으면 사용자가 IU 로 입력했을 때
             환산하지 못하고 '환산 불가' 로 처리합니다.

   ※ 지금 값은 예시입니다. 검증된 출처(KDRI 등)로 교체하세요.
   ========================================================================= */
const STD_LIST = [
  {name:'비타민 A',  unit:'µg', rda:700,  ul:3000, meal:500, iu:0.3,
   alias:['비타민a','레티놀','retinol','vitamina']},
  {name:'비타민 B1', unit:'mg', rda:1.2,  ul:null, meal:1.1,
   alias:['비타민b1','티아민','thiamine']},
  {name:'비타민 B2', unit:'mg', rda:1.4,  ul:null, meal:1.3,
   alias:['비타민b2','리보플라빈','riboflavin']},
  {name:'나이아신',  unit:'mg', rda:15,   ul:35,   meal:15, ulBasis:'supp',
   alias:['비타민b3','니아신','niacin','나이아신아마이드']},
  {name:'비타민 B6', unit:'mg', rda:1.5,  ul:100,  meal:1.6,
   alias:['비타민b6','피리독신','pyridoxine']},
  {name:'엽산',      unit:'µg', rda:400,  ul:1000, meal:300, ulBasis:'supp',
   alias:['비타민b9','폴산','folate','folicacid']},
  {name:'비타민 B12',unit:'µg', rda:2.4,  ul:null, meal:4,
   alias:['비타민b12','코발라민','cobalamin','메틸코발라민']},
  {name:'비타민 C',  unit:'mg', rda:100,  ul:2000, meal:65,
   alias:['비타민c','아스코르브산','ascorbicacid','vitaminc']},
  {name:'비타민 D',  unit:'µg', rda:10,   ul:100,  meal:3, iu:0.025,
   alias:['비타민d','비타민d3','콜레칼시페롤','cholecalciferol','vitamind']},
  {name:'비타민 E',  unit:'mg', rda:12,   ul:540,  meal:9, iu:0.67,
   alias:['비타민e','토코페롤','tocopherol','vitamine']},
  {name:'비타민 K',  unit:'µg', rda:70,   ul:null, meal:90,
   alias:['비타민k','비타민k1','비타민k2','메나퀴논','필로퀴논']},
  {name:'칼슘',      unit:'mg', rda:800,  ul:2500, meal:490,
   alias:['ca','calcium','탄산칼슘']},
  {name:'마그네슘',  unit:'mg', rda:350,  ul:350,  meal:280, ulBasis:'supp',
   alias:['magnesium','산화마그네슘','마그네슘디아스파르트산']},
  {name:'철',        unit:'mg', rda:12,   ul:45,   meal:9,
   alias:['fe','철분','iron']},
  {name:'아연',      unit:'mg', rda:10,   ul:35,   meal:8,
   alias:['zn','zinc','징크']},
  {name:'셀레늄',    unit:'µg', rda:60,   ul:400,  meal:55,
   alias:['se','셀렌','selenium']},
  {name:'오메가3',   unit:'mg', rda:1000, ul:null, meal:320,
   alias:['omega3','epa','dha','epadha','피쉬오일','어유']},
  {name:'루테인',    unit:'mg', rda:10,   ul:20,   meal:1,
   alias:['lutein','루테인지아잔틴']},
];

/** 표기를 비교용 키로 정규화합니다. 공백·하이픈·괄호를 지웁니다. */
const normKey = s => String(s || '').toLowerCase().replace(/[\s\-_·・.()（）]/g, '');

/* 별칭까지 펼친 조회표 */
const STD_INDEX = {};
STD_LIST.forEach(s => [s.name, ...(s.alias || [])].forEach(a => STD_INDEX[normKey(a)] = s));
const findStd = name => STD_INDEX[normKey(name)] || null;

/* =========================================================================
   [교체지점 2] 약물 ↔ 성분 상호작용 MED_RULES
   -------------------------------------------------------------------------
   사용자가 적은 약 이름 안에 med 의 표기가 하나라도 들어 있고,
   동시에 nut 성분이 영양제에 들어 있으면 점검 섹션에 한 줄이 생깁니다.

   한 줄 추가하는 방법 —
     {med:['자렐토','리바록사반'], nut:'비타민 K', kind:'복약 주의', tone:'red',
      text:'설명 문구가 그대로 화면에 나옵니다.'},

   칸 설명 —
     med   약 이름에서 찾을 표기들. 부분 일치이므로 '와파린' 하나면
           '와파린정 2mg', '와파린 5mg' 모두 걸립니다.
     nut   STD_LIST 의 name 과 똑같이 적어야 합니다.
     kind  화면 왼쪽 배지에 나오는 짧은 분류명.
     tone  배지 색. TONE 의 키 중 하나 (red · orange · blue · gray · green).
     text  사용자에게 보여 줄 문장. 앞에 약 이름이 자동으로 붙습니다.

   ※ 지금 값은 예시입니다. 검증된 상호작용 DB 로 교체하고,
     문구는 전문가 검토를 받으시길 권합니다.
   ========================================================================= */
const MED_RULES = [
  {med:['와파린','warfarin','쿠마딘'], nut:'비타민 K', kind:'복약 주의', tone:'red',
   text:'와파린 복용 중 비타민 K 섭취량이 갑자기 바뀌면 응고 지표가 흔들릴 수 있습니다. 담당 의료진과 상의하세요.'},
  {med:['와파린','warfarin','아스피린','aspirin','클로피도그렐'], nut:'오메가3', kind:'출혈 주의', tone:'red',
   text:'항응고·항혈소판제와 오메가3를 함께 쓰면 출혈 경향이 커질 수 있습니다.'},
  {med:['레보티록신','씬지로이드','synthroid','levothyroxine'], nut:'칼슘', kind:'복용 간격', tone:'orange',
   text:'레보티록신과 칼슘은 서로 흡수를 방해합니다. 최소 4시간 간격을 두세요.'},
  {med:['레보티록신','씬지로이드','synthroid','levothyroxine'], nut:'철', kind:'복용 간격', tone:'orange',
   text:'레보티록신과 철분제는 함께 복용하지 마세요. 최소 4시간 간격이 권장됩니다.'},
  {med:['메트포르민','metformin','다이아벡스'], nut:'비타민 B12', kind:'복약 주의', tone:'orange',
   text:'메트포르민을 오래 복용하면 비타민 B12 흡수가 떨어질 수 있어 정기 확인이 권장됩니다.'},
  {med:['테트라사이클린','독시사이클린','시프로플록사신','레보플록사신','퀴놀론'], nut:'칼슘', kind:'복용 간격', tone:'orange',
   text:'이 계열 항생제는 칼슘과 결합해 흡수가 크게 떨어집니다. 2시간 이상 간격을 두세요.'},
  {med:['테트라사이클린','독시사이클린','시프로플록사신','레보플록사신','퀴놀론'], nut:'아연', kind:'복용 간격', tone:'orange',
   text:'이 계열 항생제는 아연·철과 함께 먹으면 서로 흡수가 떨어집니다.'},
  {med:['심바스타틴','아토르바스타틴','로수바스타틴','statin','스타틴'], nut:'나이아신', kind:'복약 주의', tone:'orange',
   text:'스타틴과 고용량 나이아신을 함께 쓰면 근육 관련 이상반응 위험이 올라갑니다.'},
];

/* 어떤 항목이 고혈압·당뇨병·이상지질혈증에 속하는지 (종합 판정 구분에 필요) */
const HTN_DM_LIPID = ['bp','glu','tc','hdl','tg','ldl'];


/* =========================================================================
   5. 계산 — 입력값(state)을 화면이 그대로 그릴 수 있는 모델로 바꿉니다.
      여기서 화면 요소는 만들지 않습니다. 숫자와 판정만 다룹니다.
   ========================================================================= */

/** 입력 단위를 기준표 단위로 환산합니다. 환산할 수 없으면 null 을 돌려줍니다. */
function convert(amount, unit, std){
  const v = Number(amount);
  if(!isFinite(v)) return null;
  if(unit === 'IU')  return (std && std.iu) ? v * std.iu : null;   // 계수 없는 IU 는 환산 불가
  if(!(unit in MASS)) return null;                                 // mL·억CFU 등은 질량이 아님
  const mg = v * MASS[unit];
  return std ? mg / MASS[std.unit] : mg;                           // 기준 없으면 mg 로 모읍니다
}

/* [교체지점 4-3] 섭취 수준을 가르는 구간.
   '상한의 70% 부터 상한 근접' 같은 기준을 바꾸려면 여기 숫자를 고치세요. */
function levelOf(supp, total, std){
  if(!std || (std.rda == null && std.ul == null)) return 'unknown';
  if(!(total > 0)) return 'none';
  const ulAmount = std.ulBasis === 'supp' ? supp : total;          // 상한 비교 대상
  if(std.ul != null && ulAmount > std.ul)       return 'over';
  if(std.ul != null && ulAmount >= std.ul * 0.7) return 'near';
  if(std.rda != null && total >= std.rda)        return 'met';
  return 'low';
}

/* -------------------------------------------------------------------------
   건강검진 — 별표 4 판정기준에 따라 항목마다 정상A / 경계 / 질환의심을 냅니다.
   ------------------------------------------------------------------------- */
function computeExam(state){
  const ctx = {sex: state.sex, age: Number(state.age)};
  const groups = EXAM.map(g => ({
    group: g.group,
    rows: g.items.map(it => ({
      key  : it.key,
      name : it.name,
      ref  : it.ref(ctx),
      value: it.show(state.exam, ctx),
      judge: it.judge(state.exam, ctx),
    })),
  }));
  const rows   = groups.flatMap(g => g.rows);
  const counts = {A:0, B:0, D:0};
  rows.forEach(r => { if(r.judge.code) counts[r.judge.code]++; });

  /* 별표 4 첫 표의 종합 판정 구분 */
  const dRows  = rows.filter(r => r.judge.code === 'D');
  const isMeta = dRows.some(r => HTN_DM_LIPID.includes(r.key));
  let overall;
  if(state.chronic.length)
    overall = {label:'유질환자', tone:'red',
      desc:`${state.chronic.join(' · ')} 진단 후 약물 치료 중으로 입력되었습니다.`};
  else if(isMeta)
    overall = {label:'고혈압·당뇨병·이상지질혈증 질환의심', tone:'red',
      desc:'해당 항목이 기준을 벗어나 진료와 검사가 필요합니다.'};
  else if(dRows.length)
    overall = {label:'일반 질환의심', tone:'red',
      desc:'추적검사나 전문 의료기관의 정확한 진단이 필요합니다.'};
  else if(counts.B)
    overall = {label:'정상B(경계)', tone:'orange',
      desc:'건강에 이상은 없으나 식생활습관 개선 등 자가관리가 필요합니다.'};
  else if(counts.A)
    overall = {label:'정상A', tone:'green', desc:'검진 결과 건강이 양호합니다.'};
  else
    overall = {label:'미입력', tone:'gray', desc:'검진 결과를 입력하면 종합 판정을 계산합니다.'};

  return {groups, rows, counts, overall,
          filled: counts.A + counts.B + counts.D,
          abnormal: rows.filter(r => r.judge.code === 'D' || r.judge.code === 'B')};
}

/* -------------------------------------------------------------------------
   자유 입력된 성분들을 하나로 모읍니다.
   같은 성분인지는 기준표의 별칭으로 판단하고, 기준표에 없으면
   사용자가 적은 표기를 그대로 key 로 씁니다(그 성분은 '확인 불가'가 됩니다).
   ------------------------------------------------------------------------- */
function computeNutrients(state){
  const bucket = {};   // key → 합산 상태

  /* [식사 기준 모드] 식사 평균 추정치로 계산하겠다고 켜 두었으면,
     사용자가 영양제를 넣지 않은 성분까지 기준표에서 미리 깔아 둡니다.
     이렇게 해야 '나는 이 성분을 아예 안 챙기고 있다'가 카드로 보이고,
     추천 목록에도 올라갈 수 있습니다.
     끄면 예전처럼 사용자가 적어 넣은 성분만 계산합니다. */
  if(state.countMeal){
    STD_LIST.forEach(std => {
      if(!std.meal || std.rda == null) return;      // 식사 추정치나 권장량이 없으면 비교할 수 없습니다
      bucket[std.name] = {
        std, key:std.name, label:std.name, unit:std.unit,
        supp:0, sources:[], unmapped:[],
      };
    });
  }

  state.products.forEach(p => {
    const pname = p.name || '이름 없는 제품';
    p.items.forEach(it => {
      if(!it.name) return;
      const std = findStd(it.name);
      const key = std ? std.name : normKey(it.name);
      const b = bucket[key] || (bucket[key] = {
        std, key,
        label   : std ? std.name : it.name.trim(),
        unit    : std ? std.unit : (it.unit in MASS ? 'mg' : it.unit),
        supp    : 0,
        sources : [],
        unmapped: [],          // 환산하지 못한 입력 (IU·mL·억CFU 등)
      });
      const v = convert(it.amount, it.unit, std);
      if(v == null) b.unmapped.push(`${pname}: ${it.amount || '?'}${it.unit}`);
      else          b.supp += v;
      if(!b.sources.includes(pname)) b.sources.push(pname);
    });
  });

  return Object.values(bucket).map(b => {
    const std   = b.std;
    const meal  = (state.countMeal && std && std.meal) ? std.meal : 0;
    const total = b.supp + meal;
    const level = levelOf(b.supp, total, std);
    const rda   = std ? std.rda : null;
    const ul    = std ? std.ul  : null;
    const ulSuppOnly = !!(std && std.ulBasis === 'supp');
    const ulAmount   = ulSuppOnly ? b.supp : total;

    /* ── 막대의 기준 길이 ──────────────────────────────────────────────────
       막대의 오른쪽 끝은 **상한이 아닙니다.** 상한을 끝에 두면 상한을 넘은
       값이 전부 막대 끝에 딱 붙어 버려서, 살짝 넘었는지 두 배로 넘었는지가
       구분되지 않습니다. 그래서 눈금 뒤에 항상 여유를 둡니다.

         0 ─────────┬──────────┬──────────── 끝
                   권장       상한      ← 상한 뒤에 남는 자리가 '초과분'

       아래 후보 중 가장 큰 값이 한 칸 전체가 됩니다.
         권장×1.6   권장만 있는 성분도 눈금이 가운데쯤 오도록
         상한×1.25  상한 뒤에 20% 정도 자리가 남도록
         섭취량×1.15 이미 크게 넘긴 값도 끝에 붙지 않고 다 보이도록
       ※ 서버(analyze.py)의 같은 계산과 반드시 똑같아야 합니다 —
         목업 화면과 실서버 화면이 다른 그림을 그리면 안 되니까요. */
    const scale = Math.max(...[
      (total || 0) * 1.15, (ulAmount || 0) * 1.15,
      rda != null ? rda * 1.6  : 0,
      ul  != null ? ul  * 1.25 : 0,
    ].filter(v => v > 0), 1) || 1;

    return {
      key:b.key, name:b.label, unit:b.unit, rda, ul, std,
      supp:b.supp, meal, total, level,
      /* 상한을 실제로 무엇과 비교했는지. 마그네슘·엽산처럼 영양제분만
         비교하는 성분은 total 이 아니라 supp 가 기준입니다. */
      ulAmount, ulSuppOnly,
      sources:b.sources, unmapped:b.unmapped,
      basis: !std ? '표준 기준 미등록'
           : (rda != null && ul != null) ? `권장 ${fmt(rda)} · 상한 ${fmt(ul)}${std.unit}${std.ulBasis === 'supp' ? ' (영양제 기준)' : ''}`
           : (ul  != null)               ? `상한 ${fmt(ul)}${std.unit}`
           : (rda != null)               ? `권장 ${fmt(rda)}${std.unit} 이상`
           : '기준 없음',
      bar: {
        supp   : Math.min(b.supp / scale, 1) * 100,
        meal   : Math.max(0, Math.min(meal / scale, 1 - b.supp / scale)) * 100,
        rdaMark: (rda != null && rda <= scale) ? rda / scale * 100 : null,
        /* 상한 눈금의 위치(%). 예전에는 화면이 늘 오른쪽 끝(100%)에
           그렸지만, 이제 끝이 상한이 아니므로 좌표를 함께 내려보냅니다. */
        ulMark : (ul  != null && ul  <= scale) ? ul  / scale * 100 : null,
      },
      pct: {
        rda: rda ? total / rda : (ul ? total / ul : null),
        ul : ul  ? ulAmount / ul : (rda ? total / rda : null),
      },
    };
  }).sort((a, b) =>
    /* 1순위 — 위험한 것부터 (상한 초과 → 근접 → 부족 → 적정) */
    (LEVEL[b.level].rank - LEVEL[a.level].rank) ||
    /* 2순위 — 같은 수준이면 사용자가 실제로 먹고 있는 성분을 앞에 */
    (b.sources.length - a.sources.length) ||
    /* 3순위 — 그래도 같으면 이름순으로 (순서가 매번 바뀌지 않게) */
    a.name.localeCompare(b.name, 'ko'));
}

/** 상호작용 · 중복 · 환산 실패를 점검 행으로 만듭니다. */
function computeIssues(state, nutrients){
  const out = [];

  nutrients.forEach(n => {
    if(n.level === 'over') out.push({kind:'상한 초과', tone:'red',
      text:`${n.name} ${n.ulSuppOnly ? '영양제 섭취량' : '합산량'} ${fmt(n.ulAmount)}${n.unit}이 상한 ${fmt(n.ul)}${n.unit}을 넘습니다. 제품 구성을 조정해 보세요.`});
    else if(n.level === 'near') out.push({kind:'상한 근접', tone:'orange',
      text:`${ga(n.name)} 상한의 70%를 넘었습니다. 같은 성분이 든 제품을 더하면 초과할 수 있습니다.`});
  });

  nutrients.forEach(n => {
    if(n.sources.length > 1) out.push({kind:'성분 중복', tone:'blue',
      text:`${ga(n.name)} ${n.sources.join(' · ')} 에 함께 들어 있습니다.`});
  });

  state.meds.forEach(m => MED_RULES.forEach(r => {
    const hit = r.med.some(k => normKey(m.name).includes(normKey(k)));
    if(hit && nutrients.some(n => n.name === r.nut))
      out.push({kind:r.kind, tone:r.tone, med:m.name, text:`${m.name} · ${r.text}`});
  }));

  nutrients.forEach(n => {
    if(n.unmapped.length) out.push({kind:'환산 불가', tone:'gray',
      text:`${n.name}의 ${n.unmapped.join(', ')} — 단위를 환산할 수 없어 합산에서 제외했습니다.`});
  });

  const unknown = nutrients.filter(n => !n.std).map(n => n.name);
  if(unknown.length) out.push({kind:'기준 미등록', tone:'gray',
    text:`${eun(unknown.join(', '))} 기준값이 등록되어 있지 않아 비율을 계산하지 못했습니다.`});

  return out;
}

/* -------------------------------------------------------------------------
   추천 영양제 — 무엇을 더 챙기면 좋을지 고릅니다.
   -------------------------------------------------------------------------
   ★ 여기 규칙은 '숫자로 설명되는 것'만 다룹니다.
       · 지금 섭취량(식사 + 영양제)이 권장량에 못 미치는 성분을 고릅니다.
       · 이미 충분하거나 상한에 가까운 성분은 뺍니다.
       · 복용 중인 약과 부딪히는 성분은 빼지 않고 '주의' 표시만 붙입니다.
         (임의로 빼 버리면 사용자가 이유를 알 수 없습니다.)

   ★ 일부러 하지 않은 것 —
     '혈압이 경계니까 이 성분을 드세요' 같은 검진 결과와 성분의 연결은
     임상 근거가 필요한 판단이라 목업에서 지어내지 않았습니다.
     검진 입력은 '함께 고려했다'는 표시와, 이상 소견이 있을 때
     전문가 상담 권고 문구로만 반영합니다.
     실제 서비스에서는 이 판단을 AI 백엔드가 하게 되며, 그 규칙은
     반드시 전문가 검토를 거쳐야 합니다. (규격서 7장 참고)
   ------------------------------------------------------------------------- */
function computeRecommend(state, nutrients, exam){
  const hasProducts = state.products.length > 0;

  /* 약 이름 안에 상호작용 규칙이 걸리는 성분을 미리 모아 둡니다 */
  const cautionOf = {};
  state.meds.forEach(m => MED_RULES.forEach(r => {
    if(r.med.some(k => normKey(m.name).includes(normKey(k))))
      (cautionOf[r.nut] = cautionOf[r.nut] || []).push(`${m.name} · ${r.kind}`);
  }));

  const shortfall = nutrients
    .filter(n => n.std && n.rda != null)
    .filter(n => n.level === 'low' || n.level === 'none');

  const items = shortfall
    .map(n => {
      const gap   = Math.max(0, n.rda - n.total);
      const ratio = n.rda ? n.total / n.rda : 0;
      const caution = cautionOf[n.name];
      return {
        name  : n.name,
        amount: `${fmt(gap)}${n.unit} 더`,
        reason: n.supp > 0
          ? `지금 ${fmt(n.total)}${n.unit}로 권장량의 ${Math.round(ratio * 100)}%입니다. 영양제를 함께 넣어도 모자랍니다.`
          : `식사 추정치로 ${fmt(n.total)}${n.unit}, 권장량 ${fmt(n.rda)}${n.unit}의 ${Math.round(ratio * 100)}%입니다.`,
        /* 많이 모자라면 주황, 조금 모자라면 파랑. 빨강은 쓰지 않습니다 —
           '부족'은 위험이 아니라 채울 여지이기 때문입니다. */
        tone   : ratio < 0.5 ? 'orange' : 'blue',
        caution: caution ? `복용 중인 ${caution[0]} — 시작 전 의사·약사와 상의하세요.` : '',
        _ratio : ratio,
      };
    })
    .sort((a, b) => a._ratio - b._ratio)     // 가장 많이 모자란 것부터
    .slice(0, 6);

  items.forEach(i => delete i._ratio);

  /* 무엇을 근거로 골랐는지 사용자에게 그대로 밝힙니다 */
  const basis = [];
  basis.push(state.countMeal ? '식사 평균 추정치' : '입력하신 영양제');
  if(hasProducts && state.countMeal) basis.push('복용 중인 영양제');
  if(state.meds.length)  basis.push(`복용 중인 약 ${state.meds.length}건`);
  if(exam.filled)        basis.push(`검진 ${exam.filled}개 항목`);

  const enough  = nutrients.filter(n => n.level === 'met').length;
  const basisKo = eul(basis.join(' · '));      /* 앞말 받침에 따라 을/를 을 고릅니다 */
  let desc;
  if(!items.length){
    desc = `${basisKo} 기준으로 보면 권장량에 못 미치는 성분이 없습니다.` +
           (enough ? ` ${enough}개 성분이 권장 범위 안에 있습니다.` : '');
  } else {
    desc = `${basisKo} 기준으로, 권장량에 못 미치는 성분을 모자란 순서로 골랐습니다.` +
           (hasProducts ? ' 이미 드시는 영양제로 채워지는 성분은 뺐습니다.' : '');
  }

  /* 검진에 이상 소견이 있으면 추천보다 상담이 먼저입니다 */
  const advice = exam.abnormal && exam.abnormal.length
    ? `건강검진에서 ${exam.abnormal.length}개 항목이 기준을 벗어났습니다. 영양제를 고르기 전에 의사·약사와 상의하시기를 권합니다.`
    : '';

  /* 상위 6개만 보여주므로, 나머지가 있으면 그 사실을 밝힙니다.
     밝히지 않으면 '부족한 건 이 6개뿐'으로 읽힙니다. */
  const more = Math.max(0, shortfall.length - items.length);

  return {
    title: items.length ? '이런 성분을 더 챙겨 보세요' : '지금은 더 챙길 성분이 없습니다',
    desc, items, advice, more,
    moreText: more
      ? `이 밖에 ${more}개 성분도 권장량에 못 미칩니다. 아래 섭취량 카드에서 모두 확인하실 수 있습니다.`
      : '',
    note: '권장섭취량에 견준 계산 결과일 뿐, 특정 제품이나 복용을 권하는 것이 아닙니다. ' +
          '복용을 시작하기 전에 의사·약사와 상의하세요.',
  };
}

function buildModel(state){
  const exam      = computeExam(state);
  const nutrients = computeNutrients(state);
  const issues    = computeIssues(state, nutrients);
  const recommend = computeRecommend(state, nutrients, exam);
  const worst     = nutrients.reduce((m, n) => LEVEL[n.level].rank > LEVEL[m].rank ? n.level : m, 'met');
  return {
    state, exam, nutrients, issues, recommend, worst,
    hasSupp   : nutrients.length > 0,
    mealOnly  : state.products.length === 0,   /* 영양제 없이 식사 기준만으로 본 결과인지 */
    cols      : Math.min(Math.max(nutrients.length, 1), LAYOUT.maxCols),
  };
}


/* -------------------------------------------------------------------------
   목업 구현 — [D] 의 API 가 부르는 네 가지
   ------------------------------------------------------------------------- */
const MOCK = {

  /* 성분 이름 추천 목록. 실제로는 서버가 성분 사전을 내려줍니다. */
  async bootstrap(){
    await nap(150);
    return {nutHints: STD_LIST.map(s => s.name)};
  },

  /* 저장소 흉내. 실제로는 로그인한 사용자별로 서버 DB 에 들어갑니다.
     새로고침하면 사라지는 게 정상입니다(목업이라서 — 아래 세션도 같은
     이유로 새로고침하면 로그아웃됩니다). */
  _draft: null,
  async loadDraft(){
    await nap(120);
    if(!MOCK._session) throw new ApiError('LOGIN_REQUIRED', '로그인이 필요합니다.');
    return MOCK._draft;
  },
  async saveDraft(input){
    await nap(220);
    if(!MOCK._session) throw new ApiError('LOGIN_REQUIRED', '로그인이 필요합니다.');
    MOCK._draft = JSON.parse(JSON.stringify(input));
    return {savedAt: new Date().toISOString()};
  },

  /* ★ 판정. 실제로는 서버의 AI 가 합니다.
     일부러 1~2초 기다립니다 — '분석 중' 화면이 제대로 보이는지
     확인하기 위해서입니다. 실제 AI 응답도 이 정도는 걸립니다. */
  async analyze(input){
    await nap(1300 + Math.random() * 900);
    /* 로그인해야만 쓸 수 있는 서비스이므로, 분석 도중 로그인이 풀렸다면
       (세션 만료 등) 여기서도 다른 API 처럼 LOGIN_REQUIRED 를 돌려줘야
       합니다. 화면은 이 경우 입력을 지우지 않고 재로그인 모달만 다시
       띄운 뒤, 로그인에 성공하면 이 요청을 그대로 다시 보냅니다. */
    if(!MOCK._session) throw new ApiError('LOGIN_REQUIRED', '로그인이 필요합니다.');
    const report = toReport(input);
    /* 실제 서비스에서는 서버가 판정 결과를 자동으로 이력에 남깁니다.
       목업에서도 같은 동작을 흉내 냅니다 — 그래야 '지난 리포트'에 쌓입니다. */
    const id = 'r' + Date.now() + Math.random().toString(36).slice(2, 7);
    MOCK._reports.unshift({id, createdAt:new Date().toISOString(), report});
    return report;
  },

  /* -------------------------------------------------------------------------
     인증 — 이메일·비밀번호로 가입/로그인하는 가장 단순한 형태만 흉내 냅니다.
     소셜 로그인이 필요하면 모달에 버튼만 추가하고, 이 자리에 같은 모양
     ({name, email} 반환)의 메서드를 더 추가하면 됩니다.
     ------------------------------------------------------------------------- */
  _session: null,           // {name, email} | null
  _users: new Map(),        // email(정규화) → {name, email, password}
  _norm(email){ return String(email || '').trim().toLowerCase(); },

  async me(){
    await nap(150);
    if(!MOCK._session) throw new ApiError('LOGIN_REQUIRED', '로그인이 필요합니다.');
    return MOCK._session;
  },

  async login(email, password){
    await nap(500);
    const rec = MOCK._users.get(MOCK._norm(email));
    if(!rec || rec.password !== password)
      throw new ApiError('INVALID_CREDENTIALS', '이메일 또는 비밀번호가 올바르지 않습니다.');
    MOCK._session = {name:rec.name, email:rec.email};
    return MOCK._session;
  },

  async signup(name, email, password){
    await nap(500);
    const key = MOCK._norm(email);
    if(!name || !name.trim())        throw new ApiError('INVALID_INPUT', '이름을 입력해 주세요.');
    if(!key || !key.includes('@'))   throw new ApiError('INVALID_INPUT', '올바른 이메일을 입력해 주세요.');
    if(!password || password.length < 4)
      throw new ApiError('INVALID_INPUT', '비밀번호는 4자 이상으로 입력해 주세요.');
    if(MOCK._users.has(key))         throw new ApiError('EMAIL_TAKEN', '이미 가입된 이메일입니다.');
    MOCK._users.set(key, {name:name.trim(), email:key, password});
    MOCK._session = {name:name.trim(), email:key};
    return MOCK._session;
  },

  async logout(){
    await nap(150);
    MOCK._session = null;
    MOCK._draft   = null;   // 실제 서비스에서는 서버에 남아 있고, 목업은 세션과 함께 지웁니다
    return {};
  },

  /* -------------------------------------------------------------------------
     지난 리포트 — analyze() 가 성공할 때마다 여기 쌓입니다.
     ------------------------------------------------------------------------- */
  _reports: [],   // [{id, createdAt, report}], 최신순

  async listReports(){
    await nap(300);
    if(!MOCK._session) throw new ApiError('LOGIN_REQUIRED', '로그인이 필요합니다.');
    return {reports: MOCK._reports.map(r => ({
      id: r.id,
      createdAt: r.createdAt,
      summaryLine: `${(r.report.badges && r.report.badges[0] && r.report.badges[0].text) || '리포트'} · 성분 ${r.report.nutrients.length}개`,
      worst: r.report.worst,
      badges: r.report.badges,
      info: mockReportInfo(r.report),
    }))};
  },

  async getReport(id){
    await nap(250);
    if(!MOCK._session) throw new ApiError('LOGIN_REQUIRED', '로그인이 필요합니다.');
    const rec = MOCK._reports.find(r => r.id === id);
    if(!rec) throw new ApiError('HTTP_404', '리포트를 찾을 수 없습니다.');
    return rec.report;
  },

  async deleteReport(id){
    await nap(200);
    if(!MOCK._session) throw new ApiError('LOGIN_REQUIRED', '로그인이 필요합니다.');
    const i = MOCK._reports.findIndex(r => r.id === id);
    if(i < 0) throw new ApiError('HTTP_404', '리포트를 찾을 수 없습니다.');
    MOCK._reports.splice(i, 1);
    return {deleted:id, remaining: MOCK._reports.length};
  },

  /* ★ 검진표 사진 판독. 실제로는 서버의 비전 모델이 합니다(vision.py).
     목업은 사진 내용의 해시로 견본 넷 중 하나를 고릅니다 — 무작위가 아니라
     해시라서, 같은 사진은 늘 같은 결과가 나옵니다. */
  async readExamImage(file){
    if(!MOCK._session) throw new ApiError('LOGIN_REQUIRED', '로그인이 필요합니다.');
    const buf = new Uint8Array(await file.arrayBuffer());
    if(!sniffImage(buf))
      throw new ApiError('HTTP_400', '이미지 파일만 올릴 수 있습니다. (PNG · JPG · GIF · WEBP · HEIC)');
    if(buf.length > MAX_IMAGE_BYTES)
      throw new ApiError('HTTP_400', `이미지가 너무 큽니다. ${MAX_IMAGE_BYTES / 1048576}MB 이하로 올려 주세요.`);
    await nap(1100 + Math.random() * 700);      // 판독에 걸리는 시간 흉내
    let h = 0;
    for(let i = 0; i < buf.length; i += 997) h = (h * 31 + buf[i]) >>> 0;
    return {...cleanExamReading(DEMO_SHEETS[h % DEMO_SHEETS.length]), source:'demo'};
  },
};

/* -------------------------------------------------------------------------
   검진표 판독 — 목업용 (실제로는 vision.py 가 같은 일을 합니다)
   ※ 크기 제한 MAX_IMAGE_BYTES 는 이 블록 밖(대화형 입력 쪽)에 있습니다.
     화면이 파일을 고른 순간에도 쓰는 값이라, 목업이 빠진 실서버용
     파일에도 남아 있어야 하기 때문입니다.
   ------------------------------------------------------------------------- */

/** 확장자나 브라우저가 알려 준 형식은 믿지 않고, 파일 앞머리의 고정된
    바이트(매직 넘버)로 직접 확인합니다. 둘 다 마음대로 적어 보낼 수 있으니까요. */
function sniffImage(b){
  const at = (i, ...sig) => sig.every((v, k) => b[i + k] === v);
  if(b.length < 12) return null;
  if(at(0, 0x89, 0x50, 0x4E, 0x47)) return 'image/png';
  if(at(0, 0xFF, 0xD8, 0xFF))       return 'image/jpeg';
  if(at(0, 0x47, 0x49, 0x46, 0x38)) return 'image/gif';
  if(at(0, 0x52, 0x49, 0x46, 0x46) && at(8, 0x57, 0x45, 0x42, 0x50)) return 'image/webp';
  if(at(0, 0x42, 0x4D))             return 'image/bmp';
  if(at(4, 0x66, 0x74, 0x79, 0x70)) return 'image/heic';
  return null;
}

/* 실제 검진 결과지에 흔히 있는 조합 넷. 채워지는 검진 그룹이 서로 달라서,
   어떤 사진을 올리느냐에 따라 '남은 질문'도 달라집니다. */
const DEMO_SHEETS = [
  {name:'홍길동', age:'45', sex:'남성', date:'2026-03-10', chronic:[],
   exam:{sbp:'132', dbp:'84', height:'175', weight:'88', waist:'94', hb:'15.1', glu:'108',
         tc:'226', hdl:'42', tg:'189', ldl:'146', ast:'38', alt:'45', ggt:'71',
         upro:'음성(-)', cr:'1.0', egfr:'88'}},
  {name:'김영자', age:'68', sex:'여성', date:'2025-11-18', chronic:['고혈압'],
   exam:{cxr:'정상', sbp:'148', dbp:'88', height:'156', weight:'52', waist:'82', hb:'11.4',
         glu:'132', tc:'210', hdl:'55', tg:'143', ldl:'128', ast:'26', alt:'22', ggt:'28',
         upro:'약양성(±)', cr:'1.1', egfr:'58', tscore:'-2.7', bmd:'78'}},
  {name:'이수민', age:'34', sex:'여성', date:'2026-01-07', chronic:[],
   exam:{cxr:'정상', sbp:'112', dbp:'71', height:'163', weight:'54', waist:'71', hb:'12.8',
         glu:'88', tc:'178', hdl:'68', tg:'82', ldl:'96', ast:'18', alt:'15', ggt:'14',
         upro:'음성(-)', cr:'0.7', egfr:'104'}},
  {name:'박정호', age:'57', sex:'남성', date:'2025-09-02', chronic:['이상지질혈증'],
   exam:{cxr:'비활동성 폐결핵', sbp:'126', dbp:'79', height:'171', weight:'79', waist:'91',
         hb:'14.6', glu:'97', tc:'188', hdl:'47', tg:'168', ldl:'112', ast:'62', alt:'58',
         ggt:'96', upro:'음성(-)', cr:'1.2', egfr:'76', ratio:'68', fev1:'74', fvc:'89'}},
];

/** 판독 결과를 화면이 아는 모양으로 다듬습니다. 모델이 엉뚱한 key 나 말도
    안 되는 값을 뱉어도 그대로 입력에 들어가면 안 되므로, 견본이든 모델이든
    반드시 이 함수를 지나갑니다. */
function cleanExamReading(raw){
  raw = raw || {};
  const exam = {};
  EXAM.forEach(g => g.items.forEach(it => it.inputs.forEach(inp => {
    const v = (raw.exam || {})[inp.key];
    if(v == null || v === '') return;
    if(inp.type === 'select'){
      if((inp.options || []).includes(String(v))) exam[inp.key] = String(v);
      return;
    }
    if(!Number.isNaN(Number(v))) exam[inp.key] = String(v).trim();
  })));

  const sex = ['남성', '여성'].includes(raw.sex) ? raw.sex : '';
  const groups = EXAM.filter(g => g.items.some(it => it.inputs.some(inp => inp.key in exam)))
                     .map(g => g.group);
  const fields = [];
  EXAM.forEach(g => g.items.forEach(it => {
    if(!it.inputs.some(inp => inp.key in exam)) return;
    fields.push({group:g.group, name:it.name, text: it.show(exam, {sex})});
  }));

  return {
    name: String(raw.name || '').trim().slice(0, 40),
    age : String(raw.age || '').trim(),
    sex,
    date: String(raw.date || '').trim().slice(0, 40),
    exam, chronic: (raw.chronic || []).filter(c => CHRONIC.includes(c)),
    groups, fields,
  };
}

/** 목록 카드에 '무엇을 넣고 뽑은 리포트인지' 보여 주기 위한 요약.
    (실제로는 서버가 analyze.py 의 report_info() 로 만들어 내려줍니다) */
function mockReportInfo(report){
  const s = report.input || {};
  const products = s.products || [], meds = s.meds || [], exam = s.exam || {};
  return {
    name: s.name || '', age: s.age || '', sex: s.sex || '', date: s.date || '',
    countMeal: !!s.countMeal, chronic: s.chronic || [],
    products: products.map(p => p.name || '이름 없는 제품').slice(0, 3),
    productCount: products.length,
    meds: meds.map(m => m.name).filter(Boolean).slice(0, 3),
    medCount: meds.length,
    examCount: Object.values(exam).filter(v => v !== '' && v != null).length,
    examOverall: ((report.exam || {}).overall || {}).label || '',
    nutrientCount: (report.nutrients || []).length,
  };
}

/* -------------------------------------------------------------------------
   계산 결과를 화면이 쓰는 형태(Report)로 포장합니다.
   ★ 이 함수가 만들어 내는 모양이 곧 백엔드가 지켜야 할 응답 형식입니다.
     규격서의 'Report' 항목과 같습니다.
   ------------------------------------------------------------------------- */
function toReport(input){
  const m = buildModel(input);

  /* 성분 카드 아래 코멘트. 실제 서비스에서는 AI 가 쓴 문장이 옵니다. */
  const noteOf = n => ({
    over : {title:'상한 초과.',
            body:`${n.ulSuppOnly ? '영양제로만 ' : ''}${fmt(n.ulAmount)}${n.unit}, 상한 ${fmt(n.ul)}${n.unit}을 넘었습니다. 제품 수를 줄이거나 함량이 낮은 제품으로 바꿔 보세요.`},
    near : {title:'상한 근접.', body:'여기에 같은 성분이 든 제품을 더하면 초과할 수 있습니다.'},
    met  : {title:'충분합니다.', body:'현재 구성을 유지해도 괜찮습니다.'},
    low  : n.sources.length
             ? {title:'권장량에 못 미칩니다.', body:'식사에서 보충하거나 제품의 함량을 확인해 보세요.'}
             : {title:'식사만으로는 모자랍니다.', body:`권장량 ${fmt(n.rda)}${n.unit}까지 ${fmt(Math.max(0, n.rda - n.total))}${n.unit}이 부족합니다. 위의 추천을 참고해 보세요.`},
    none : {title:'섭취량이 없습니다.', body:'등록한 제품에 이 성분이 들어 있지 않습니다.'},
    unknown: {title:'기준값이 없습니다.',
              body: n.unmapped.length
                ? `${n.unmapped.join(', ')} — 이 단위는 환산 규칙이 없어 합산하지 않았습니다.`
                : '기준표에 없는 성분이라 합산량만 표시합니다.'},
  }[n.level]);

  /* 카드 위 작은 캡션 — 어느 제품에서 얼마씩 왔는지 */
  const captionOf = n => {
    /* 제품에서 온 성분이면 제품 이름부터, 식사 추정치만이면 그 사실을 밝힙니다 */
    if(!n.sources.length) return `식사 평균 추정 ${fmt(n.meal)}${n.unit} · 등록한 제품 없음`;
    return n.sources.join(' · ') +
      (n.supp > 0 ? ` · 영양제 ${fmt(n.supp)}${n.unit}` : '') +
      (n.meal    ? ` + 식사 ${fmt(n.meal)}${n.unit}`   : '');
  };

  const nutrients = m.nutrients.map(n => ({
    key:n.key, name:n.name, unit:n.unit, level:n.level,
    supp:n.supp, meal:n.meal, total:n.total,
    rda:n.rda, ul:n.ul,
    hasStd    : !!n.std,          /* 기준값이 등록된 성분인지 (std 객체를 넘기지 않습니다) */
    ulSuppOnly: n.ulSuppOnly,
    ulAmount  : n.ulAmount,
    sources   : n.sources,
    unmapped  : n.unmapped,
    basis     : n.basis,
    bar       : n.bar,
    gauge     : n.pct,            /* {rda, ul} — 각 탭의 게이지 비율 */
    caption   : captionOf(n),
    note      : noteOf(n),
  }));

  /* 종합 소견 문장. 실제 서비스에서는 AI 가 통째로 써서 내려줍니다. */
  const pick  = lv => nutrients.filter(n => lv.includes(n.level));
  const over  = pick(['over']), near = pick(['near']),
        low   = pick(['low','none']), met = pick(['met']);
  const names = list => {
    const a = list.map(x => x.name);
    return a.length > 3 ? `${a.slice(0, 3).join(', ')} 외 ${a.length - 3}개` : a.join(', ');
  };

  const examLine = m.exam.filled ? `건강검진 종합 판정은 '${m.exam.overall.label}' 입니다. ` : '';
  let text;
  if(!m.hasSupp){
    text = examLine + '계산할 성분이 없습니다. 영양제를 넣거나 식사 평균 추정치 계산을 켜 주세요.';
  } else {
    /* 영양제를 넣었는지 아닌지에 따라 첫 문장이 달라집니다 */
    const parts = [m.mealOnly
      ? `식사 평균 추정치를 기준으로 ${nutrients.length}개 성분을 살펴봤습니다.`
      : `등록한 ${input.products.length}개 제품${input.countMeal ? '과 식사 평균 추정치' : ''}에서 ${nutrients.length}개 성분을 확인했습니다.`];
    if(over.length) parts.push(`${eun(names(over))} 상한을 넘어 조정이 필요합니다.`);
    if(near.length) parts.push(`${eun(names(near))} 상한에 가까워 추가 섭취에 주의가 필요합니다.`);
    if(low.length)  parts.push(`${eun(names(low))} 권장량에 미치지 못합니다.`);
    if(met.length)  parts.push(`나머지 ${met.length}개 성분은 권장 범위 안에 있습니다.`);
    if(m.issues.length) parts.push(`점검에서 ${m.issues.length}건이 확인됐습니다.`);
    text = examLine + parts.join(' ');
  }

  const chips = [];
  if(over.length) chips.push({text:`상한 초과 ${over.length}`, tone:'red'});
  if(near.length) chips.push({text:`상한 근접 ${near.length}`, tone:'orange'});
  if(met.length)  chips.push({text:`적정 ${met.length}`,      tone:'green'});
  if(low.length)  chips.push({text:`부족 ${low.length}`,      tone:'blue'});
  if(!chips.length) chips.push({text:'데이터 없음', tone:'gray'});

  /* 헤더 요약 배지 */
  const badges = [];
  if(m.exam.filled)        badges.push({text:m.exam.overall.label, tone:m.exam.overall.tone});
  if(input.meds.length)    badges.push({text:`복약 ${input.meds.length}건`,     tone:'orange'});
  if(input.products.length)badges.push({text:`영양제 ${input.products.length}종`, tone:'green'});
  else if(m.hasSupp)       badges.push({text:'식사 기준', tone:'gray'});
  if(m.worst === 'over')   badges.push({text:'성분 상한 초과', tone:'red'});
  if(m.recommend.items.length) badges.push({text:`보충 권장 ${m.recommend.items.length}`, tone:'blue'});
  if(!badges.length)       badges.push({text:'입력 대기', tone:'gray'});

  return {
    meta: {
      generatedAt: new Date().toISOString(),
      source     : 'mock',
      engine     : '브라우저 임시 계산 (예시 기준값)',
    },
    input,
    hasSupp : m.hasSupp,
    mealOnly: m.mealOnly,
    cols    : m.cols,
    worst   : m.worst,
    badges,
    exam    : m.exam,
    nutrients,
    issues  : m.issues,
    recommend: m.recommend,
    summary : {text, chips},
  };
}

/* ###########################################################################
   ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲  [E] 목업 블록 — 끝  ▲▲▲▲▲▲▲▲▲▲▲▲▲▲▲
   ########################################################################### */



/* =========================================================================
   4. 렌더 — 모델을 받아 HTML 문자열을 만듭니다. 여기서는 계산하지 않습니다.
      블록 하나당 함수 하나. 원본 3개 파일의 마크업을 그대로 재현합니다.
   ========================================================================= */

/* ---- [블록 1] 프로필 헤더 ------------------------------------------------ */
function renderHeader(m){
  const s = m.input;
  const ex = m.exam;

  /* 요약 배지는 서버(Report.badges)가 정합니다. 화면은 색만 입힙니다. */
  const tags = (m.badges || []).map(b => chip(b.text, b.tone));

  /* 검진 결과 열 — 종합 판정과 눈에 띄는 항목만. 전체 표는 아래에 있습니다. */
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
              <span class="row-d">${esc(r.value)} · 기준 ${r.ref}</span></div>
            ${tag(r.judge.text, r.judge.tone)}
          </div>`).join('')}
         ${ex.abnormal.length > 3
            ? `<div class="row"><div class="row-l"><span class="row-d">이 밖에 ${ex.abnormal.length - 3}개 항목이 기준을 벗어났습니다.</span></div></div>`
            : ''}
       </div>`;

  /* 검진 결과 전체 표 — 입력된 항목만 목표질환별로 묶어 보여 줍니다. */
  const filledGroups = ex.groups
    .map(g => ({...g, rows: g.rows.filter(r => r.judge.code)}))
    .filter(g => g.rows.length);
  const blank = ex.rows.length - ex.filled;
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
            <span class="rf">${r.ref}</span>
            <span class="right">${tag(r.judge.text, r.judge.tone)}</span>
          </div>`).join('')).join('')}
      </div>
      ${blank ? `<div class="note-s" style="padding-top:8px">미입력 ${blank}개 항목은 표시하지 않았습니다.</div>` : ''}
    </details>`;

  /* 복약 정보 열 */
  const medsCol = !s.meds.length
    ? emptyCard('등록된 약이 없습니다',
                '복용 중인 약을 입력하면 영양제와의 상호작용을 함께 점검합니다.')
    : `<div class="rows">${s.meds.map(md => {
         /* 어떤 경고가 어느 약에서 나왔는지는 서버가 issue.med 로 알려 줍니다.
            (예전에는 문구 앞글자를 비교했는데, 문장이 조금만 바뀌어도
             연결이 끊어져서 규격에 필드를 하나 두었습니다.) */
         const hits = m.issues.filter(i => i.med && i.med === md.name);
         return `<div class="row">
           <div class="row-l"><span class="row-t">${esc(md.name)}</span>
             <span class="row-d">${esc(md.desc || '설명 없음')}</span></div>
           ${hits.length ? tag(`주의 ${hits.length}건`, hits.some(h => h.tone === 'red') ? 'red' : 'orange')
                         : tag('점검 완료', 'gray')}
         </div>`;
       }).join('')}</div>`;

  /* 등록한 영양제 열 */
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
        <div class="avatar">${esc((s.name || '?').trim().charAt(0))}</div>
        <div class="hd-info">
          <div class="hd-name">
            <span class="nm">${esc(s.name || '이름 미입력')}</span>
            <span class="mt">${esc(s.age || '—')}세 · ${esc(s.sex)} · ${esc(s.date)}</span>
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
  const lv = LEVEL[n.level], t = TONE[lv.tone];

  /* 게이지 — 권장량 대비 몇 %인지 하나만 보여 줍니다.
     상한을 넘었는지는 아래 막대에서 눈금을 지나쳤는지로 바로 보이므로,
     같은 이야기를 게이지로 한 번 더 할 필요가 없습니다. */
  const pct = n.gauge.rda;
  let label = '—', arc = 0;
  const arcColor = t.fg;
  if(pct != null && n.level !== 'unknown'){
    label = Math.round(pct * 100) + '%';
    arc   = LAYOUT.gaugeArc * Math.min(pct, 1);   // 100%를 넘어도 반원은 꽉 찬 데까지만
  }
  const track = `<path d="M8,60 A52,52 0 0 1 112,60" fill="none" stroke="#EEF0F3" stroke-width="12" stroke-linecap="round"/>`;
  const fill  = arc > 0
    ? `<path d="M8,60 A52,52 0 0 1 112,60" fill="none" stroke="${arcColor}" stroke-width="12" stroke-linecap="round" stroke-dasharray="${arc.toFixed(1)} 200"/>`
    : '';

  /* ── 막대 ────────────────────────────────────────────────────────────────
     오른쪽 끝은 **상한이 아닙니다.** 상한 눈금 뒤에 자리가 남아 있어서,
     상한을 넘은 값도 '얼마나 넘었는지'가 그대로 보입니다.

        │████████████│░░░░│      │
        0           권장  상한   끝            ← 넘으면 눈금을 지나쳐 뻗습니다

     예전에는 상한을 넘으면 막대를 통째로 빨갛게 채웠는데, 그러면 살짝
     넘은 것과 두 배로 넘은 것이 똑같아 보였습니다. */
  const over = n.level === 'over';
  const bar = `<div class="bar">
         <div style="width:${n.bar.supp.toFixed(2)}%;background:${over ? TONE.crit.fg : '#1E3A8A'}"></div>
         <div style="width:${n.bar.meal.toFixed(2)}%;background:${over ? '#F3B4B4' : '#D8DBE0'}"></div>
       </div>`;

  const rm = n.bar.rdaMark, um = (n.hasStd && n.ul != null) ? n.bar.ulMark : null;
  const mark = (pos, kind, text) => pos == null ? '' :
    `<i class="mk mk-${kind}" style="left:${pos.toFixed(2)}%"></i>` +
    (text ? `<b class="mkl mkl-${kind}" style="left:${pos.toFixed(2)}%">${text}</b>` : '');

  /* 마그네슘처럼 권장량과 상한이 같은 성분은 두 눈금이 포개집니다.
     그때는 글자를 하나로 합쳐 적습니다 — 겹쳐 쓰면 둘 다 못 읽습니다. */
  const merged = rm != null && um != null && Math.abs(um - rm) < 9;
  const marks = merged
    ? mark(rm, 'rda', '') + mark(um, 'ul', '권장·상한')
    : mark(rm, 'rda', '권장') + mark(um, 'ul', '상한');

  /* 캡션과 코멘트는 서버가 써서 내려줍니다(실서비스에서는 AI 가 쓴 문장).
     혹시 비어 있어도 카드가 깨지지 않도록 기본값을 둡니다. */
  const cap  = n.caption || n.sources.join(' · ');
  const note = n.note || {title:'', body:''};

  /* 제품에서 온 성분이면 '2개 제품', 식사 추정치만인 성분이면 '식사 추정'. */
  const srcTag = n.sources.length
    ? tag(`${n.sources.length}개 제품`, lv.tone)
    : tag('식사 추정', 'gray');

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
  /* 영양제를 넣었는지에 따라 제목과 설명이 달라집니다.
     식사 기준만으로 본 결과인데 '내 섭취량'이라고 하면 오해를 부릅니다. */
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

  /* 방어용 — 정상 흐름에서는 입력 화면에서 막히므로 여기에 오지 않습니다. */
  if(!m.hasSupp){
    return `<section class="intake">${head}
      <div class="pane always">${emptyCard('계산할 섭취량이 없습니다',
        '영양제를 입력하거나 식사 평균 추정치 계산을 켜면 이 자리에 표시됩니다.',
        '입력 수정하기', true, 'products')}</div>
    </section>`;
  }

  /* (B) 성분 카드 — 한 화면입니다.
     예전에는 '권장 대비'와 '상한 대비' 탭이 따로 있었는데, 권장량과 상한은
     한 눈금자 위의 두 지점일 뿐이라 굳이 나눌 이유가 없었습니다. 오히려
     탭을 오갈 때마다 같은 카드의 숫자만 바뀌어서, 지금 보는 게 어느
     기준인지 헷갈렸습니다. 이제 막대 하나에 권장·상한 눈금이 함께
     찍히므로 한 번에 다 읽힙니다. */
  return `<section class="intake">${head}
  <div class="pane always">
    <div class="grid" data-cols="${m.cols}">${m.nutrients.map(renderCard).join('')}</div>
  </div>
</section>`;
}

/* ---- [블록 2-B] 추천 영양제 ----------------------------------------------
   서버가 준 recommend 를 그대로 그립니다. 무엇을 추천할지는 서버가 정합니다.
   recommend 가 아예 없으면(구버전 응답 등) 이 블록은 나오지 않습니다.        */
function renderRecommend(m){
  const r = m.recommend;
  if(!r) return '';

  const body = r.items && r.items.length
    ? `<div class="rc-grid">${r.items.map(it => {
        const t = TONE[it.tone] || TONE.gray;
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
    ? m.issues.map(i => `<div class="ix-row">
        <span class="ix-kind" style="background:${TONE[i.tone].bg};color:${TONE[i.tone].fg}">${esc(i.kind)}</span>
        <span class="ix-text">${esc(i.text)}</span>
      </div>`).join('')
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
  /* 소견 문장과 핵심 배지는 서버가 통째로 내려줍니다.
     실서비스에서는 AI 가 쓴 문장이 그대로 여기에 들어옵니다.
     화면은 문장을 만들지 않고 받아서 그리기만 합니다. */
  const sum   = m.summary || {text:'', chips:[]};
  const chips = (sum.chips && sum.chips.length ? sum.chips : [{text:'데이터 없음', tone:'gray'}])
                  .map(c => bigchip(c.text, c.tone));

  return `<section class="card sm">
    <span class="h3">종합 소견</span>
    <p class="sm-text">${esc(sum.text)}</p>
    <div class="sm-keys"><span class="sm-keys-l">핵심</span><div class="sm-keys-r">${chips.join('')}</div></div>
  </section>`;
}

/* ---- [블록 5] 푸터 ------------------------------------------------------- */
const renderFooter = () => `<footer class="ft">
  ${API.source === 'mock'
    ? '<p>이 화면의 기준값과 상호작용 규칙은 검증되지 않은 예시입니다. 실제 판단에 사용하지 마세요.</p>'
    : ''}
  <p>이 리포트는 입력하신 내용을 바탕으로 한 참고 자료이며, 진단이나 처방이 아닙니다.
     건강 상태나 복약에 대한 판단은 반드시 의사·약사와 상의하시기 바랍니다.</p>
</footer>`;

/* ---- 알림 띠 ------------------------------------------------------------- */

/** 목업으로 도는 중이라는 경고. 실서비스(USE_MOCK=false)에서는 나오지 않습니다. */
const mockBanner = () => API.source !== 'mock' ? '' :
  `<div class="banner warn">
     <span><b>예시 기준값으로 계산 중입니다.</b>
       성분 기준값과 상호작용 규칙이 아직 검증되지 않았습니다. 실제 판단에 사용하지 마세요.</span>
   </div>`;

/** 샘플 리포트를 보고 있을 때 뜨는 띠 */
const sampleBanner = () =>
  `<div class="banner info">
     <span><b>샘플 리포트입니다.</b> 예시로 만든 가상의 입력으로 만든 화면입니다.</span>
     <button type="button" class="btn-line" data-act="fresh">내 정보로 시작하기</button>
   </div>`;

/* ---- 전체 조립 ----------------------------------------------------------- */
const renderReport = m =>
  `<div class="page">
    ${UI.sample ? sampleBanner() : mockBanner()}
    <div class="rp-top">
      <div><span class="h2">영양제 섭취 리포트</span>
        <span class="sub" style="display:block">${esc(m.input.date || '')} 기준 · 입력하신 내용으로 분석했습니다.</span></div>
      <div class="rp-acts">
        <button type="button" class="btn-line" data-act="print">인쇄 · PDF 저장</button>
        <button type="button" class="rp-back" data-act="edit">입력 수정</button>
      </div>
    </div>
    ${renderHeader(m)}${renderRecommend(m)}${renderIntake(m)}${renderIssues(m)}${renderSummary(m)}${renderFooter()}</div>`;

/** 결과 화면 하나를 고릅니다.
    -------------------------------------------------------------------------
    서버가 완성된 HTML(m.html)을 보내 주면 그것을 그대로 씁니다 — 판정도
    문장도 전부 서버가 만든 것이므로 화면은 손대지 않습니다. html 이 없으면
    예전처럼 이 화면이 직접 그립니다(목업으로 볼 때가 그렇습니다).

    위아래의 '인쇄 · 입력 수정' 줄은 어느 쪽이든 붙입니다. 이게 없으면
    결과를 본 뒤 돌아갈 방법이 사라집니다. */
/** 분석 서버가 보지 못한 입력이 있는지.
    -------------------------------------------------------------------------
    결과보기는 분석 서버가 처리하는데, 그 서버는 나이·성별·체중·이름만
    받습니다. 영양제·복용 약·건강검진 수치는 넘길 자리가 아예 없어서
    그쪽 리포트에는 반영되지 않습니다.

    그런데 그 입력들에 대한 판정은 이 응답 안에 이미 함께 들어 있습니다
    (서버가 같은 요청에서 계산해 둡니다). 그냥 버리면 사용자는 와파린과
    오메가3를 같이 적어 놓고도 출혈 주의 안내를 못 보게 됩니다 —
    '경고가 없다'로 읽히는 쪽이 위험합니다. 그래서 아래에 따로 붙입니다. */
function serverMissedInput(m){
  const issues = (m.issues || []).length;
  const flagged = (m.nutrients || []).filter(n => n.level === 'over' || n.level === 'near').length;
  const abnormal = ((m.exam || {}).abnormal || []).length;
  return {issues, flagged, abnormal, any: issues + flagged + abnormal > 0};
}

const reportHtml = m => {
  if(!m || !m.html) return renderReport(m);

  const missed = serverMissedInput(m);
  const extra = !missed.any ? '' : `
    <div class="rp-extra-head">
      <span class="h3">입력하신 영양제 · 약 · 검진 결과로 확인한 내용</span>
      <span class="sub">위 리포트에는 포함되지 않은 항목입니다.
        ${missed.issues ? `점검 ${missed.issues}건 · ` : ''}${missed.flagged ? `주의 성분 ${missed.flagged}개 · ` : ''}${missed.abnormal ? `검진 이상 ${missed.abnormal}건` : ''}</span>
    </div>
    ${missed.issues ? renderIssues(m) : ''}
    ${missed.flagged ? renderIntake(m) : ''}`;

  return `<div class="page">
    ${UI.sample ? sampleBanner() : mockBanner()}
    <div class="rp-top">
      <div><span class="h2">영양제 섭취 리포트</span>
        <span class="sub" style="display:block">입력하신 내용으로 분석했습니다.</span></div>
      <div class="rp-acts">
        <button type="button" class="btn-line" data-act="print">인쇄 · PDF 저장</button>
        <button type="button" class="rp-back" data-act="edit">입력 수정</button>
      </div>
    </div>
    <section class="card rp-server">${m.html}</section>
    ${extra}
  </div>`;
};


/* =========================================================================
   [G] 화면 — 다섯 가지 상태
   -------------------------------------------------------------------------
     loading    처음 열 때. 저장된 입력을 불러오는 중.
     input      입력 화면
     analyzing  서버(AI)가 판정하는 중. 몇 초 걸립니다.
     report     결과
     error      실패. 무엇이 잘못됐는지 알려 주고 다시 시도할 수 있게.
   ========================================================================= */

/* 진행 단계 문구 — 분석 중 화면에서 순서대로 켜집니다.
   실제 진행 상황이 아니라 기다리는 시간을 덜 지루하게 만드는 장치입니다. */
const ANALYZE_STEPS = [
  '입력하신 제품의 성분을 모으는 중',
  '성분별 섭취량을 합산하는 중',
  '복용 중인 약과의 상호작용을 확인하는 중',
  '검진 결과와 함께 소견을 정리하는 중',
];

const screenLoading = (msg) => `<div class="page"><div class="state">
  <div class="spin"></div>
  <span class="h1">불러오는 중입니다</span>
  <span class="sub">${esc(msg || '저장해 두신 입력이 있는지 확인하고 있습니다.')}</span>
</div></div>`;

const screenAnalyzing = () => `<div class="page"><div class="state">
  <div class="spin"></div>
  <span class="h1">결과를 분석하고 있습니다</span>
  <span class="sub">입력하신 내용을 바탕으로 성분을 합산하고 주의사항을 확인하는 중입니다.
    보통 몇 초면 끝납니다.</span>
  <ul class="steps" id="an-steps">
    ${ANALYZE_STEPS.map((s, i) => `<li${i === 0 ? ' class="on"' : ''}>${esc(s)}</li>`).join('')}
  </ul>
  <div class="btn-row"><button type="button" class="btn-line" data-act="cancel">취소하고 돌아가기</button></div>
</div></div>`;

/* LOGIN_REQUIRED 는 '/login' 같은 별도 페이지로 보내지 않습니다.
   이 앱은 화면이 통째로 innerHTML 로 바뀌는 구조라서, 페이지를 이동하면
   입력하던 내용이 전부 사라집니다. 대신 로그인 모달을 다시 띄우고,
   원래 하려던 일(재시도 버튼이 부를 함수)을 기억해 뒀다가 로그인 성공
   직후 이어서 실행합니다. */
const screenError = (err, retryLabel) => `<div class="page"><div class="state">
  <span class="h1">결과를 만들지 못했습니다</span>
  <span class="sub">${esc(err && err.message || '알 수 없는 문제가 생겼습니다.')}
    ${err && err.code === 'LOGIN_REQUIRED' ? ' 다시 로그인하면 이어서 진행됩니다.' : ' 입력하신 내용은 그대로 남아 있습니다.'}</span>
  <div class="btn-row">
    ${err && err.code === 'LOGIN_REQUIRED'
      ? `<button type="button" class="btn-solid" data-act="relogin">다시 로그인하기</button>`
      : `<button type="button" class="btn-solid" data-act="retry">${esc(retryLabel || '다시 시도')}</button>`}
    <button type="button" class="btn-line" data-act="edit">입력으로 돌아가기</button>
  </div>
  ${err && err.detail ? `<div class="errbox">${esc(String(err.detail).slice(0, 500))}</div>` : ''}
</div></div>`;

/* =========================================================================
   [블록 -7] 지난 리포트 화면
   ========================================================================= */
const fmtDate = iso => {
  try {
    const d = new Date(iso);
    return `${d.getFullYear()}.${String(d.getMonth()+1).padStart(2,'0')}.${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
  } catch(e){ return iso || ''; }
};

/** 목록 카드에 '무엇을 넣고 뽑은 리포트인지' 적습니다.
    -------------------------------------------------------------------------
    날짜와 배지만 있으면 같은 날 여러 번 돌린 리포트가 전부 똑같아 보여서,
    하나씩 열어 보기 전에는 어느 것이 어느 것인지 알 수 없었습니다.
    그래서 서버가 info 로 입력 요약을 함께 내려보냅니다(규격서 §3.5).

    옛 서버가 info 없이 응답하더라도 카드가 깨지지 않아야 하므로,
    없으면 이 줄들만 빠지고 나머지는 그대로 나옵니다. */
function historyInfoLines(info){
  if(!info) return '';
  const who = [];
  if(info.name) who.push(info.name);
  if(info.age)  who.push(`${info.age}세`);
  if(info.sex)  who.push(info.sex);
  if(info.date) who.push(`검진일 ${info.date}`);

  const what = [];
  if(info.productCount){
    const names = (info.products || []).join(', ');
    const more  = info.productCount - (info.products || []).length;
    what.push(`영양제 ${info.productCount}종${names ? ` (${names}${more ? ` 외 ${more}` : ''})` : ''}`);
  } else if(info.countMeal){
    what.push('식사 평균 추정치 기준');
  }
  if(info.medCount){
    const names = (info.meds || []).join(', ');
    const more  = info.medCount - (info.meds || []).length;
    what.push(`약 ${info.medCount}건${names ? ` (${names}${more ? ` 외 ${more}` : ''})` : ''}`);
  }
  if(info.examCount) what.push(`검진 ${info.examCount}개 항목`);
  if((info.chronic || []).length) what.push(`진단 질환 ${info.chronic.join(' · ')}`);

  return `${who.length ? `<span class="hist-who">${esc(who.join(' · '))}</span>` : ''}
    ${what.length ? `<span class="hist-what">${esc(what.join(' · '))}</span>` : ''}`;
}

const historyCard = r => {
  const asking = UI.deleteAsk === r.id;
  return `<div class="hist-card${asking ? ' asking' : ''}">
  <div class="hist-l">
    <span class="hist-date">${esc(fmtDate(r.createdAt))}</span>
    ${historyInfoLines(r.info)}
    <span class="hist-sum">${esc(r.summaryLine || '')}</span>
    <div class="hist-badges">${(r.badges || []).slice(0, 3).map(b => chip(b.text, b.tone)).join('')}</div>
  </div>
  ${asking
    /* 지우기 전 확인은 카드 안에서 받습니다 — 브라우저 기본 확인창은
       화면 밖에 떠서 '무엇을 지우는 중인지'가 보이지 않습니다. */
    ? `<div class="hist-acts hist-confirm">
         <span class="hist-confirm-t">이 리포트를 지울까요?<br>되돌릴 수 없어요.</span>
         <div class="hist-actrow">
           <button type="button" class="btn-line sm" data-act="cancel-delete-report">취소</button>
           <button type="button" class="btn-danger sm" data-act="confirm-delete-report" data-id="${esc(r.id)}">지우기</button>
         </div>
       </div>`
    : `<div class="hist-acts">
         <button type="button" class="btn-line" data-act="open-report" data-id="${esc(r.id)}">다시 보기</button>
         <button type="button" class="hist-del" data-act="ask-delete-report" data-id="${esc(r.id)}"
                 title="이 리포트 지우기" aria-label="이 리포트 지우기">삭제</button>
       </div>`}
</div>`;
};

function renderHistory(){
  const list = UI.historyList || [];
  return `<div class="page">
    <div class="rp-top">
      <div><span class="h2">지난 리포트</span>
        <span class="sub" style="display:block">${list.length}건</span></div>
      <button type="button" class="btn-solid" data-act="new-report">새 리포트 시작</button>
    </div>
    ${UI.deleteError ? `<div class="banner warn"><b>지우지 못했습니다.</b> ${esc(UI.deleteError)}</div>` : ''}
    ${list.length
      ? `<div class="hist-list">${list.map(historyCard).join('')}</div>`
      : `<section class="card">${emptyCard('아직 리포트가 없습니다',
          '영양제를 입력하고 결과 보기를 누르면 여기에 쌓입니다.')}</section>`}
  </div>`;
}


/* =========================================================================
   [G-1] 메인(홈) 화면
   -------------------------------------------------------------------------
   상단바의 'MyHerb' 이름을 누르면 오는 소개 화면입니다. 실제로 쓸 수 있는
   기능만 적습니다 — 아직 없는 통계나 후기를 꾸며 넣지 않습니다(사용자
   숫자·평점 같은 건 지금 이 서비스에 실제로 없으므로, 있는 것처럼
   보이면 거짓 정보가 됩니다).
   ========================================================================= */
const HOME_FEATURES = [
  {t:'대화 또는 폼, 편한 방식으로', d:'질문에 답하듯 대화로 입력하거나, 원하는 항목만 골라 폼으로 입력하세요. 화면 위 토글로 언제든 바꿀 수 있고, 입력한 내용은 그대로 남아 있어요.'},
  {t:'국가 건강검진 기준 반영', d:'국가 건강검진 실시기준([별표 4])에 맞춰 혈압·혈당·콜레스테롤 같은 검진 항목의 판정을 함께 보여드려요.'},
  {t:'권장 대비 · 상한 대비, 두 기준', d:'먹는 영양제 성분을 권장 섭취량과 상한섭취량, 두 가지 기준으로 동시에 비교해서 보여드려요.'},
  {t:'복용 중인 약과 겹치는지 확인', d:'지금 드시는 약을 함께 적으면, 영양제 성분과 부딪힐 수 있는 조합이 있는지 같이 확인해요.'},
  {t:'지난 리포트는 이력에 저장', d:'분석할 때마다 이력에 남아, 로그인만 하면 언제든 다시 열어볼 수 있어요.'},
  {t:'인쇄해서 보관', d:'결과 화면을 그대로 인쇄하거나 파일로 저장해서 참고할 수 있어요.'},
];

const HOME_STEPS = [
  {t:'기본 정보', d:'나이와 성별만 있으면 시작할 수 있어요.'},
  {t:'건강검진 결과', d:'받으신 항목만 넣으시면 돼요. 선택 사항이에요.'},
  {t:'영양제 · 약', d:'지금 드시는 것들을 적어 주세요. 이것도 선택이에요.'},
  {t:'결과 확인', d:'권장 대비·상한 대비로 바로 확인하고, 필요하면 인쇄해 두세요.'},
];

const HOME_USECASES = [
  {t:'영양제를 여러 개 챙겨 드시는 분', d:'제품마다 겹치는 성분이 상한을 넘기고 있진 않은지 궁금하신 분께 도움이 돼요.'},
  {t:'건강검진 결과를 그냥 넘기셨던 분', d:'수치를 받아만 보고 무엇을 챙겨야 할지 몰랐던 분도, 넣기만 하면 바로 확인할 수 있어요.'},
  {t:'약을 꾸준히 드시는 분', d:'지금 먹는 약과 영양제가 부딪히지 않는지 궁금하신 분께 도움이 돼요.'},
];

function homeFaqAnswerAboutData(){
  return API.source === 'mock'
    ? '지금은 예시 기준값으로 동작하는 개발용 화면이에요. 화면 위에 안내 띠가 떠 있는 동안은 실제 판단에 사용하지 마세요.'
    : '실제 서비스에 연결된 기준으로 계산돼요.';
}

const HOME_FAQ = () => [
  {q:'이 결과는 진단인가요?',
   a:'아니요. MyHerb는 참고용 정보를 보여드릴 뿐, 진단이나 처방이 아니에요. 건강 상태나 복약에 대한 판단은 반드시 의사·약사와 상의해 주세요.'},
  {q:'지금 보여주는 기준값은 실제 서비스 기준인가요?', a:homeFaqAnswerAboutData()},
  {q:'로그인해야만 쓸 수 있나요?',
   a:'네. 입력하신 내용과 지난 리포트를 안전하게 이어서 보시려면 로그인이 필요해요.'},
  {q:'입력한 정보는 어떻게 저장되나요?',
   a:'입력하는 동안 자동으로 저장되고, 분석한 리포트는 이력에 남아 언제든 다시 볼 수 있어요.'},
  {q:'대화형과 폼 중 어느 쪽이 더 정확한가요?',
   a:'둘 다 같은 정보를 모으는 방식만 다를 뿐, 계산 결과는 완전히 같아요. 편한 쪽을 고르시면 됩니다.'},
];

const faqItem = ({q, a}) => `<details class="card sec home-faq">
  <summary><span class="sec-t">${esc(q)}</span>
    <span class="sec-state"><span class="sec-arrow"></span></span></summary>
  <div class="sec-body"><span class="sub">${esc(a)}</span></div>
</details>`;

function screenHome(){
  /* 로그인 여부에 따라 히어로의 행동 버튼이 달라집니다. 로그인하지 않은
     사람에게는 '무료로 시작하기(회원가입)'와 '로그인'을, 이미 로그인한
     사람에게는 실제로 할 수 있는 '입력 시작하기'와 '지난 리포트 보기'를
     보여줍니다 — 로그인·회원가입은 이렇게 메인 화면에서 사용자가 직접
     골라서 시작합니다(자동으로 로그인 창이 뜨지 않습니다). */
  const heroCtas = AUTH.user
    ? `<button type="button" class="home-cta-primary" data-act="start-input">입력 시작하기</button>
       <button type="button" class="home-cta-ghost" data-act="history">지난 리포트 보기</button>`
    : `<button type="button" class="home-cta-primary" data-act="signup">무료로 시작하기</button>
       <button type="button" class="home-cta-ghost" data-act="login">로그인</button>`;

  return `<div class="page home-page">
    ${mockBanner()}

    <section class="home-hero-wrap">
      <div class="home-hero-inner">
        <span class="tag home-eyebrow">영양제 · 건강검진 통합 분석</span>
        <span class="h1">내가 먹는 영양제, 정말 필요한 만큼일까요?</span>
        <span class="sub">나이·성별에 건강검진 결과와 지금 드시는 영양제·약을 더하면, 권장 섭취량과
          상한선 대비 어디쯤인지, 약과 부딪히는 성분은 없는지 한 번에 확인해 드려요.</span>
        <div class="hero-meta">
          <span>대화 또는 폼, 편한 방식으로 입력</span>
          <span>국가 건강검진 실시기준 반영</span>
          <span>지난 리포트는 이력에 저장돼요</span>
        </div>
        <div class="hero-row">${heroCtas}</div>
      </div>
    </section>

    <section class="home-sec">
      <div class="home-sec-head">
        <span class="home-sec-eyebrow">FEATURES</span>
        <span class="h2">MyHerb가 확인해 드리는 것들</span>
        <span class="sub">입력한 내용을 바탕으로 아래 내용을 함께 보여드려요.</span>
      </div>
      <div class="home-feat-grid">
        ${HOME_FEATURES.map((f, i) => `<div class="home-feat">
          <span class="home-badge">${String(i + 1).padStart(2, '0')}</span>
          <span class="home-feat-t">${esc(f.t)}</span>
          <p class="home-feat-d">${esc(f.d)}</p>
        </div>`).join('')}
      </div>
    </section>

    <section class="home-sec tint">
      <div class="home-sec-head">
        <span class="home-sec-eyebrow">HOW IT WORKS</span>
        <span class="h2">이용 방법</span>
      </div>
      <div class="home-steps">
        ${HOME_STEPS.map((s, i) => `<div class="home-step">
          <span class="home-badge">${i + 1}</span>
          <span class="home-step-t">${esc(s.t)}</span>
          <p class="home-step-d">${esc(s.d)}</p>
        </div>`).join('')}
      </div>
    </section>

    <section class="home-sec">
      <div class="home-sec-head">
        <span class="home-sec-eyebrow">FOR YOU</span>
        <span class="h2">이런 분들께 도움이 돼요</span>
      </div>
      <div class="home-usecase-grid">
        ${HOME_USECASES.map(u => `<div class="home-usecase">
          <span class="home-usecase-t">${esc(u.t)}</span>
          <p class="home-usecase-d">${esc(u.d)}</p>
        </div>`).join('')}
      </div>
    </section>

    <section class="home-sec plain">
      <div class="home-sec-head">
        <span class="home-sec-eyebrow">FAQ</span>
        <span class="h2">자주 묻는 질문</span>
      </div>
      ${HOME_FAQ().map(faqItem).join('')}
    </section>

    <footer class="ft">
      <p>이 서비스는 참고용이며 진단이나 처방이 아닙니다.
         건강 상태나 복약에 대한 판단은 반드시 의사·약사와 상의하시기 바랍니다.</p>
    </footer>
  </div>`;
}


/* =========================================================================
   [G-2] 입력 화면
   -------------------------------------------------------------------------
   순서가 중요합니다. 꼭 필요한 '영양제'를 맨 위에 두고, 건너뛸 수 있는
   세 가지는 접어 둡니다. 첫 화면에서 할 일이 하나로 보이게 하기 위해서입니다.
   ========================================================================= */

const unitOpts = sel => UNITS.map(u => `<option${u === sel ? ' selected' : ''}>${u}</option>`).join('');

/* 영양제 성분 한 줄 */
const ingRow = (i = {}) => `<div class="fm-ing" data-ing>
  <input type="text" data-iname list="nutlist" placeholder="예: 비타민 C" value="${esc(i.name || '')}">
  <input type="number" step="any" data-iamt placeholder="함량" value="${i.amount ?? ''}">
  <select data-iunit>${unitOpts(i.unit || 'mg')}</select>
  <span class="ing-flag idle" data-iflag></span>
  <button type="button" class="fm-x" data-del-ing title="이 성분 삭제">×</button>
</div>`;

/* 영양제 한 제품 */
const prodCard = (p = {}) => `<div class="fm-card" data-prod>
  <div class="fm-cardtop">
    <input type="text" data-pname placeholder="제품명 (예: 종합비타민)" value="${esc(p.name || '')}">
    <button type="button" class="fm-x" data-del-prod title="이 제품 삭제">×</button>
  </div>
  <div class="fm-inglab"><span>성분명</span><span>함량</span><span>단위</span><span>기준</span><span></span></div>
  <div data-items>${(p.items && p.items.length ? p.items : [{}]).map(ingRow).join('')}</div>
  <button type="button" class="fm-add sm" data-add-ing>+ 성분 추가</button>
</div>`;

/* 약 한 건 */
const medRow = (m = {}) => `<div class="fm-card" data-med>
  <div class="fm-cardtop">
    <input type="text" data-mname placeholder="약 이름 (예: 와파린 5mg)" value="${esc(m.name || '')}">
    <button type="button" class="fm-x" data-del-med title="삭제">×</button>
  </div>
  <input type="text" data-mdesc placeholder="복용법이나 메모 (선택)" value="${esc(m.desc || '')}">
</div>`;

/* 검진 항목 한 개.
   vals 는 선택 항목입니다 — 폼에서는 렌더 후 fillForm() 이 값을 채우므로
   빈 채로 그려도 되지만, 대화형에서는 그런 후속 처리가 없어서 이미 있는
   state.exam 값을 마크업에 직접 넣어 줘야 '처음부터 다시 입력'했을 때
   전에 답한 값이 그대로 보입니다. */
const examItem = (it, vals = {}) => `<div class="fm-item">
  <span class="nm">${esc(it.name)}</span>
  <div class="fm-row">${it.inputs.map(inp => inp.type === 'select'
    ? `<label class="fm-f"><span>${esc(inp.name || '선택')}</span>
         <select data-exam="${inp.key}">${inp.options.map(o =>
           `<option value="${esc(o)}"${vals[inp.key] === o ? ' selected' : ''}>${esc(o || '미입력')}</option>`).join('')}</select></label>`
    : `<label class="fm-f"><span>${esc(inp.name || it.name)}${inp.unit ? ` (${esc(inp.unit)})` : ''}</span>
         <input type="number" step="any" data-exam="${inp.key}" placeholder="—" value="${esc(vals[inp.key] ?? '')}"></label>`
  ).join('')}</div>
</div>`;

/** 접이식 섹션 껍데기 */
const section = ({id, n, title, required, hint, open, body}) => `
  <details class="card sec" id="sec-${id}"${open ? ' open' : ''}>
    <summary>
      <span class="sec-n">${n}</span>
      <span class="sec-t">${esc(title)}</span>
      ${required ? '<span class="sec-req">필수</span>' : '<span class="sec-opt">건너뛸 수 있음</span>'}
      <span class="sec-state">
        <span class="sec-badge" data-secbadge hidden></span>
        <span class="sec-arrow"></span>
      </span>
    </summary>
    <div class="sec-body">
      ${hint ? `<span class="sub">${hint}</span>` : ''}
      ${body}
    </div>
  </details>`;

/** 입력 화면 맨 위의 '대화로 입력 / 폼으로 입력' 전환 토글.
    두 화면 모두 이 값 하나(UI.inputMode)만 보고 어느 쪽을 그릴지 정합니다. */
function modeToggle(){
  return `<div class="mode-toggle" role="tablist" aria-label="입력 방식">
    <button type="button" class="mode-btn${UI.inputMode === 'chat' ? ' on' : ''}"
            data-act="mode-chat" aria-pressed="${UI.inputMode === 'chat'}">💬 대화로 입력</button>
    <button type="button" class="mode-btn${UI.inputMode === 'form' ? ' on' : ''}"
            data-act="mode-form" aria-pressed="${UI.inputMode === 'form'}">📝 폼으로 입력</button>
  </div>`;
}

/** 폼 화면에서 '전체 초기화'를 눌렀을 때 한 번 더 확인받는 카드.
    대화형 화면과 똑같이, 누르자마자 지우지 않습니다. */
function formClearConfirmHtml(){
  return `<div class="chat-confirm">
    <span class="sub2">정말 지금까지 입력한 내용을 모두 지울까요? 이 작업은 되돌릴 수 없어요.</span>
    <div class="chat-sendrow">
      <button type="button" class="btn-solid sm" data-act="form-clear-yes">네, 전부 지울게요</button>
      <button type="button" class="btn-line sm" data-act="form-clear-no">아니요, 계속할게요</button>
    </div>
  </div>`;
}

function renderInputScreen(){
  return `<div class="page">
    <datalist id="nutlist">${APP.hints.map(h => `<option value="${esc(h)}">`).join('')}</datalist>

    ${mockBanner()}
    ${modeToggle()}

    <section class="card hero">
      <div class="hero-head">
        <span class="h1">지금 나에게 부족한 영양소, 확인해 보세요</span>
        <div class="chat-tools">
          <button type="button" class="chat-tool-btn danger" data-act="form-clear"
                  title="지금까지 입력한 내용을 모두 지우고 처음부터 다시 시작합니다.">전체 초기화</button>
        </div>
      </div>
      <span class="sub">나이와 성별만 넣으면 식사에서 섭취하는 평균 추정치로 부족한 성분을 찾아
        드립니다. 복용 중인 영양제와 약을 더 넣으면 합산량·상한 초과·상호작용까지 함께 봅니다.</span>
      <div class="hero-meta">
        <span>나이와 성별만 있으면 시작</span>
        <span>약 1분</span>
        <span>넣는 정보가 많을수록 결과가 정확해집니다</span>
      </div>
      <div class="hero-row">
        <button type="button" class="btn-line" data-act="history">지난 리포트 보기</button>
        <span class="savestate" id="savestate"></span>
      </div>
      ${UI.confirmClear ? formClearConfirmHtml() : ''}
    </section>

    ${section({
      id:'profile', n:1, title:'기본 정보', required:true, open:true,
      hint:'나이와 성별에 따라 권장섭취량과 검진 판정 기준이 달라집니다. 이 두 가지만 있으면 결과를 볼 수 있습니다.',
      body:`<div class="fm-row">
        <label class="fm-f"><span>이름 (선택)</span><input type="text" id="f-name" placeholder="홍길동"></label>
        <label class="fm-f"><span>나이 *</span><input type="number" id="f-age" min="0" max="120" placeholder="45"></label>
        <label class="fm-f"><span>성별 *</span><select id="f-sex">
          <option value="">선택해 주세요</option><option>남성</option><option>여성</option></select></label>
      </div>
      <label class="fm-tag" style="align-self:flex-start" id="meal-wrap">
        <input type="checkbox" id="f-meal"><span>식사에서 섭취하는 평균 추정치로 함께 계산</span></label>
      <span class="note-s">이 항목을 켜 두면 영양제를 넣지 않아도 식사만으로 부족한 성분을 찾아 드립니다.</span>`,
    })}

    ${section({
      id:'exam', n:2, title:'건강검진 결과',
      hint:'받으신 항목만 넣으시면 됩니다. 국가 건강검진 판정기준(별표 4)으로 항목별 판정을 계산합니다.',
      body:`<div class="fm-row">
          <label class="fm-f" style="max-width:200px"><span>검진일</span><input type="date" id="f-date"></label>
        </div>

        <div>${EXAM.map(g => `<details class="fm-grp">
          <summary>${esc(g.group)}<i class="cnt" data-count></i></summary>
          <div class="fm-grpbody">${g.items.map(examItem).join('')}</div>
        </details>`).join('')}</div>

        <div class="fm-head" style="margin-top:4px"><span class="h3" style="font-size:13px">진단 후 약물 치료 중인 질환</span></div>
        <div class="fm-tags">${CHRONIC.map(c => `<label class="fm-tag">
          <input type="checkbox" data-chronic="${esc(c)}"><span>${esc(c)}</span></label>`).join('')}</div>`,
    })}

    ${section({
      id:'products', n:3, title:'복용 중인 영양제',
      hint:'제품 하나에 성분을 여러 개 넣을 수 있습니다. 제품 뒷면 영양정보의 함량을 그대로 적어 주세요.',
      body:`<div id="prod-list"></div>
        <button type="button" class="fm-add" data-add-prod>+ 영양제 추가</button>`,
    })}

    ${section({
      id:'meds', n:4, title:'복용 중인 약',
      hint:'약 이름을 그대로 적어 주세요. 영양제와 함께 먹을 때 주의할 점을 찾아 드립니다.',
      body:`<div id="med-list"></div>
        <button type="button" class="fm-add" data-add-med>+ 약 추가</button>`,
    })}

    <div class="fm-bar card">
      <div class="fm-sum"><b id="sum-line">나이와 성별을 입력해 주세요</b>
        <span class="note-s" id="sum-hint">이 두 가지만 있으면 식사 기준으로 부족한 성분을 찾아 드립니다.</span></div>
      <button type="button" class="fm-go" id="go-report" disabled>결과 보기</button>
    </div>

    <footer class="ft">
      ${API.source === 'mock'
        ? '<p>지금은 예시 기준값으로 도는 개발용 화면입니다. 실제 판단에 사용하지 마세요.</p>'
        : ''}
      <p>이 서비스는 참고용이며 진단이나 처방이 아닙니다.
         건강 상태나 복약에 대한 판단은 반드시 의사·약사와 상의하시기 바랍니다.</p>
    </footer>
  </div>`;
}


/* =========================================================================
   [G-3] 대화형 입력 화면
   -------------------------------------------------------------------------
   폼과 완전히 같은 state 를 채우는 또 하나의 입력 방식입니다. 판정 로직은
   전혀 없고(질문 순서만 정할 뿐), 답을 받을 때마다 state 를 직접 채운
   뒤 폼과 똑같이 analyze() 를 부릅니다. 그래서 대화 도중 언제든 '폼으로
   입력' 토글을 눌러도 지금까지 답한 내용이 그대로 폼에 채워져 있습니다.

   진행 순서는 nextChatStep() 한 곳에 정리돼 있습니다. 순서를 바꾸고
   싶으면 이 함수 안의 case 들만 옮기면 됩니다.
   ========================================================================= */

/** 지금 단계(from)에 답했다고 가정할 때, 다음에 물어볼 단계. */
function nextChatStep(from){
  switch(from){
    case 'name': return 'age';
    case 'age':  return 'sex';
    case 'sex':  return 'meal';
    case 'meal': return 'examAsk';
    case 'examAsk': return CHAT.wantsExam ? 'examGroups' : 'chronic';
    case 'examGroups': return CHAT.examQueue.length ? 'examGroupDetail' : 'examDate';
    case 'examGroupDetail': return CHAT.examQueue.length ? 'examGroupDetail' : 'examDate';
    case 'examDate': return 'chronic';
    case 'chronic':  return 'prodAsk';
    case 'prodAsk':  return CHAT.wantsProd ? 'prodName' : 'medAsk';
    case 'prodName': return 'prodIngredients';
    case 'prodIngredients': return 'prodMore';
    case 'prodMore': return CHAT.prodMoreYes ? 'prodName' : 'medAsk';
    case 'medAsk':   return CHAT.wantsMed ? 'medName' : 'summary';
    case 'medName':  return 'medDesc';
    case 'medDesc':  return 'medMore';
    case 'medMore':  return CHAT.medMoreYes ? 'medName' : 'summary';
    default: return 'summary';
  }
}

/** 지금 단계에서 봇이 물어보는 말풍선 문구. */
function chatBubbleText(step){
  const nm = state.name ? `${state.name}님, ` : '';
  switch(step){
    case 'name': return '먼저 이름을 알려주시겠어요? 답하지 않으셔도 괜찮아요.';
    case 'age':  return `${nm}나이가 어떻게 되세요?`;
    case 'sex':  return '성별을 알려주세요.';
    case 'meal': return '식사에서 섭취하는 영양성분은 평균 추정치를 반영하여 계산할까요?';
    case 'examAsk': return '건강검진 결과가 있으신가요? 있으시면 몇 가지만 여쭤볼게요.';
    case 'examGroups': return CHAT.importedGroups.length
      ? `검진표에서 읽은 항목(${CHAT.importedGroups.join(', ')})은 이미 채워 두었어요. 이 밖에 결과가 더 있는 항목만 골라 주세요.`
      : '어떤 항목의 검진 결과가 있으신가요? 해당하는 것을 모두 골라 주세요.';
    case 'examGroupDetail': return `${CHAT.examQueue[0]} 결과를 알려주세요. 모르는 값은 비워 두셔도 괜찮아요.`;
    case 'examDate': return '검진 받으신 날짜를 알고 계신가요?';
    case 'chronic': return '진단 후 약물 치료 중인 질환이 있으신가요? 있으시면 골라 주세요.';
    case 'prodAsk': return '지금 복용 중인 영양제가 있으신가요?';
    case 'prodName': return '제품명이 무엇인가요? 제품 뒷면 표기 그대로 적어 주세요.';
    case 'prodIngredients': return `${CHAT.prodDraft ? esc(CHAT.prodDraft.name) : ''}에 들어있는 성분과 함량을 알려주세요.`;
    case 'prodMore': return '다른 영양제도 등록하시겠어요?';
    case 'medAsk': return '지금 복용 중인 약이 있으신가요?';
    case 'medName': return '약 이름을 알려주세요.';
    case 'medDesc': return '복용법이나 메모가 있으면 알려주세요.';
    case 'medMore': return '다른 약도 등록하시겠어요?';
    case 'summary': return '입력하신 내용을 확인해 주세요. 바로 결과를 보여드릴까요?';
    default: return '';
  }
}

/* ---- 위젯(질문에 답하는 입력칸) ------------------------------------------- */
function chatTextWidget({type = 'text', placeholder = '', skippable = false, value = ''}){
  return `<form id="chatTextForm" class="chat-inputrow">
    <input id="chatTextInput" type="${type}" placeholder="${esc(placeholder)}"
           class="chat-textin" value="${esc(value)}" autocomplete="off">
    <button type="submit" class="btn-solid sm">보내기</button>
    ${skippable ? `<button type="button" class="btn-line sm" data-chat-skip>건너뛰기</button>` : ''}
  </form>`;
}

/** 버튼(빠른 선택)과 문장 입력을 둘 다 받는 선택형 위젯들.
    current 를 넘기면 이미 답한 값을 버튼에 미리 표시해 줍니다 —
    '처음부터 다시 입력'으로 같은 질문을 다시 볼 때 필요합니다. */
function chatQuickReplies(options, current){
  return `<div class="chat-inputrow chat-chips">
    ${options.map(o => `<button type="button" class="chip-btn${o.value === current ? ' on' : ''}" data-chat-reply="${esc(o.value)}">${esc(o.label)}</button>`).join('')}
  </div>`;
}

function chatYesNo(yesLabel, noLabel, current){
  return `<div class="chat-inputrow chat-chips">
    <button type="button" class="chip-btn${current === true ? ' on' : ''}" data-chat-yn="yes">${esc(yesLabel)}</button>
    <button type="button" class="chip-btn${current === false ? ' on' : ''}" data-chat-yn="no">${esc(noLabel)}</button>
  </div>`;
}

function chatChipMulti(options, noneLabel){
  const sel = CHAT.tempSelection;
  return `<div>
    <div class="chat-inputrow chat-chips">
      ${options.map(o => `<button type="button" class="chip-btn${sel.includes(o) ? ' on' : ''}" data-chat-chip="${esc(o)}">${esc(o)}</button>`).join('')}
      ${noneLabel ? `<button type="button" class="chip-btn${!sel.length ? ' on' : ''}" data-chat-chip-none>${esc(noneLabel)}</button>` : ''}
    </div>
    <div class="chat-sendrow"><button type="button" class="btn-solid sm" data-chat-confirm-multi>선택 완료</button></div>
  </div>`;
}

/** 버튼 대신 문장으로 답할 수 있게, 모든 선택형 질문 아래에 함께 붙는
    자유 입력 한 줄. chatSubmitFreeText() 가 쉬운 단어 매칭으로 뜻을
    알아내서, 버튼을 눌렀을 때와 똑같은 처리 함수로 넘깁니다. */
function chatFreeTextRow(placeholder){
  return `<form id="chatFreeForm" class="chat-inputrow chat-freerow">
    <input id="chatFreeInput" type="text" class="chat-textin" placeholder="${esc(placeholder)}" autocomplete="off">
    <button type="submit" class="btn-line sm">입력</button>
  </form>`;
}

/** state.exam 에 이미 값이 있는 항목들로부터, 그 항목이 속한 검진 그룹
    이름을 되짚어 냅니다. '처음부터 다시 입력'했을 때 예전에 고른 그룹이
    다시 선택된 채로 보이게 하기 위해서입니다. */
function deriveExamGroupsFromState(){
  return EXAM.filter(g => g.items.some(it => it.inputs.some(inp => state.exam[inp.key] != null && state.exam[inp.key] !== '')))
             .map(g => g.group);
}

/** 검진 항목 카드 위에 보여줄 안내 문구 — 그 그룹의 필드 이름을 그대로
    나열해서, 어떤 순서로 편하게 말하듯 적으면 되는지 알려줍니다. */
function chatExamFreePlaceholder(g){
  const labels = g.items.flatMap(it => it.inputs.map(inp => inp.name || it.name)).filter(Boolean);
  return labels.length ? `예: ${labels.join(', ')} 순서로 편하게 적어주세요` : '결과를 편하게 적어주세요';
}

/** 아래 항목별 칸은 강제로 하나하나 채워야 하는 틀이 아니라, 문장으로
    적은 내용을 이해한 결과를 보여주고 고칠 수 있는 확인란입니다. */
function chatExamGroupCard(){
  const g = EXAM.find(x => x.group === CHAT.examQueue[0]);
  if(!g) return '';
  return `<div>
    <form id="chatExamFreeForm" class="chat-inputrow">
      <input id="chatExamFreeInput" type="text" class="chat-textin"
             placeholder="${esc(chatExamFreePlaceholder(g))}" autocomplete="off">
      <button type="submit" class="btn-line sm">채우기</button>
    </form>
    <span class="sub chat-fieldnote">아래 칸에서 이해한 내용을 확인하고, 다르면 바로 고칠 수 있어요.</span>
    <div class="fm-card chat-card-inline">${g.items.map(it => examItem(it, state.exam)).join('')}</div>
    <div class="chat-sendrow"><button type="button" class="btn-solid sm" data-chat-confirm="examGroupDetail">다음</button></div>
  </div>`;
}

/** 문장 하나를 검진 결과 한 그룹의 필드들에 순서대로 채워 넣습니다.
    선택형(select) 필드는 보기 문구가 그대로 들어있는지로 찾고, 나머지
    숫자 필드는 문장에서 찾은 숫자를 나오는 순서대로(=화면에 보이는
    필드 순서대로) 채웁니다. 완벽하지 않아도 괜찮습니다 — 바로 아래
    칸에서 사용자가 확인하고 고칠 수 있기 때문입니다. */
function fillExamFieldsFromText(g, raw){
  const numbers = raw.match(/-?\d+(?:\.\d+)?/g) || [];
  let ni = 0;
  g.items.forEach(it => it.inputs.forEach(inp => {
    const el = document.querySelector(`#chatWidget [data-exam="${inp.key}"]`);
    if(!el) return;
    if(inp.type === 'select'){
      const hit = (inp.options || []).find(o => o && raw.includes(o));
      if(hit) el.value = hit;
      return;
    }
    if(ni < numbers.length){ el.value = numbers[ni]; ni++; }
  }));
}

/** 문장을 채워 넣은 뒤 바로 다음 질문으로 넘어갑니다 — '채우기'까지만
    하고 '다음'을 따로 마우스로 눌러야 했던 게 대화 흐름을 끊었으므로,
    문장을 보내는 동작 자체가 그 그룹에 대한 답이 되도록 합니다.
    (필드는 여전히 화면에 남아 있으니, 굳이 문장으로 안 쓰고 칸을 직접
    고친 뒤 '다음' 버튼을 눌러도 똑같이 동작합니다.) */
function chatSubmitExamFree(){
  const el = document.getElementById('chatExamFreeInput');
  const raw = el ? el.value.trim() : '';
  if(!raw) return;
  const g = EXAM.find(x => x.group === CHAT.examQueue[0]);
  if(!g) return;
  fillExamFieldsFromText(g, raw);
  chatConfirmExamGroup(raw);      // 대화에는 사용자가 쓴 문장을 그대로 남깁니다
}

/** 영양제 성분도 항목별 칸을 하나씩 클릭해서 채우지 않아도, 문장으로
    쭉 적으면(쉼표나 줄바꿈으로 구분) 자동으로 여러 줄에 나눠 채워 줍니다. */
function chatProductCard(){
  return `<div>
    <form id="chatProdFreeForm" class="chat-inputrow">
      <input id="chatProdFreeInput" type="text" class="chat-textin"
             placeholder="예: 비타민D 25mcg, 오메가3 1000mg" autocomplete="off">
      <button type="submit" class="btn-line sm">채우기</button>
    </form>
    <span class="sub chat-fieldnote">아래 칸에서 이해한 내용을 확인하고, 다르면 바로 고칠 수 있어요.</span>
    <div class="fm-card chat-card-inline" data-prod>
      <div class="fm-inglab"><span>성분명</span><span>함량</span><span>단위</span><span></span></div>
      <div data-items>${(CHAT.prodDraft.items && CHAT.prodDraft.items.length ? CHAT.prodDraft.items : [{}]).map(ingRow).join('')}</div>
      <button type="button" class="fm-add sm" data-add-ing>+ 성분 추가</button>
    </div>
    <div class="chat-sendrow"><button type="button" class="btn-solid sm" data-chat-confirm="prodIngredients">이 제품 등록 완료</button></div>
  </div>`;
}

/** 자유 입력에서 자주 쓰이는 단위 표기를, 드롭다운에 있는 정식 표기로
    바꿔 줍니다(마이크로그램 기호 µ 는 손으로 치기 어려우니 mcg/μg/ug
    같은 표기도 다 받아 줍니다). 목록에 없는 표기는 그대로 둡니다 —
    드롭다운에서 사용자가 직접 고르면 되니까요. */
const UNIT_ALIASES = {mcg:'µg', 'μg':'µg', ug:'µg', ml:'mL', iu:'IU', cfu:'억CFU', '억cfu':'억CFU'};
function normalizeUnit(raw){
  const t = (raw || '').trim();
  if(!t) return '';
  const alias = UNIT_ALIASES[t.toLowerCase()];
  if(alias) return alias;
  const hit = UNITS.find(u => u.toLowerCase() === t.toLowerCase());
  return hit || t;
}

/** "비타민D 25mcg, 오메가3 1000mg" 처럼 쉼표·줄바꿈으로 구분한 문장 하나를
    성분 하나로 봅니다. 이름 뒤에 오는 숫자를 함량으로, 그 다음 글자를
    단위로 봅니다 — 단위를 안 적었거나 목록에 없는 표기여도 일단 그대로
    받아 두고, 사용자가 아래 드롭다운에서 고치면 됩니다. */
function parseIngredientText(seg){
  const m = seg.match(/^(.+?)\s+(-?\d+(?:\.\d+)?)\s*([^\d\s,]*)\s*$/);
  if(!m) return null;
  const name = m[1].trim();
  const amount = m[2];
  const unit = normalizeUnit(m[3]);
  return {name, amount, unit};
}

/** 성분을 채워 넣은 뒤 바로 이 제품 등록을 완료하고 다음으로 넘어갑니다
    — examGroupDetail 과 같은 이유로, 문장을 보내는 동작 자체가 답이
    되게 합니다. 문장에서 성분을 하나도 못 알아들었을 때만 다시 물어보고
    (조용히 빈 제품으로 넘어가면 사용자가 실수를 알아채기 어려우므로),
    알아들은 게 있으면 그대로 등록하고 넘어갑니다. */
function chatSubmitProdFree(){
  const el = document.getElementById('chatProdFreeInput');
  const raw = el ? el.value.trim() : '';
  if(!raw) return;
  const segs = raw.split(/[,\n、]+/).map(s => s.trim()).filter(Boolean);
  const parsed = segs.map(parseIngredientText).filter(Boolean);
  if(!parsed.length){
    chatFlagFreeText('성분 이름과 숫자를 함께 적어 주세요 (예: 비타민D 25mcg)', 'chatProdFreeInput');
    return;
  }
  const box = document.querySelector('#chatWidget [data-items]');
  if(!box) return;
  parsed.forEach((p, i) => {
    let row = box.querySelectorAll('[data-ing]')[i];
    if(!row){
      box.insertAdjacentHTML('beforeend', ingRow());
      row = box.lastElementChild;
    }
    row.querySelector('[data-iname]').value = p.name;
    row.querySelector('[data-iamt]').value = p.amount;
    if(p.unit){
      const unitEl = row.querySelector('[data-iunit]');
      // 드롭다운에 없는 표기를 그대로 넣으면 선택이 풀려 버리므로,
      // 목록에 실제로 있는 값일 때만 바꿔 줍니다(없으면 기본값 mg 유지).
      if([...unitEl.options].some(o => o.value === p.unit)) unitEl.value = p.unit;
    }
  });
  chatConfirmProduct(raw);        // 대화에는 사용자가 쓴 문장을 그대로 남깁니다
}

function chatSummaryWidget(){
  const items = state.products.reduce((a, p) => a + p.items.length, 0);
  const examFilled = Object.values(state.exam).filter(v => v !== '' && v != null).length;
  const bits = [`${state.age}세 · ${state.sex}`];
  if(items) bits.push(`영양제 ${state.products.length}종 · 성분 ${items}개`);
  else if(state.countMeal) bits.push('식사 평균 추정치 기준');
  if(state.meds.length) bits.push(`약 ${state.meds.length}건`);
  if(examFilled) bits.push(`검진 ${examFilled}개 항목`);
  return `<div>
    <div class="chat-summary">${bits.map(b => chip(b, 'blue')).join('')}</div>
    <div class="chat-sendrow">
      <button type="button" class="fm-go" data-chat-finish>결과 보기</button>
      <button type="button" class="btn-line sm" data-act="mode-form">폼에서 확인하기</button>
    </div>
    ${chatFreeTextRow('예: 네, 결과 보여주세요')}
  </div>`;
}

/** 지금 단계에 맞는 위젯 하나를 고릅니다.
    선택형 질문(버튼)에는 chatFreeTextRow() 를 함께 붙여서, 버튼을 누르지
    않고 문장으로 답해도 되게 합니다. */
function chatWidgetHtml(step){
  switch(step){
    case 'name':   return chatTextWidget({placeholder:'홍길동', skippable:true, value:state.name});
    case 'age':    return chatTextWidget({type:'number', placeholder:'45', value:state.age});
    case 'sex':    return chatQuickReplies([{label:'남성', value:'남성'}, {label:'여성', value:'여성'}], state.sex)
                          + chatFreeTextRow('예: 여성');
    case 'meal':   return chatYesNo('네, 함께 계산할게요', '아니요, 영양제만요', state.countMeal)
                          + chatFreeTextRow('예: 네, 함께 계산해줘');
    case 'examAsk': return chatYesNo('있어요', '없어요', CHAT.wantsExam)
                          + chatFreeTextRow('예: 있어요 / 없어요');
    case 'examGroups': {
      if(CHAT.tempSeededFor !== 'examGroups'){
        CHAT.tempSelection = deriveExamGroupsFromState();
        CHAT.tempSeededFor = 'examGroups';
      }
      return chatChipMulti(EXAM.map(g => g.group)) + chatFreeTextRow('예: 고혈압, 당뇨병 / 없음');
    }
    case 'examGroupDetail': return chatExamGroupCard();
    case 'examDate': return chatTextWidget({placeholder:'예: 2024-03-15 또는 지난달 중순', skippable:true, value:state.date});
    case 'chronic': {
      if(CHAT.tempSeededFor !== 'chronic'){
        CHAT.tempSelection = state.chronic.slice();
        CHAT.tempSeededFor = 'chronic';
      }
      return chatChipMulti(CHRONIC, '없음') + chatFreeTextRow('예: 고혈압 / 없음');
    }
    case 'prodAsk': return chatYesNo('있어요', '없어요', CHAT.wantsProd) + chatFreeTextRow('예: 있어요 / 없어요');
    case 'medAsk':  return chatYesNo('있어요', '없어요', CHAT.wantsMed) + chatFreeTextRow('예: 있어요 / 없어요');
    /* 고치는 중일 때는 지금 값이 칸에 그대로 들어가 있어야 합니다 —
       빈 칸이 뜨면 무엇을 고치는 중인지 알 수 없기 때문입니다. */
    case 'prodName': return chatTextWidget({placeholder:'종합비타민', value: editValueOf('prodName')});
    case 'prodIngredients': return chatProductCard();
    case 'prodMore': return chatYesNo('네, 더 있어요', '아니요, 다 됐어요', CHAT.prodMoreYes) + chatFreeTextRow('예: 네 / 아니요');
    case 'medMore':  return chatYesNo('네, 더 있어요', '아니요, 다 됐어요', CHAT.medMoreYes) + chatFreeTextRow('예: 네 / 아니요');
    case 'medName': return chatTextWidget({placeholder:'와파린 5mg', value: editValueOf('medName')});
    case 'medDesc': return chatTextWidget({placeholder:'항응고제 · 1일 1회 (선택)', skippable:true, value: editValueOf('medDesc')});
    case 'summary': return chatSummaryWidget();
    default: return '';
  }
}

/* ---- 화면 조립 ------------------------------------------------------------ */
/** '전체 초기화'를 눌렀을 때, 지우기 전에 한 번 더 확인받는 문구.
    입력칸 자리에 위젯 대신 이 카드가 뜹니다. */
function chatClearConfirmHtml(){
  return `<div class="chat-confirm">
    <span class="sub2">정말 지금까지 입력한 내용을 모두 지울까요? 이 작업은 되돌릴 수 없어요.</span>
    <div class="chat-sendrow">
      <button type="button" class="btn-solid sm" data-act="chat-clear-yes">네, 전부 지울게요</button>
      <button type="button" class="btn-line sm" data-act="chat-clear-no">아니요, 계속할게요</button>
    </div>
  </div>`;
}

/** 말풍선 하나. 사용자가 답한 말풍선에는 '수정'을 붙여, 뒤늦게 잘못 답한
    것을 알아차렸을 때 처음부터 다시 하지 않아도 되게 합니다. */
function chatMsgHtml(m, i){
  const editable = m.role === 'user' && m.step && canEditStep(m.step) && !CHAT.editing;
  return `<div class="chat-msg ${m.role}${m.edited ? ' edited' : ''}${m.auto ? ' auto' : ''}">
    ${editable ? `<button type="button" class="chat-edit" data-chat-edit="${i}"
        title="이 답변 고치기" aria-label="이 답변 고치기">수정</button>` : ''}
    <span class="chat-bubble">${m.auto ? '<i class="chat-auto">검진표에서</i>' : ''}${esc(m.text)}</span>
  </div>`;
}

/* =========================================================================
   [G-3B] 검진표 사진 등록 — 대화 중 언제든 쓸 수 있는 ＋ 버튼
   -------------------------------------------------------------------------
   질문에 하나씩 답하는 대신, 건강검진 결과지를 사진으로 올리면 서버가 읽어
   한꺼번에 채워 넣습니다. 그리고 그렇게 채워진 것은 **다시 묻지 않습니다.**

   ★ 이미지만 받습니다. 파일 선택 창에서도 이미지만 보이게 하고(accept),
     고르고 난 뒤에도 한 번 더 확인합니다 — accept 는 '권장'일 뿐이라
     사용자가 '모든 파일'로 바꿔서 아무거나 고를 수 있기 때문입니다.
     서버도 파일 앞머리 바이트로 다시 확인합니다(3중 확인).
   ========================================================================= */
const IMAGE_ACCEPT = 'image/png,image/jpeg,image/gif,image/webp,image/bmp,image/heic';

/* 사진 한 장의 크기 상한. 요즘 폰 사진이 3~6MB 쯤이라 10MB 면 넉넉합니다.
   서버(vision.py)도 같은 값으로 다시 확인합니다 — 화면에서 막는 것은
   사용자를 기다리게 하지 않으려는 것일 뿐, 방어는 서버가 합니다. */
const MAX_IMAGE_BYTES = 10 * 1024 * 1024;

function chatAttachToolHtml(){
  if(CHAT.imgBusy){
    return `<span class="chat-tool-btn attach busy" aria-live="polite">
      <span class="spin sm"></span>
      <span>검진표를 읽고 있어요…</span>
    </span>`;
  }
  const done = CHAT.imported;
  /* 안내 문구('이미지 파일만 · 10MB 이하')는 버튼 옆에 따로 두지 않고
     title 로 옮겼습니다 — 머리글 줄은 좁아서 글자가 늘어나면 줄이
     밀립니다. 무엇을 읽었는지는 어차피 대화에 그대로 남습니다. */
  return `<button type="button" class="chat-tool-btn attach" data-act="pick-exam-image"
          title="건강검진 결과지 사진을 올리면 읽어서 자동으로 채워 드려요 (이미지 파일만 · 10MB 이하)">
    <span class="chat-attach-plus" aria-hidden="true">＋</span>
    <span>${done ? '검진표 다시 올리기' : '검진표 이미지 등록'}</span>
  </button>`;
}

/** 사진을 읽지 못한 이유. 머리글 바로 아래에 한 줄로 붙습니다.
    파일 형식·크기 때문에 막힌 경우는 대화에 아무것도 남지 않으므로,
    이 줄이 없으면 왜 아무 일도 일어나지 않았는지 알 수 없습니다. */
function chatAttachErrHtml(){
  return CHAT.imgError
    ? `<div class="chat-attach-err">${esc(CHAT.imgError)}</div>`
    : '';
}

/** 파일을 고른 순간 — 서버에 보내기 전에 화면에서 먼저 걸러 냅니다.
    (서버까지 갔다 와서 거절당하면 그만큼 사용자가 기다립니다) */
async function handleExamImageFile(file){
  if(!file) return;
  CHAT.imgError = null;

  if(!/^image\//.test(file.type || '')){
    CHAT.imgError = '이미지 파일만 올릴 수 있어요. (PNG · JPG · GIF · WEBP · HEIC)';
    rerenderChat();
    return;
  }
  if(file.size > MAX_IMAGE_BYTES){
    CHAT.imgError = `사진이 너무 큽니다. ${MAX_IMAGE_BYTES / 1048576}MB 이하로 올려 주세요.`;
    rerenderChat();
    return;
  }

  /* 결과보기 때 이 사진을 서버로 함께 보냅니다. 서버는 사진을 저장하지
     않기 때문에(민감정보), 분석하는 순간까지 브라우저가 들고 있습니다. */
  CHAT.examFile = file;

  CHAT.imgBusy = true;
  CHAT.log.push({role:'user', text:`🖼 ${file.name}`});
  rerenderChat();

  try {
    applyExamReading(await API.readExamImage(file));
  } catch(e){
    /* 판독에 실패해도 대화는 그대로 이어집니다 — 사진이 흐리다고 입력을
       처음부터 다시 하게 만들 수는 없으니까요. */
    CHAT.log.push({role:'bot', text:'사진을 읽지 못했어요. 질문에 직접 답해 주시면 그대로 채워 드릴게요.'});
    CHAT.imgError = e.code === 'LOGIN_REQUIRED'
      ? '로그인이 풀렸어요. 다시 로그인한 뒤 올려 주세요.'
      : (e.message || '사진을 읽지 못했습니다.');
  } finally {
    CHAT.imgBusy = false;
    rerenderChat();
  }
}

/** 판독 결과를 입력값에 넣고, 이미 채워진 질문은 건너뜁니다.
    -------------------------------------------------------------------------
    무엇을 덮어쓰고 무엇을 남길지 —
      검진 수치   사진이 원본이므로 **덮어씁니다**
      만성질환    이미 고른 것에 **더합니다** (사진에 없다고 지우면 안 됩니다)
      검진일      사진의 날짜로 덮어씁니다 (검진표에 찍힌 날이 정확합니다)
      이름·나이·성별
        이번 대화에서 **직접 답하신 적이 있으면 그대로 둡니다.** 방금 손으로
        적은 값을 사진이 밀어내면 안 되니까요. 반대로 지난번에 저장해 둔
        값(임시저장)만 있다면 사진 쪽을 씁니다 — 사용자가 방금 이 검진표를
        올린 것 자체가 '이 문서 기준으로 봐 달라'는 뜻이기 때문입니다. */
function chatAnsweredByUser(step){
  return CHAT.log.some(m => m.role === 'user' && m.step === step && !m.auto);
}

function applyExamReading(r){
  const keys = Object.keys(r.exam || {});
  Object.entries(r.exam || {}).forEach(([k, v]) => { state.exam[k] = v; });
  (r.chronic || []).forEach(c => { if(!state.chronic.includes(c)) state.chronic.push(c); });

  const auto = [];   // [단계, 대화에 남길 문구]
  if(r.name && !chatAnsweredByUser('name')){ state.name = r.name; auto.push(['name', r.name]); }
  if(r.age  && !chatAnsweredByUser('age') ){ state.age  = r.age;  auto.push(['age', `${r.age}세`]); }
  if(r.sex  && !chatAnsweredByUser('sex') ){ state.sex  = r.sex;  auto.push(['sex', r.sex]); }
  if(r.date && !chatAnsweredByUser('examDate')){ state.date = r.date; auto.push(['examDate', r.date]); }

  CHAT.imported = {source: r.source, count: keys.length, at: Date.now()};
  CHAT.importedGroups = r.groups || [];
  CHAT.wantsExam = true;

  /* 사진에서 읽은 것은 다시 묻지 않습니다. */
  CHAT.known = ['examAsk', ...auto.map(([step]) => step)];
  if((r.chronic || []).length) CHAT.known.push('chronic');

  /* 무엇을 읽었는지 그대로 보여 줍니다 — 잘못 읽었을 때 사용자가 바로
     알아채고 고칠 수 있어야 하기 때문입니다. */
  const head = r.source === 'demo'
    ? '⚠ 예시 판독입니다(실제 사진을 읽은 결과가 아니에요). 검진표에서 이렇게 읽었다고 가정할게요.'
    : '검진표에서 이렇게 읽었어요.';
  const lines = (r.fields || []).map(f => `· ${f.name} ${f.text}`);
  CHAT.log.push({role:'bot', text: keys.length
    ? `${head}\n${lines.join('\n')}\n\n다르게 읽은 값이 있으면 아래 '수정'으로 고칠 수 있어요.`
    : '사진에서 읽어낼 수 있는 검진값이 없었어요. 질문에 직접 답해 주시면 그대로 채워 드릴게요.'});

  /* 자동으로 채워진 답들도 대화에 남깁니다 — 그래야 '수정' 버튼이 붙어서
     나중에 고칠 수 있고, 무엇이 저절로 채워졌는지도 눈에 보입니다. */
  auto.forEach(([step, text]) => CHAT.log.push({role:'user', text, step, auto:true}));
  if(CHAT.importedGroups.length){
    CHAT.importedGroups.forEach(g => CHAT.log.push({
      role:'user', text: chatExamGroupConfirmText(g), step:'examGroupDetail', ref:g, auto:true}));
  }

  /* 사진에서 채워지지 않은 검진 그룹만 큐에 남깁니다. */
  CHAT.examQueue = CHAT.examQueue.filter(g => !CHAT.importedGroups.includes(g));
  CHAT.step = chatFirstUnknownFrom(CHAT.step);
}

/** 지금 단계부터 앞으로 나아가면서, 이미 아는 질문은 지나칩니다. */
function chatFirstUnknownFrom(step){
  let s = step;
  for(let i = 0; i < 40 && CHAT.known.includes(s); i++) s = nextChatStep(s);
  return s;
}

/** 고치는 중일 때 입력칸 위에 뜨는 안내 줄. */
function chatEditBarHtml(){
  return `<div class="chat-editbar">
    <span class="chat-editbar-t">답변을 고치고 있어요. 새로 답하시면 원래 보시던 자리로 돌아가요.</span>
    <button type="button" class="chat-tool-btn" data-act="chat-edit-cancel">고치기 취소</button>
  </div>`;
}

function renderChatScreen(){
  /* 지금까지 끝난 대화(CHAT.log)는 그대로 보여 주고, 아직 답하지 않은
     '지금 질문'만 매번 새로 계산해서 맨 아래 하나 더 붙입니다. */
  const liveBubble = `<div class="chat-msg bot"><span class="chat-bubble">${esc(chatBubbleText(CHAT.step))}</span></div>`;
  return `<div class="page">
    <datalist id="nutlist">${APP.hints.map(h => `<option value="${esc(h)}">`).join('')}</datalist>

    ${mockBanner()}
    ${modeToggle()}

    <section class="card chat-card">
      <div class="chat-headrow">
        <div>
          <span class="h2">대화로 입력하기</span>
          <span class="sub">질문에 답하시면 그대로 채워져요. 버튼을 누르거나 문장으로 직접 답해도 돼요.</span>
        </div>
        <div class="chat-tools">
          ${CHAT.editing || CHAT.confirmClear ? '' : chatAttachToolHtml()}
          <button type="button" class="chat-tool-btn danger" data-act="chat-clear"
                  title="지금까지 입력한 내용을 모두 지우고 처음부터 다시 시작합니다.">전체 초기화</button>
        </div>
      </div>
      ${chatAttachErrHtml()}

      <div class="chat-log" id="chatLog">
        ${CHAT.log.map(chatMsgHtml).join('')}
        ${liveBubble}
      </div>

      <div class="chat-input-area" id="chatInputArea">
        ${CHAT.editing ? chatEditBarHtml() : ''}
        ${CHAT.confirmClear ? chatClearConfirmHtml() : `<div id="chatWidget">${chatWidgetHtml(CHAT.step)}</div>`}
      </div>

      <!-- 파일 선택 창을 여는 데만 쓰는 숨은 입력칸입니다. 위의 ＋ 버튼이
           이걸 대신 눌러 줍니다(기본 파일 선택 버튼은 모양을 맞추기 어렵습니다). -->
      <input type="file" id="examImageInput" accept="${IMAGE_ACCEPT}" hidden>
    </section>

    <footer class="ft">
      ${API.source === 'mock'
        ? '<p>지금은 예시 기준값으로 도는 개발용 화면입니다. 실제 판단에 사용하지 마세요.</p>'
        : ''}
      <p>이 서비스는 참고용이며 진단이나 처방이 아닙니다.
         건강 상태나 복약에 대한 판단은 반드시 의사·약사와 상의하시기 바랍니다.</p>
    </footer>
  </div>`;
}

/** 화면을 다시 그리고 맨 아래(방금 온 말풍선)로 스크롤합니다.
    화면 전체를 innerHTML 로 새로 그리기 때문에, 방금 답하고 나서 커서가
    있던 입력칸도 매번 새 DOM 요소로 바뀌어 포커스가 풀립니다. 그대로 두면
    한 마디 칠 때마다 다시 입력칸을 클릭해야 해서 불편하므로, 다시 그린
    뒤 바로 다음 질문의 입력칸에 포커스를 돌려줍니다. */
function rerenderChat(){
  app().innerHTML = renderChatScreen();
  const log = document.getElementById('chatLog');
  if(log) log.scrollTop = log.scrollHeight;
  focusChatInput();
}

/** 지금 화면에 있는 입력칸 중 가장 먼저 답해야 할 것에 포커스를 줍니다. */
function focusChatInput(){
  const el = document.getElementById('chatTextInput')
    || document.getElementById('chatFreeInput')
    || document.getElementById('chatExamFreeInput')
    || document.getElementById('chatProdFreeInput')
    || document.querySelector('#chatWidget input, #chatWidget select');
  if(el) el.focus();
}

/** 한 질문에 답했을 때 공통으로 하는 일 — 로그에 남기고, (있다면) 어떻게
    반영됐는지 챗봇이 짚어준 뒤, 다음 질문으로 넘어가고, 저장합니다.
    confirmText 를 넘기면 사용자의 답이 실제로 어떤 값으로 기록됐는지
    챗봇이 한 번 더 확인해 줍니다 — 특히 검진 수치처럼 문장에서 여러 값을
    뽑아 채우는 경우, 제대로 이해했는지 사용자가 바로 알 수 있어야 하기
    때문입니다. */
function chatAdvance(step, botText, userText, confirmText, ref){
  const ed = CHAT.editing;
  if(ed && ed.index != null){
    /* 고치는 중이면 새 말풍선을 아래에 덧붙이지 않고, 원래 답했던 그 자리의
       내용을 고쳐 씁니다 — 대화 기록이 지금 값과 어긋나 있으면 나중에 무엇이
       맞는 값인지 알 수 없게 되기 때문입니다. */
    CHAT.log[ed.index] = {role:'user', text:userText, step, ref, edited:true};
    const after = CHAT.log[ed.index + 1];
    if(confirmText){
      if(after && after.confirm) after.text = confirmText;
      else CHAT.log.splice(ed.index + 1, 0, {role:'bot', text:confirmText, confirm:true});
    }
    ed.index = null;            // 이어지는 되묻기(있다면)는 평소처럼 아래에 쌓습니다
  } else {
    /* 고치는 중에 딸려 나온 질문을 다시 답한 것이라면, 같은 질문에 대한
       예전 말풍선은 걷어냅니다 — 같은 질문과 답이 위아래로 두 번 남아 있으면
       어느 쪽이 지금 값인지 알 수 없기 때문입니다. */
    if(CHAT.editing) chatDropAnswers([step], ref !== undefined ? [ref] : null);
    CHAT.log.push({role:'bot', text: botText});
    if(userText != null) CHAT.log.push({role:'user', text: userText, step, ref});
    if(confirmText) CHAT.log.push({role:'bot', text: confirmText, confirm:true});
  }

  CHAT.step = chatNextAfterAnswer(step);
  queueSave();
  rerenderChat();
}

/** 다음에 보여줄 질문을 정합니다.
    평소에는 nextChatStep() 그대로지만, 답을 고치는 중이라면 고치기 전에
    보고 있던 자리로 돌려보냅니다 — 나이 하나 고치려다 뒤의 질문을 전부
    다시 답하게 되면 고치는 의미가 없기 때문입니다.
    단, '검진 결과가 있으신가요?'처럼 답을 바꾸면 새로 물어봐야 할 것이
    생기는 질문은, 그 딸린 질문들을 다 마친 뒤에 돌아갑니다. */
function chatNextAfterAnswer(step){
  /* 검진표 사진으로 이미 채워진 질문은 지나칩니다 — 사진을 올린 다음에도
     "검진 결과가 있으신가요?" 를 다시 묻는다면 사진을 올린 의미가 없습니다.
     (고치는 중일 때는 지나치지 않습니다. 일부러 그 질문으로 돌아온 것이니까요.) */
  const next = CHAT.editing ? nextChatStep(step) : chatFirstUnknownFrom(nextChatStep(step));
  if(!CHAT.editing) return next;
  const flow = EDIT_SUBFLOW[CHAT.editing.step] || [];
  if(flow.includes(next)) return next;          // 아직 딸린 질문이 남았습니다
  const back = CHAT.editing.returnStep;
  if(!flow.length) chatRestoreEditContext();    // 값만 고친 경우 — 하던 자리 그대로 복원
  CHAT.editing = null;
  return back;
}

/* ---- 이전 답변 고치기 -----------------------------------------------------
   대화는 위에서 아래로 흐르지만, 중간에 잘못 답한 것을 알아차렸을 때 처음부터
   다시 하게 만들면 안 됩니다. 그래서 답한 말풍선마다 '수정'을 붙이고, 누르면
   그 질문으로 잠깐 되돌아갔다가 답하면 하던 자리로 되돌아옵니다.        */

/** 이 답변에 '수정' 버튼을 붙일 수 있는지. */
function canEditStep(step){ return EDITABLE_STEPS.includes(step); }

/** 되돌아가기 전에, 지금 진행 중이던 상태를 통째로 넣어 둡니다.
    (예: 검진 그룹을 순서대로 묻는 도중에 나이를 고치러 갔다가 돌아오면,
     남아 있던 그룹 순서가 그대로 이어져야 합니다) */
function chatSaveEditContext(){
  return {
    examQueue: CHAT.examQueue.slice(),
    prodDraft: CHAT.prodDraft,
    medDraft : CHAT.medDraft,
    tempSelection: CHAT.tempSelection.slice(),
    tempSeededFor: CHAT.tempSeededFor,
  };
}

function chatRestoreEditContext(){
  const s = CHAT.editing && CHAT.editing.saved;
  if(!s) return;
  CHAT.examQueue = s.examQueue;
  CHAT.prodDraft = s.prodDraft;
  CHAT.medDraft  = s.medDraft;
  CHAT.tempSelection = s.tempSelection;
  CHAT.tempSeededFor = s.tempSeededFor;
}

/** 되돌아간 질문이 '지금 값'을 그대로 보여주도록 준비합니다. */
function chatPrepareEditContext(e){
  if(e.step === 'examGroupDetail'){ CHAT.examQueue = [e.ref]; }
  else if(e.step === 'chronic'){ CHAT.tempSelection = state.chronic.slice(); CHAT.tempSeededFor = 'chronic'; }
  else if(e.step === 'examGroups'){ CHAT.tempSelection = deriveExamGroupsFromState(); CHAT.tempSeededFor = 'examGroups'; }
  else if(e.step === 'prodIngredients'){
    const p = state.products[e.ref];
    CHAT.prodDraft = p ? {name:p.name, items:p.items.slice()} : {name:'', items:[{}]};
  }
}

function chatStartEdit(index){
  const e = CHAT.log[index];
  if(!e || !e.step || !canEditStep(e.step)) return;
  CHAT.editing = {index, step:e.step, ref:e.ref, returnStep: CHAT.step, saved: chatSaveEditContext()};
  CHAT.confirmClear = false;
  chatPrepareEditContext(e);
  CHAT.step = e.step;
  rerenderChat();
}

/** 고치다 말고 그만두기 — 값도 대화 기록도 건드리지 않고 하던 자리로. */
function chatCancelEdit(){
  if(!CHAT.editing) return;
  const back = CHAT.editing.returnStep;
  chatRestoreEditContext();
  CHAT.editing = null;
  CHAT.step = back;
  rerenderChat();
}

/** 지금 고치는 중인 단계인지 (위젯에 지금 값을 미리 채워 넣을 때 씁니다) */
function editingStep(step){
  return CHAT.editing && CHAT.editing.step === step ? CHAT.editing : null;
}

/** 고치는 중인 항목의 지금 값 — 처음 답할 때는 빈 칸 그대로입니다. */
function editValueOf(step){
  const ed = editingStep(step);
  if(!ed) return '';
  if(step === 'prodName') return (state.products[ed.ref] || {}).name || '';
  if(step === 'medName')  return (state.meds[ed.ref] || {}).name || '';
  if(step === 'medDesc')  return (state.meds[ed.ref] || {}).desc || '';
  return '';
}

/** '있어요 → 없어요'처럼 답을 되돌렸을 때, 그 답에 딸려 있던 값과 말풍선을
    함께 걷어냅니다. 답은 '없어요'인데 아래에 그때 적은 수치가 그대로 남아
    있으면 어느 쪽이 맞는지 알 수 없기 때문입니다. */
function chatDropAnswers(steps, refs){
  for(let i = CHAT.log.length - 1; i >= 0; i--){
    const m = CHAT.log[i];
    if(m.role !== 'user' || !steps.includes(m.step)) continue;
    if(refs && !refs.includes(m.ref)) continue;
    const from = (i > 0 && CHAT.log[i - 1].role === 'bot' && !CHAT.log[i - 1].confirm) ? i - 1 : i;
    const to   = (CHAT.log[i + 1] && CHAT.log[i + 1].confirm) ? i + 1 : i;
    CHAT.log.splice(from, to - from + 1);
    i = from;
  }
}

/** 검진 그룹 하나에 딸린 값들을 지웁니다. */
function clearExamGroup(groupName){
  const g = EXAM.find(x => x.group === groupName);
  if(!g) return;
  g.items.forEach(it => it.inputs.forEach(inp => { delete state.exam[inp.key]; }));
}

/* ---- 답변 처리 ------------------------------------------------------------
   위젯 종류별로 하나씩. 값을 state/CHAT 에 쓴 뒤 chatAdvance() 를 부릅니다. */
/** 답을 꼭 해야 하는 칸을 비운 채 보내면, 다시 그리지 않고 그 칸만
    빨갛게 표시합니다(전체를 다시 그리면 방금 누른 포커스가 날아갑니다). */
function chatFlagRequired(){
  const el = document.getElementById('chatTextInput');
  if(!el) return;
  el.classList.add('err');
  el.placeholder = '꼭 답해 주세요';
  el.focus();
}

/** 자유 입력 칸에 뜻을 알 수 없는 문장이 들어오면, 다시 그리지 않고 그
    칸만 빨갛게 표시하고 안내 문구로 바꿔 줍니다(칸을 비워서 다시 쓰게 함).
    elId 를 넘기지 않으면 선택형 질문의 공용 자유 입력칸(chatFreeInput)을
    가리킵니다 — 검진·영양제처럼 자기만의 자유 입력칸이 따로 있는
    단계에서는 그 id 를 넘겨서 씁니다. */
function chatFlagFreeText(msg, elId = 'chatFreeInput'){
  const el = document.getElementById(elId);
  if(!el) return;
  el.classList.add('err');
  el.value = '';
  el.placeholder = msg;
  el.focus();
}

/** "네/아니요" 류 질문에 문장으로 답했을 때 뜻을 알아냅니다.
    쉬운 단어 매칭이라 완벽하지 않지만, 못 알아들었을 때는 버튼으로도
    답할 수 있고 다시 물어보므로 안전합니다. */
function parseYesNo(raw){
  const NO  = ['아니요','아니','아뇨','안 할래요','안할래요','없어요','없습니다','없어','괜찮아요','필요없어요','필요 없어요','말고요','싫어요','아니오'];
  const YES = ['네','예','응','그래요','좋아요','있어요','있습니다','있어','함께요','같이요','해주세요','해줘요','필요해요','넣어주세요','넣어줘요'];
  if(NO.some(w => raw.includes(w))) return false;
  if(YES.some(w => raw.includes(w))) return true;
  return null;
}

/** 성별 질문에 문장으로 답했을 때 뜻을 알아냅니다. */
function parseSex(raw){
  if(/여성|여자|^여$/.test(raw)) return '여성';
  if(/남성|남자|^남$/.test(raw)) return '남성';
  return null;
}

/** 버튼 대신 문장으로 답했을 때의 처리. 뜻을 알아낸 뒤에는 버튼을
    눌렀을 때와 완전히 같은 처리 함수(chatSubmitReply 등)를 그대로
    불러서, 판단 로직이 두 군데로 나뉘지 않게 합니다. */
function chatSubmitFreeText(){
  const step = CHAT.step;
  const el = document.getElementById('chatFreeInput');
  const raw = el ? el.value.trim() : '';
  if(!raw) return;

  if(step === 'sex'){
    const v = parseSex(raw);
    if(v == null){ chatFlagFreeText('성별은 "남성" 또는 "여성"으로 답해 주세요'); return; }
    el.value = '';
    chatSubmitReply(v, raw);
    return;
  }
  if(['meal', 'examAsk', 'prodAsk', 'medAsk', 'prodMore', 'medMore'].includes(step)){
    const yn = parseYesNo(raw);
    if(yn == null){ chatFlagFreeText('"네" 또는 "아니요"로 답해 주세요'); return; }
    el.value = '';
    chatSubmitYesNo(yn, raw);
    return;
  }
  if(step === 'examGroups' || step === 'chronic'){
    const options = step === 'examGroups' ? EXAM.map(g => g.group) : CHRONIC;
    const matched = options.filter(o => raw.includes(o));
    if(!matched.length){
      if(/없|모름|모르겠|건너뛰/.test(raw)){
        CHAT.tempSelection = [];
        el.value = '';
        chatSubmitChipMulti(raw);
        return;
      }
      chatFlagFreeText(`해당하는 항목을 적어 주세요 (예: ${options[0]})`);
      return;
    }
    CHAT.tempSelection = [...new Set([...CHAT.tempSelection, ...matched])];
    el.value = '';
    chatSubmitChipMulti(raw);
    return;
  }
  if(step === 'summary'){
    if(parseYesNo(raw) === true || /결과|보여|보기|볼래/.test(raw)){
      el.value = '';
      chatFinish();
      return;
    }
    chatFlagFreeText('"네, 결과 보여주세요" 처럼 답하시면 바로 결과를 보여드려요');
    return;
  }
}

function chatSubmitText(){
  const step = CHAT.step;
  const el = document.getElementById('chatTextInput');
  const val = el ? el.value.trim() : '';
  const botText = chatBubbleText(step);
  let userText, confirmText, ref;
  if(step === 'name'){
    state.name = val;
    userText = val || '(건너뜀)';
    confirmText = val ? `"${val}"님으로 기록할게요.` : '이름은 남기지 않고 진행할게요.';
  }
  else if(step === 'age'){
    if(!val){ chatFlagRequired(); return; }
    state.age = val;
    userText = `${val}세`;
    confirmText = `나이 ${val}세로 기록했어요.`;
  }
  else if(step === 'examDate'){
    state.date = val;
    userText = val || '(건너뜀)';
    confirmText = val ? `검진일을 "${val}"(으)로 기록했어요.` : '검진일은 남기지 않고 넘어갈게요.';
  }
  /* 이름을 고치는 중이면 이미 등록해 둔 제품·약의 이름을 그 자리에서 바꿉니다.
     (평소처럼 draft 를 만들어 새로 밀어 넣으면 같은 제품이 두 개가 됩니다) */
  else if(step === 'prodName'){
    if(!val){ chatFlagRequired(); return; }
    const ed = editingStep('prodName');
    if(ed && state.products[ed.ref]) state.products[ed.ref].name = val;
    else CHAT.prodDraft = {name: val, items: [{}]};
    userText = val;
    ref = ed ? ed.ref : state.products.length;
    confirmText = ed
      ? `제품 이름을 "${val}"(으)로 고쳤어요.`
      : `"${val}" 제품으로 등록할게요. 이제 성분을 여쭤볼게요.`;
  }
  else if(step === 'medName'){
    if(!val){ chatFlagRequired(); return; }
    const ed = editingStep('medName');
    if(ed && state.meds[ed.ref]) state.meds[ed.ref].name = val;
    else CHAT.medDraft = {name: val, desc: ''};
    userText = val;
    ref = ed ? ed.ref : state.meds.length;
    confirmText = ed ? `약 이름을 "${val}"(으)로 고쳤어요.` : `"${val}" 약으로 등록할게요.`;
  }
  else if(step === 'medDesc'){
    const ed = editingStep('medDesc');
    const med = ed ? state.meds[ed.ref] : CHAT.medDraft;
    if(!med) return;
    const medName = med.name;
    med.desc = val;
    if(!ed){ state.meds.push(CHAT.medDraft); CHAT.medDraft = null; }
    userText = val || '(건너뜀)';
    ref = ed ? ed.ref : state.meds.length - 1;
    confirmText = val
      ? `"${medName}" 복용법을 "${val}"(으)로 기록했어요.`
      : `"${medName}" 약을 복용법 메모 없이 등록했어요.`;
  }
  else return;
  chatAdvance(step, botText, userText, confirmText, ref);
}

function chatSubmitSkip(){
  const step = CHAT.step;
  const botText = chatBubbleText(step);
  let confirmText = '', ref;
  if(step === 'name'){
    state.name = '';
    confirmText = '이름은 남기지 않고 진행할게요.';
  }
  else if(step === 'examDate'){
    state.date = '';
    confirmText = '검진일은 남기지 않고 넘어갈게요.';
  }
  else if(step === 'medDesc'){
    const ed = editingStep('medDesc');
    const med = ed ? state.meds[ed.ref] : CHAT.medDraft;
    if(!med) return;
    const medName = med.name;
    med.desc = '';
    if(!ed){ state.meds.push(CHAT.medDraft); CHAT.medDraft = null; }
    ref = ed ? ed.ref : state.meds.length - 1;
    confirmText = `"${medName}" 약을 복용법 메모 없이 등록했어요.`;
  }
  chatAdvance(step, botText, '(건너뜀)', confirmText, ref);
}

/** logText 를 따로 넘기면 그 문구를 대화 로그에 남깁니다 — 문장으로 답했을
    때(chatSubmitFreeText) 버튼 라벨 대신 사용자가 실제로 쓴 말을 그대로
    보여주기 위해서입니다. 버튼을 눌렀을 때는 넘기지 않으므로 그대로 동작합니다. */
function chatSubmitReply(value, logText){
  const step = CHAT.step;
  const botText = chatBubbleText(step);
  let confirmText = '';
  if(step === 'sex'){
    state.sex = value;
    confirmText = `성별을 "${value}"(으)로 기록했어요.`;
  }
  chatAdvance(step, botText, logText != null ? logText : value, confirmText);
}

function chatSubmitYesNo(yes, logText){
  const step = CHAT.step;
  const botText = chatBubbleText(step);
  let confirmText = '';
  if(step === 'meal'){
    state.countMeal = yes;
    confirmText = yes
      ? '식사에서 드시는 영양성분도 평균 추정치로 함께 계산할게요.'
      : '식사 추정치는 반영하지 않고 넘어갈게요.';
  }
  /* '있어요'를 '없어요'로 고친 경우에는, 그때 적어 둔 값과 그 질문에 딸린
     말풍선까지 함께 걷어냅니다 — 답은 '없어요'인데 아래에 수치가 그대로
     남아 있으면 어느 쪽이 맞는 값인지 알 수 없기 때문입니다. */
  else if(step === 'examAsk'){
    CHAT.wantsExam = yes;
    const undo = editingStep('examAsk') && !yes;
    if(undo){ state.exam = {}; CHAT.examQueue = []; chatDropAnswers(EDIT_SUBFLOW.examAsk); }
    confirmText = yes ? '건강검진 결과를 몇 가지 여쭤볼게요.'
                      : (undo ? '적어 주셨던 검진 결과는 지우고, 검진 결과 없이 진행할게요.' : '건강검진 결과 없이 진행할게요.');
  }
  else if(step === 'prodAsk'){
    CHAT.wantsProd = yes;
    const undo = editingStep('prodAsk') && !yes;
    if(undo){ state.products = []; CHAT.prodDraft = null; chatDropAnswers(EDIT_SUBFLOW.prodAsk); }
    confirmText = yes ? '지금 드시는 영양제를 등록할게요.'
                      : (undo ? '등록해 두셨던 영양제는 지우고 넘어갈게요.' : '영양제는 없는 것으로 하고 넘어갈게요.');
  }
  else if(step === 'medAsk'){
    CHAT.wantsMed = yes;
    const undo = editingStep('medAsk') && !yes;
    if(undo){ state.meds = []; CHAT.medDraft = null; chatDropAnswers(EDIT_SUBFLOW.medAsk); }
    confirmText = yes ? '복용 중인 약을 등록할게요.'
                      : (undo ? '등록해 두셨던 약은 지우고 넘어갈게요.' : '복용 중인 약은 없는 것으로 할게요.');
  }
  else if(step === 'prodMore'){
    CHAT.prodMoreYes = yes;
    confirmText = yes ? '다른 영양제도 이어서 등록할게요.' : '영양제 등록은 여기까지 할게요.';
  }
  else if(step === 'medMore'){
    CHAT.medMoreYes = yes;
    confirmText = yes ? '다른 약도 이어서 등록할게요.' : '약 등록은 여기까지 할게요.';
  }
  chatAdvance(step, botText, logText != null ? logText : (yes ? '네' : '아니요'), confirmText);
}

function chatToggleChip(value){
  CHAT.tempSelection = CHAT.tempSelection.includes(value)
    ? CHAT.tempSelection.filter(v => v !== value)
    : [...CHAT.tempSelection, value];
  rerenderChat();
}

function chatToggleChipNone(){
  CHAT.tempSelection = [];
  rerenderChat();
}

function chatSubmitChipMulti(logText){
  const step = CHAT.step;
  const botText = chatBubbleText(step);
  const picked = CHAT.tempSelection.slice();
  let confirmText;
  if(step === 'examGroups'){
    if(CHAT.editing){
      /* 항목을 고치는 중이면, 새로 고른 것만 물어봅니다 — 이미 수치를 적어
         둔 항목까지 전부 다시 물어보면 고치는 게 더 번거로워집니다.
         빼신 항목은 그때 적었던 수치와 말풍선을 함께 걷어냅니다. */
      const had = deriveExamGroupsFromState();
      const removed = had.filter(g => !picked.includes(g));
      removed.forEach(clearExamGroup);
      if(removed.length) chatDropAnswers(['examGroupDetail'], removed);
      CHAT.examQueue = picked.filter(g => !had.includes(g));
      confirmText = CHAT.examQueue.length
        ? `${CHAT.examQueue.join(', ')} 결과를 이어서 여쭤볼게요.`
        : (removed.length ? `${removed.join(', ')} 결과는 지웠어요.` : '고른 항목은 그대로예요.');
    } else {
      /* 사진에서 이미 채워진 항목은 큐에서 빼 둡니다 — 방금 읽어 들인 값을
         처음부터 다시 물어보면 사진을 올린 의미가 없습니다.
         (고치고 싶으면 그 말풍선의 '수정'을 누르면 됩니다) */
      CHAT.examQueue = picked.filter(g => !CHAT.importedGroups.includes(g));
      confirmText = CHAT.examQueue.length
        ? `${CHAT.examQueue.join(', ')} 결과를 순서대로 여쭤볼게요.`
        : (CHAT.importedGroups.length ? '검진표에서 읽은 값으로 충분해요. 다음으로 넘어갈게요.'
                                      : '검진 결과 항목은 넘어갈게요.');
    }
  }
  else if(step === 'chronic'){
    state.chronic = picked;
    confirmText = picked.length ? `${picked.join(', ')}을(를) 진단받으신 질환으로 기록했어요.` : '진단받은 만성질환은 없는 것으로 기록했어요.';
  }
  CHAT.tempSelection = [];
  CHAT.tempSeededFor = null;   // 다음에 이 단계에 다시 오면(재검토) 새로 채워 넣어야 하므로
  chatAdvance(step, botText, logText != null ? logText : (picked.length ? picked.join(', ') : '없음'), confirmText);
}

/** 방금 답한 검진 그룹에서 실제로 어떤 값이 채워졌는지, 항목별 표시용
    show() 함수 그대로(예: "혈압 132/80mmHg") 문장으로 짚어 줍니다 —
    문장에서 값을 뽑아 채운 경우 특히, 챗봇이 숫자를 제대로 이해했는지
    사용자가 다음 질문으로 넘어가기 전에 바로 확인할 수 있어야 하기
    때문입니다. */
function chatExamGroupConfirmText(groupName){
  const grp = EXAM.find(x => x.group === groupName);
  if(!grp) return '';
  const parts = grp.items
    .map(it => `${it.name} ${it.show(state.exam)}`)
    .filter(s => !/—$/.test(s));
  return parts.length
    ? `${groupName} 결과 ${parts.join(', ')}(으)로 기록했어요.`
    : `${groupName} 항목은 입력하신 값이 없어서 비워둘게요.`;
}

/** 사용자가 칸에 채워 넣은 값을 그대로 한 줄로 옮겨 적습니다 — 문장으로
    적지 않고 칸을 직접 채운 경우에도, 대화 기록에 '무엇을 넣었는지'가
    그대로 남아야 나중에 되짚어 볼 수 있기 때문입니다. */
function chatExamFieldsText(g){
  if(!g) return '';
  const parts = [];
  g.items.forEach(it => it.inputs.forEach(inp => {
    const el = document.querySelector(`#chatWidget [data-exam="${inp.key}"]`);
    if(!el || el.value === '') return;
    parts.push(`${inp.name || it.name} ${el.value}${inp.unit ? inp.unit : ''}`);
  }));
  return parts.join(', ');
}

/** rawText 를 넘기면(문장으로 답한 경우) 사용자가 쓴 문장을 그대로 대화에
    남깁니다. 칸을 직접 채운 경우에는 채운 값들을 그대로 옮겨 적습니다. */
function chatConfirmExamGroup(rawText){
  const step = CHAT.step;
  const name = CHAT.examQueue[0];
  const g = EXAM.find(x => x.group === name);
  const botText = chatBubbleText(step);
  const typed = (rawText && rawText.trim()) || chatExamFieldsText(g);
  /* 비운 칸은 값에서도 지웁니다 — 고치는 중에 잘못 넣은 값을 지울 수
     있어야 하기 때문입니다(처음 입력할 때는 어차피 없던 값이라 같습니다). */
  $$('#chatWidget [data-exam]').forEach(el => {
    if(el.value !== '') state.exam[el.dataset.exam] = el.value;
    else delete state.exam[el.dataset.exam];
  });
  const confirmText = chatExamGroupConfirmText(name);
  CHAT.examQueue.shift();
  chatAdvance(step, botText, typed || `${name} 결과 없음`, confirmText, name);
}

function chatConfirmProduct(rawText){
  const step = CHAT.step;
  const botText = chatBubbleText(step);
  const prodName = CHAT.prodDraft ? CHAT.prodDraft.name : '';
  const items = $$('#chatWidget [data-ing]').map(r => ({
    name  : r.querySelector('[data-iname]').value.trim(),
    amount: r.querySelector('[data-iamt]').value,
    unit  : r.querySelector('[data-iunit]').value,
  })).filter(i => i.name);
  CHAT.prodDraft.items = items;
  /* 성분을 고치는 중이면 원래 자리의 제품을 바꿔 끼웁니다(그냥 밀어 넣으면
     같은 제품이 하나 더 생깁니다). */
  const ed = editingStep('prodIngredients');
  let ref;
  if(ed && state.products[ed.ref]){ state.products[ed.ref] = CHAT.prodDraft; ref = ed.ref; }
  else { state.products.push(CHAT.prodDraft); ref = state.products.length - 1; }
  CHAT.prodDraft = null;
  const parts = items.map(i => `${i.name} ${i.amount}${i.unit}`.trim());
  const confirmText = parts.length
    ? `"${prodName}"에 ${parts.join(', ')}(으)로 기록했어요.`
    : `"${prodName}"은 성분 없이 등록했어요.`;
  const typed = (rawText && rawText.trim()) || parts.join(', ');
  chatAdvance(step, botText, typed || '성분 없음', confirmText, ref);
}

/** '결과 보기' — 폼의 #go-report 와 완전히 같은 일을 합니다. */
function chatFinish(){
  clearTimeout(saveTimer); doSave();
  analyze(snapshot());
}

/* ---- 초기화 · 처음부터 다시 입력 -------------------------------------------
   '전체 초기화'는 되돌릴 수 없으므로, 누르자마자 지우지 않고 확인 문구를
   한 번 더 보여줍니다. '처음부터 다시 입력'은 그 반대로 즉시 실행해도
   안전합니다 — state 를 전혀 건드리지 않기 때문입니다. */
function chatRequestClear(){
  CHAT.confirmClear = true;
  rerenderChat();
}
function chatCancelClear(){
  CHAT.confirmClear = false;
  rerenderChat();
}
function chatConfirmClear(){
  clearInputState();
  resetChat();
  queueSave();
  rerenderChat();
}


/* =========================================================================
   [H] 상태 · 이벤트 · 시작
   ========================================================================= */

/** 사용자가 입력한 값 = 서버로 보내는 것 (Input) */
const state = {
  /* sex 는 일부러 빈 값입니다. 기본값을 남성으로 두면 사용자가 고르지 않은 채
     남성 기준으로 계산되어 버립니다(혈색소·허리둘레·γ-GTP 판정이 달라집니다). */
  name:'', age:'', sex:'', date:new Date().toISOString().slice(0, 10),
  exam:{}, chronic:[], meds:[], products:[], countMeal:true,
};

/** 화면에만 있는 값 = 서버로 보내지 않는 것 */
const UI = {
  view   : 'loading',   // loading · input · analyzing · report · history · error
  sample : false,       // 샘플 리포트를 보고 있는지 (로그인 필수 버전에서는 항상 false)
  deleteAsk  : null,    // 지난 리포트에서 '삭제'를 눌러 확인을 기다리는 리포트 id
  deleteError: null,    // 방금 지우기에 실패한 이유
  report : null,        // 서버가 준 결과
  error  : null,
  retryAction: null,    // 오류 화면의 '다시 시도'가 부를 함수. 매번 상황에 맞게 지정합니다.
  pendingAfterLogin: null,  // 로그인 모달이 닫힌 뒤 이어서 할 일 (예: 끊겼던 분석 재시도)
  loadingMessage: '',
  historyList: null,
  confirmClear: false,  // 폼 화면에서 '전체 초기화'를 눌러 확인을 기다리는 중인지.
                        // (대화형 쪽은 CHAT.confirmClear 가 따로 들고 있습니다)
  inputMode: 'chat',    // 'chat' | 'form' — 입력 화면을 대화형으로 볼지 폼으로 볼지.
                         // 로그인 직후에는 대화형이 기본값이고, 사용자가 화면 위 토글로
                         // 언제든 자유롭게 바꿀 수 있습니다. 둘 다 같은 state 를 채웁니다.
};

/** 부팅 시 서버에서 받아 두는 것 */
const APP = {hints: []};

/* =========================================================================
   [블록 -6] 인증 상태 — 로그인 여부와 모달의 열림 상태
   -------------------------------------------------------------------------
   이 서비스는 로그인해야만 쓸 수 있습니다. AUTH.user 가 null 이면
   #app 을 inert(비활성) 로 만들고 그 위에 로그인 모달을 띄웁니다.
   ========================================================================= */
const AUTH = {
  user : null,     // {name, email} | null
  gateOpen: false,
  mode : 'login',   // 'login' | 'signup'
  message: '',      // 모달 위에 보여줄 안내 문구 (세션 만료 등 상황별로 다릅니다)
  formError: '',
  busy: false,
  /* 입력칸 값을 여기 함께 저장해 둡니다. paintAuthModal() 은 실패했을 때도
     폼 전체를 다시 그리는데, 그때 이 값으로 채워 넣지 않으면 비밀번호를
     한 번 잘못 입력했을 뿐인데 이메일까지 지워져 처음부터 다시 써야 합니다. */
  name: '', email: '', pw: '',
};

/* =========================================================================
   [블록 -6A] 세션 저장소 — 로그인한 사용자를 브라우저에도 한 벌 둡니다
   -------------------------------------------------------------------------
   진짜 세션은 서버가 쿠키(myherb_sid)로 들고 있습니다. 여기 담는 것은 그
   사본입니다. 사본을 두는 이유는 하나뿐입니다 — 새로고침했을 때
   GET /api/me 응답이 올 때까지 상단바가 비어 있다가 이름이 뒤늦게 나타나는
   깜빡임을 없애기 위해서입니다.

   ★ 그래서 이 값은 '표시용'입니다. 이 값이 있다고 해서 로그인된 것으로
     치지 않습니다. 화면을 열 때 서버에 반드시 다시 물어보고(me), 서버가
     아니라고 하면 이 사본을 지웁니다. 브라우저 저장소는 사용자가 직접
     고칠 수 있으므로 권한의 근거로 쓰면 안 됩니다.

   sessionStorage 는 탭 하나에만 살아 있고 탭을 닫으면 사라집니다.
   시크릿 모드나 저장소가 막힌 환경에서는 접근 자체가 예외를 던지므로
   전부 try 로 감쌌습니다 — 실패해도 화면은 그대로 동작합니다.
   ========================================================================= */
const SESSION_KEY = 'myherb.user';

/** 로그인 성공·로그아웃 때마다 부릅니다. user 가 null 이면 지웁니다. */
function saveSessionUser(user){
  try {
    if(user) sessionStorage.setItem(SESSION_KEY, JSON.stringify(user));
    else     sessionStorage.removeItem(SESSION_KEY);
  } catch(e){
    console.warn('[session] 브라우저 저장소를 쓸 수 없습니다. 이름이 조금 늦게 뜰 뿐 동작에는 지장 없습니다.', e);
  }
}

/** 저장해 둔 사본. 모양이 깨져 있으면 없는 것으로 봅니다. */
function loadSessionUser(){
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if(!raw) return null;
    const u = JSON.parse(raw);
    return (u && typeof u === 'object' && u.email) ? u : null;
  } catch(e){
    return null;
  }
}

/* =========================================================================
   [블록 -9] 대화형 입력 상태 — 폼과 같은 state 를 채우는 또 하나의 방식
   -------------------------------------------------------------------------
   여기 담긴 값은 전부 '아직 진행 중인 대화'에 관한 것일 뿐입니다.
   실제로 서버에 보내는 값은 언제나 state 하나뿐입니다 — 챗봇이 한
   질문에 답할 때마다 곧바로 state 를 채우기 때문에, 폼으로 화면을
   바꿔도 지금까지 대화로 답한 내용이 그대로 보입니다.
   ========================================================================= */
const CHAT = {
  log : [],              // 끝난 대화. [{role:'bot'|'user', text}]
  step: 'name',          // 지금 사용자가 답해야 할 질문
  wantsExam: null, wantsProd: null, wantsMed: null,   // 이 섹션을 입력하겠다고 했는지
  prodMoreYes: null, medMoreYes: null,                // '다른 것도 있나요?' 답
  tempSelection: [],     // 다중 선택 칩(검진 항목 · 만성질환)에서 지금 고른 것
  examQueue: [],         // 고른 검진 그룹 중 아직 안 물어본 것들 (앞에서부터 하나씩 뺍니다)
  prodDraft: null,       // 지금 입력 중인 영양제 {name, items}
  medDraft : null,       // 지금 입력 중인 약 {name, desc}
  examFile: null,        // 사용자가 고른 검진표 사진. 결과보기 때 함께 보냅니다.
                         // (서버에 저장하지 않으므로 여기서만 들고 있습니다)
  confirmClear: false,   // '전체 초기화' 버튼을 눌러서 확인을 기다리는 중인지 (대화형)
  tempSeededFor: null,   // 다중 선택 칩에 이미 있던 값을 한 번 채워 넣은 단계 이름
                          // (계속 다시 채우면 사용자가 일부러 다 지워도 되돌아가 버립니다)
  editing: null,         // 이전 답변을 고치는 중일 때 {index, step, ref, returnStep, saved}

  /* ---- 검진표 사진 판독 ---------------------------------------------------
     ＋ 버튼으로 검진 결과지 사진을 올리면 서버가 읽어서 값을 채워 줍니다.
     그렇게 이미 채워진 질문은 다시 묻지 않기 위해, 무엇이 채워졌는지를
     여기에 기억해 둡니다. */
  imgBusy: false,        // 판독 중인지 (버튼을 잠그고 '읽는 중' 표시)
  imgError: null,        // 방금 판독이 실패한 이유 (사용자에게 그대로 보여 줍니다)
  imported: null,        // 판독에 성공했으면 {source, count, at}
  importedGroups: [],    // 사진에서 값이 채워진 검진 그룹 이름
  known: [],             // 사진 덕분에 물어보지 않아도 되는 단계 이름들
};

/** 답을 바꾸면 새로 물어봐야 할 것이 생기는 질문과, 그때 딸려 오는 질문들.
    여기 없는 질문(이름·나이·검진 수치 등)은 값 하나만 바뀌므로, 고치고 나면
    곧바로 원래 보고 있던 자리로 돌아갑니다. */
const EDIT_SUBFLOW = {
  examAsk   : ['examGroups', 'examGroupDetail', 'examDate'],
  examGroups: ['examGroupDetail'],
  prodAsk   : ['prodName', 'prodIngredients', 'prodMore'],
  medAsk    : ['medName', 'medDesc', 'medMore'],
};

/** '수정' 버튼을 붙일 답변들.
    '더 등록하시겠어요?'(prodMore·medMore)는 값이 아니라 그때그때의 진행
    선택일 뿐이라 뺐습니다. 영양제나 약을 더 넣고 싶으면 '영양제가
    있으신가요?'(prodAsk) 답을 수정하면 그 부분만 다시 물어봅니다. */
const EDITABLE_STEPS = ['name', 'age', 'sex', 'meal', 'examAsk', 'examGroups',
  'examGroupDetail', 'examDate', 'chronic', 'prodAsk', 'prodName',
  'prodIngredients', 'medAsk', 'medName', 'medDesc'];

/** 새 리포트를 시작하거나 로그아웃할 때, 또는 '처음부터 다시 입력'을 눌렀을 때
    — 대화 진행 상태만 초기화합니다. state(실제 입력값)는 건드리지 않으므로,
    '처음부터 다시 입력'에 쓰면 답한 내용은 남은 채로 질문만 다시 보여줄 수 있습니다. */
function resetChat(){
  CHAT.log = [];
  CHAT.step = 'name';
  CHAT.wantsExam = CHAT.wantsProd = CHAT.wantsMed = null;
  CHAT.prodMoreYes = CHAT.medMoreYes = null;
  CHAT.tempSelection = [];
  CHAT.examQueue = [];
  CHAT.prodDraft = null;
  CHAT.medDraft = null;
  CHAT.confirmClear = false;
  CHAT.tempSeededFor = null;
  CHAT.editing = null;
  CHAT.imgBusy = false;
  CHAT.imgError = null;
  CHAT.examFile = null;
  CHAT.imported = null;
  CHAT.importedGroups = [];
  CHAT.known = [];
}

/** 입력값을 전부 빈 값으로 되돌립니다. state 의 처음 모양과 똑같아야 합니다.
    (로그아웃할 때, 그리고 대화형 화면의 '전체 초기화'에서 함께 씁니다) */
function clearInputState(){
  Object.assign(state, {
    name:'', age:'', sex:'', date:new Date().toISOString().slice(0, 10),
    exam:{}, chronic:[], meds:[], products:[], countMeal:true,
  });
}

const $  = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const app = () => document.getElementById('app');

/** 입력값을 그대로 복사합니다(서버로 보낼 때 화면 상태가 섞이지 않도록). */
const snapshot = () => JSON.parse(JSON.stringify({
  name:state.name, age:state.age, sex:state.sex, date:state.date,
  exam:state.exam, chronic:state.chronic, meds:state.meds,
  products:state.products, countMeal:state.countMeal,
}));

/* ---- 상태 ↔ 입력칸 ------------------------------------------------------- */
function fillForm(){
  $('#f-name').value = state.name;
  $('#f-age').value  = state.age;
  $('#f-sex').value  = state.sex;
  $('#f-date').value = state.date;
  $('#f-meal').checked = state.countMeal;
  $$('[data-exam]').forEach(el => el.value = state.exam[el.dataset.exam] ?? '');
  $$('[data-chronic]').forEach(el => el.checked = state.chronic.includes(el.dataset.chronic));
  $('#med-list').innerHTML  = state.meds.map(medRow).join('');
  $('#prod-list').innerHTML = (state.products.length ? state.products : [{}]).map(prodCard).join('');
  refreshForm();
}

function readForm(){
  state.name = $('#f-name').value.trim();
  state.age  = $('#f-age').value;
  state.sex  = $('#f-sex').value;
  state.date = $('#f-date').value;
  state.countMeal = $('#f-meal').checked;

  state.exam = {};
  $$('[data-exam]').forEach(el => state.exam[el.dataset.exam] = el.value);
  state.chronic = $$('[data-chronic]:checked').map(el => el.dataset.chronic);

  state.meds = $$('[data-med]').map(r => ({
    name: r.querySelector('[data-mname]').value.trim(),
    desc: r.querySelector('[data-mdesc]').value.trim(),
  })).filter(m => m.name);

  state.products = $$('[data-prod]').map(c => ({
    name : c.querySelector('[data-pname]').value.trim(),
    items: [...c.querySelectorAll('[data-ing]')].map(r => ({
      name  : r.querySelector('[data-iname]').value.trim(),
      amount: r.querySelector('[data-iamt]').value,
      unit  : r.querySelector('[data-iunit]').value,
    })).filter(i => i.name),
  })).filter(p => p.name || p.items.length);
}

/** 성분 이름이 기준표에 있는지 — 입력하는 즉시 알려 줍니다.
    추천 목록(APP.hints)에 있으면 '기준 있음'. 목록은 서버가 내려줍니다. */
const HINT_SET = new Set();
const hintKey  = s => String(s || '').toLowerCase().replace(/[\s\-_·・.()（）]/g, '');
function rebuildHints(){
  HINT_SET.clear();
  APP.hints.forEach(h => HINT_SET.add(hintKey(h)));
}

function refreshIngFlags(){
  $$('[data-ing]').forEach(row => {
    const name = row.querySelector('[data-iname]').value.trim();
    const flag = row.querySelector('[data-iflag]');
    if(!flag) return;
    if(!name){ flag.className = 'ing-flag idle'; flag.textContent = ''; return; }
    if(HINT_SET.has(hintKey(name))){
      flag.className = 'ing-flag ok';  flag.textContent = '✓ 있음';
      flag.title = '기준값이 등록된 성분입니다. 권장·상한과 비교합니다.';
    } else {
      flag.className = 'ing-flag no';  flag.textContent = '? 없음';
      flag.title = '기준값이 없는 성분입니다. 합산은 되지만 권장·상한 비율은 계산하지 않습니다. 이름 표기를 확인해 보세요.';
    }
  });
}

/** 입력칸은 그대로 두고, 요약·배지·버튼 상태만 갱신합니다.
    (다시 그리면 타이핑 중 커서가 날아갑니다) */
function refreshForm(){
  /* 대화형 화면 등 폼 자체가 없는 화면에서 입력 이벤트가 올라와도
     조용히 넘어갑니다(예: 챗봇의 성분 입력칸에서 타이핑할 때). */
  if(!document.getElementById('go-report')) return;
  readForm();

  $$('.fm-tag').forEach(l => l.classList.toggle('on', l.querySelector('input').checked));
  $$('.fm-grp').forEach(g => {
    const n = [...g.querySelectorAll('[data-exam]')].filter(el => el.value !== '').length;
    const b = g.querySelector('[data-count]');
    if(b){ b.textContent = n ? `입력 ${n}` : ''; b.classList.toggle('on', !!n); }
  });
  refreshIngFlags();

  /* 섹션 머리의 요약 배지 — 접혀 있어도 뭐가 들어 있는지 보이게 */
  const items    = state.products.reduce((a, p) => a + p.items.length, 0);
  const examCnt  = Object.values(state.exam).filter(v => v !== '' && v != null).length;
  const setBadge = (id, text) => {
    const b = document.querySelector(`#sec-${id} [data-secbadge]`);
    if(!b) return;
    b.textContent = text || '';
    b.hidden = !text;
  };
  const hasBasic = !!(String(state.age).trim() && state.sex);
  setBadge('profile',  hasBasic ? `${state.age}세 · ${state.sex}` : '');
  setBadge('exam',     examCnt ? `${examCnt}개 항목` : '');
  setBadge('products', items ? `${state.products.length}종 · 성분 ${items}개` : '');
  setBadge('meds',     state.meds.length ? `${state.meds.length}건` : '');

  /* 결과를 볼 수 있는 조건 —
       ① 나이와 성별은 반드시 필요합니다(권장량과 판정 기준이 여기서 갈립니다).
       ② 계산할 거리가 하나는 있어야 합니다.
          영양제를 넣었거나, 아니면 식사 평균 추정치로 계산하겠다고 켜 두었거나.
     둘 다 없으면(영양제도 없고 식사 추정도 끄면) 더할 것이 없습니다. */
  const hasSource = items > 0 || state.countMeal;
  const ready     = hasBasic && hasSource;

  const bits = [];
  if(hasBasic)          bits.push(`${state.age}세 · ${state.sex}`);
  if(items)             bits.push(`영양제 ${state.products.length}종 · 성분 ${items}개`);
  if(state.meds.length) bits.push(`약 ${state.meds.length}건`);
  if(examCnt)           bits.push(`검진 ${examCnt}개 항목`);

  let line, hint;
  if(!hasBasic){
    line = '나이와 성별을 입력해 주세요';
    hint = '이 두 가지만 있으면 식사 기준으로 부족한 성분을 찾아 드립니다.';
  } else if(!hasSource){
    line = bits.join(' · ');
    hint = '영양제를 넣거나, 기본 정보의 「식사 평균 추정치로 함께 계산」을 켜 주세요.';
  } else if(!items){
    line = bits.join(' · ');
    hint = '식사 평균 추정치로 계산합니다. 복용 중인 영양제를 넣으면 합산량과 상한도 함께 봅니다.';
  } else {
    line = bits.join(' · ');
    hint = '결과 보기를 누르면 분석을 시작합니다.';
  }
  $('#sum-line').textContent = line;
  $('#sum-hint').textContent = hint;
  $('#go-report').disabled   = !ready;
  /* 버튼 이름은 늘 '결과 보기' 입니다 — 대화형 화면과 같은 말을 씁니다.
     (예전에는 영양제를 안 넣었을 때만 '식사 기준으로 확인하기' 로 바뀌어서,
      같은 일을 하는 버튼이 화면마다 다른 이름으로 보였습니다) */

  queueSave();
}


/* ---- 자동 저장 -----------------------------------------------------------
   입력이 멈추고 1.2초 뒤에 서버로 보냅니다. 글자마다 보내지 않기 위해서입니다.
   저장에 실패해도 입력을 막지 않습니다 — 표시만 하고 다음 저장 때 다시 시도합니다. */
let saveTimer = null, saveSeq = 0;

function setSaveState(text, cls){
  const el = document.getElementById('savestate');
  if(el){ el.textContent = text; el.className = 'savestate' + (cls ? ' ' + cls : ''); }
}

function queueSave(){
  if(UI.sample) return;                       // 샘플을 보는 중에는 저장하지 않습니다
  clearTimeout(saveTimer);
  saveTimer = setTimeout(doSave, 1200);
}

async function doSave(){
  const seq  = ++saveSeq;
  const body = snapshot();
  /* 아무것도 안 적은 상태는 저장하지 않습니다 */
  if(!body.age && !body.sex && !body.products.length && !body.meds.length && !body.name) return;
  setSaveState('저장 중…');
  try {
    await API.saveDraft(body);
    if(seq === saveSeq) setSaveState('저장됨', 'ok');
  } catch(e){
    if(seq !== saveSeq) return;
    setSaveState(e.code === 'LOGIN_REQUIRED' ? '로그인하면 저장됩니다' : '저장하지 못했습니다', 'err');
  }
}


/* ---- 화면 전환 -----------------------------------------------------------
   주소(history)에도 남겨서 브라우저 뒤로가기가 '입력 수정'과 똑같이 동작합니다.
   폰에서 뒤로가기 제스처로 사이트를 나가버리는 일을 막습니다. */
/* 주소 기록은 '있으면 좋은 것'이지 '없으면 안 되는 것'이 아닙니다.
   샌드박스된 iframe(미리보기 창 등)이나 일부 브라우저의 file:// 에서는
   브라우저가 history 조작을 막고 예외를 던집니다. 그 예외가 화면 전환을
   멈추게 하면 안 되므로 여기서 삼킵니다.
   막힌 환경에서는 뒤로가기만 동작하지 않고 나머지는 그대로 동작합니다. */
let historyOK = true;
function nav(method, view, url){
  if(!historyOK) return;
  try { history[method]({view}, '', url); }
  catch(e){
    historyOK = false;
    console.warn('[history] 이 환경에서는 주소를 바꿀 수 없어 뒤로가기가 동작하지 않습니다.',
                 e && e.message);
  }
}

const HASH_OF = {report:'#report', history:'#history', home:'#home'};
function go(view, {push = true} = {}){
  /* 화면을 옮기면 폼의 '정말 지울까요?' 는 없던 일이 됩니다 — 확인 카드만
     남겨 둔 채 다른 화면에 갔다가 돌아왔을 때 그대로 떠 있으면, 무엇을
     지우려던 참이었는지 모른 채 '네' 를 누르게 됩니다. */
  UI.confirmClear = false;
  UI.view = view;
  if(push){
    const url = HASH_OF[view] || '#input';
    let cur = '';
    try { cur = location.hash; } catch(e){ /* 접근이 막힌 환경 */ }
    if(cur !== url) nav('pushState', view, url);
  }
  paint();
}

function paint(){
  try { paintView(); }
  catch(e){
    /* 그리다 실패해도 빈 화면을 남기지 않습니다.
       (예: 서버가 규격에 없는 값을 보내 렌더가 멈춘 경우) */
    console.error('[paint] 화면을 그리지 못했습니다.', e);
    UI.error = {code:'RENDER', message:'화면을 그리는 중 문제가 생겼습니다.', detail:String(e && e.message || e)};
    UI.view  = 'error';
    app().innerHTML = screenError(UI.error, '다시 시도');
  }
}

function paintView(){
  const v = UI.view;
  if(v === 'loading')   { app().innerHTML = screenLoading(UI.loadingMessage); return; }
  if(v === 'analyzing') { app().innerHTML = screenAnalyzing(); startStepTicker(); return; }
  if(v === 'error')     { app().innerHTML = screenError(UI.error, UI.retryLabel); return; }
  if(v === 'report')    { app().innerHTML = reportHtml(UI.report); window.scrollTo(0, 0); return; }
  if(v === 'history')   { app().innerHTML = renderHistory(); window.scrollTo(0, 0); return; }
  if(v === 'home')      { app().innerHTML = screenHome(); window.scrollTo(0, 0); return; }

  /* 입력 화면 — 대화형(chat)이 기본값이고, 위 토글로 폼(form)과 자유롭게
     오갈 수 있습니다. 어느 쪽이든 채우는 대상은 같은 state 하나입니다. */
  if(UI.inputMode === 'chat'){
    app().innerHTML = renderChatScreen();
    return;
  }
  app().innerHTML = renderInputScreen();
  fillForm();
  const to  = UI.focus; UI.focus = null;
  const sec = to && document.getElementById('sec-' + to);
  if(!sec){ window.scrollTo(0, 0); return; }

  sec.open = true;
  if(to === 'exam') $$('#sec-exam .fm-grp').forEach(g => { if(g.querySelector('.cnt.on')) g.open = true; });
  try { sec.scrollIntoView({behavior:'smooth', block:'start'}); } catch(e){ /* 구형 브라우저 */ }
  sec.classList.add('fm-focus');
  setTimeout(() => sec.classList.remove('fm-focus'), 1600);
  const first = sec.querySelector('input:not([type=checkbox]), select');
  if(first && to !== 'exam') setTimeout(() => first.focus(), 400);
}


/* =========================================================================
   [블록 -8] 상단바 · 로그인 모달 그리기
   -------------------------------------------------------------------------
   #topbar 와 #authModal 은 #app 과 별도의 자리입니다. paintView() 가
   화면(입력→분석중→리포트)을 바꿀 때마다 다시 그리지 않고, 로그인 상태가
   바뀔 때만 따로 다시 그립니다.
   ========================================================================= */
/** 로그인 전에도 상단바는 늘 떠 있습니다 — 로그인하지 않은 사람도 언제든
    'MyHerb' 이름을 눌러 메인 화면으로 돌아가거나 로그인·회원가입을 시작할
    수 있어야 하기 때문입니다(로그인 자체는 메인 화면에서 사용자가 골라야
    합니다). 로그인한 뒤에는 오른쪽이 계정 메뉴로 바뀝니다. */
function paintTopbar(){
  const el = document.getElementById('topbar');
  if(!el) return;
  el.hidden = false;
  const right = AUTH.user
    ? `<div class="tb-acct">
        <button type="button" class="tb-name" data-act="acct-menu">${esc(AUTH.user.name || AUTH.user.email)} ▾</button>
        <div class="tb-menu" id="acctMenu" hidden>
          <a href="#" data-act="history">지난 리포트</a>
          <a href="#" data-act="logout">로그아웃</a>
        </div>
      </div>`
    : `<div class="tb-guest">
        <button type="button" class="btn-line sm" data-act="login">로그인</button>
        <button type="button" class="btn-solid sm" data-act="signup">회원가입</button>
      </div>`;
  el.innerHTML = `<div class="tb-inner">
    <button type="button" class="tb-logo-btn" data-act="home" title="메인 화면으로 이동">MyHerb</button>
    ${right}
  </div>`;
}

/** 로그인 전에는 #app 을 inert 로 만들어, 뒤에 흐릿하게 보이는 입력화면을
    마우스로도 키보드로도 건드릴 수 없게 막습니다. */
function openAuthGate({mode = 'login', message = ''} = {}){
  AUTH.gateOpen  = true;
  AUTH.mode      = mode;
  AUTH.message   = message;
  AUTH.formError = '';
  AUTH.busy      = false;
  AUTH.name = ''; AUTH.email = ''; AUTH.pw = '';
  const appEl = app();
  if(appEl) appEl.inert = true;
  paintAuthModal(true);
}

function closeAuthGate(){
  AUTH.gateOpen = false;
  const appEl = app();
  if(appEl) appEl.inert = false;
  paintAuthModal();
}

function renderAuthModal(){
  const m = AUTH.mode === 'signup' ? 'signup' : 'login';
  const defaultMsg = m === 'signup'
    ? '계정을 만들면 입력한 내용과 지난 리포트를 이어서 보실 수 있습니다.'
    : '입력하신 내용과 지난 리포트를 이어서 보려면 로그인해 주세요.';
  return `<div class="modal-scrim">
    <div class="modal-card" role="dialog" aria-modal="true" aria-label="${m === 'signup' ? '회원가입' : '로그인'}">
      <div>
        <span class="h2">${m === 'signup' ? '회원가입' : '로그인'}</span>
        <span class="sub">${esc(AUTH.message || defaultMsg)}</span>
      </div>
      <form id="authForm" class="fm" style="padding:0;gap:12px">
        ${m === 'signup' ? `<label class="fm-f"><span>이름</span><input type="text" id="au-name" autocomplete="name" required placeholder="홍길동" value="${esc(AUTH.name)}"></label>` : ''}
        <label class="fm-f"><span>이메일</span><input type="email" id="au-email" autocomplete="email" required placeholder="you@example.com" value="${esc(AUTH.email)}"></label>
        <label class="fm-f"><span>비밀번호</span><input type="password" id="au-pw" autocomplete="${m === 'signup' ? 'new-password' : 'current-password'}" required minlength="4" placeholder="4자 이상" value="${esc(AUTH.pw)}"></label>
        ${AUTH.formError ? `<div class="errbox" style="max-width:none">${esc(AUTH.formError)}</div>` : ''}
        <button type="submit" class="fm-go" style="align-self:stretch;justify-content:center" ${AUTH.busy ? 'disabled' : ''}>
          ${AUTH.busy ? '처리 중…' : (m === 'signup' ? '회원가입' : '로그인')}
        </button>
      </form>
      <div style="text-align:center">
        ${m === 'signup'
          ? `<a class="link" href="#" data-act="auth-switch" data-mode="login">이미 계정이 있으신가요? 로그인</a>`
          : `<a class="link" href="#" data-act="auth-switch" data-mode="signup">계정이 없으신가요? 회원가입</a>`}
      </div>
    </div>
  </div>`;
}

/* focusFirst 는 모달을 '새로 열었을 때'나 '로그인 ↔ 회원가입 전환'처럼
   사용자가 아직 아무 입력도 하지 않은 순간에만 true 로 넘겨 주세요.
   제출 중(busy)이나 실패(오류) 뒤에 다시 그릴 때는 포커스를 건드리지
   않아야, 사용자가 막 다음 칸으로 넘어가려는 순간과 겹쳐 입력이 엉뚱한
   칸에 들어가는 일이 없습니다.
   ★ 포커스는 setTimeout 없이 곧바로 겁니다. 예전에는 50ms 뒤로 미뤄
   뒀었는데, 그 지연 시간 동안 사용자(또는 자동화 테스트)가 이미 다음
   칸에 입력을 시작해 버리면 그 입력이 다시 포커스를 빼앗아 온 첫 번째
   칸으로 끼어드는 경합이 실제로 재현됐습니다. innerHTML 로 넣은 요소는
   그 즉시 포커스를 걸 수 있으므로 지연이 필요하지 않습니다. */
function paintAuthModal(focusFirst){
  const root = document.getElementById('authModal');
  if(!root) return;
  root.innerHTML = AUTH.gateOpen ? renderAuthModal() : '';
  if(AUTH.gateOpen && focusFirst){
    const first = document.getElementById(AUTH.mode === 'signup' ? 'au-name' : 'au-email');
    if(first) first.focus();
  }
}

/** 로그인/회원가입에 성공한 뒤 — 저장된 입력을 이어받고,
    끊겼던 작업(pendingAfterLogin)이 있으면 그걸 이어서 합니다. */
async function afterLogin(){
  try {
    const draft = await API.loadDraft();
    if(draft) Object.assign(state, draft);
  } catch(e){
    console.warn('[draft] 로그인 직후 불러오기 실패.', e);
  }
  if(UI.pendingAfterLogin){
    /* 세션이 끊겨서 다시 로그인한 경우입니다. 하던 일(대개 끊겼던 분석)을
       그대로 이어서 합니다 — 여기서 메인 화면으로 보내 버리면 사용자가
       방금 하던 작업을 잃습니다. */
    const fn = UI.pendingAfterLogin;
    UI.pendingAfterLogin = null;
    await fn();
  } else {
    /* 평범하게 로그인·회원가입한 경우입니다. 메인 화면으로 보냅니다.
       (입력 화면으로 곧장 던져 넣지 않는 이유 — 방금 로그인한 사람은
        '지난 리포트 보기'로 가고 싶을 수도, 새로 입력하고 싶을 수도
        있습니다. 메인 화면에 두 갈래가 다 있으므로 거기서 고르게 합니다.) */
    go('home');
  }
}

async function showHistory(){
  UI.loadingMessage = '지난 리포트를 불러오는 중입니다.';
  UI.view = 'loading';
  UI.deleteAsk = UI.deleteError = null;   // 목록을 새로 열 때는 확인 중이던 것도 없던 일로
  paint();
  try {
    const res = await API.listReports();
    UI.historyList = res.reports || [];
    go('history');
  } catch(e){
    UI.error = e;
    UI.retryLabel = '다시 불러오기';
    UI.retryAction = showHistory;
    UI.view = 'error';
    paint();
  }
}

/** 리포트 하나 지우기. 카드 안에서 '지우기'를 눌렀을 때만 여기까지 옵니다.
    -------------------------------------------------------------------------
    목록을 통째로 다시 불러오지 않고 화면에서 그 줄만 걷어냅니다 — 지운
    직후에 목록이 깜빡이며 다시 그려지면, 방금 무엇을 지웠는지 눈으로
    따라가기 어렵습니다. */
async function deleteReport(id){
  UI.deleteError = null;
  try {
    await API.deleteReport(id);
    UI.historyList = (UI.historyList || []).filter(r => r.id !== id);
  } catch(e){
    /* 이미 지워진 것(404)이라면 화면에서도 없애는 게 맞습니다 —
       목록에만 남아 있는 유령 줄을 그대로 두면 눌러도 아무 일이 없습니다. */
    if(e.code === 'HTTP_404') UI.historyList = (UI.historyList || []).filter(r => r.id !== id);
    else UI.deleteError = e.message || '잠시 후 다시 시도해 주세요.';
  } finally {
    UI.deleteAsk = null;
    paint();
  }
}

async function openReport(id){
  UI.loadingMessage = '리포트를 불러오는 중입니다.';
  UI.view = 'loading';
  paint();
  try {
    const report = await API.getReport(id);
    if(report.input) Object.assign(state, report.input);   // 입력 수정을 누르면 이 리포트 기준으로
    UI.report = report;
    UI.sample = false;
    go('report');
  } catch(e){
    UI.error = e;
    UI.retryLabel = '다시 불러오기';
    UI.retryAction = () => openReport(id);
    UI.view = 'error';
    paint();
  }
}

/** 화면 전체를 로그인 전 상태로 되돌립니다. 계정이 바뀌었는데 이전 사람이
    입력하던 내용이 남아 있으면 안 되므로 state 도 함께 비웁니다. */
function resetToGuest(){
  clearInputState();
  UI.report = null;
  UI.historyList = null;
  UI.deleteAsk = UI.deleteError = null;
  UI.sample = false;
  UI.inputMode = 'chat';   // 다음 사람이 로그인했을 때도 대화형이 기본값입니다
  resetChat();
}

/** 분석 중의 단계 표시를 순서대로 켭니다. */
let stepTimer = null;
function startStepTicker(){
  clearInterval(stepTimer);
  let i = 0;
  stepTimer = setInterval(() => {
    const lis = $$('#an-steps li');
    if(!lis.length){ clearInterval(stepTimer); return; }
    if(i < lis.length - 1){
      lis[i].classList.remove('on'); lis[i].classList.add('done');
      i++; lis[i].classList.add('on');
    }
  }, 7000);
}

/** 리포트를 접힘 상태를 지키며 다시 그립니다. */
function rerenderReport(){
  const open = {};
  $$('#app details[data-k]').forEach(d => open[d.dataset.k] = d.open);
  /* #app 을 통째로 innerHTML 로 다시 그리면 화면이 맨 위로 튀어 버립니다.
     보고 있던 자리를 유지한 채 내용만 바뀌어야 하므로, 다시 그리기 전
     스크롤 위치를 기억해 뒀다가 그대로 되돌려 놓습니다. */
  const scrollY = window.scrollY;
  app().innerHTML = renderReport(UI.report);
  $$('#app details[data-k]').forEach(d => {
    if(open[d.dataset.k] !== undefined) d.open = open[d.dataset.k];
  });
  window.scrollTo(0, scrollY);
}

/* ---- 분석 요청 ----------------------------------------------------------- */
let analyzeSeq = 0;

async function analyze(input, {sample = false} = {}){
  const seq = ++analyzeSeq;
  UI.sample = sample;
  go('analyzing', {push:false});
  try {
    const report = await API.analyze(input);
    if(seq !== analyzeSeq) return;             // 취소되었거나 더 새 요청이 있음
    clearInterval(stepTimer);
    UI.report = report;
    go('report');
  } catch(e){
    if(seq !== analyzeSeq) return;
    clearInterval(stepTimer);
    UI.error = e;
    UI.retryLabel = '다시 분석하기';
    UI.lastInput = input;
    UI.retryAction = () => analyze(input, {sample});
    UI.view = 'error';
    paint();
  }
}


/* ---- 이벤트 (화면이 통째로 바뀌므로 최상위에서 위임합니다) ---------------- */
document.addEventListener('input', e => {
  if(['chatTextInput', 'chatFreeInput', 'chatExamFreeInput', 'chatProdFreeInput'].includes(e.target.id))
    e.target.classList.remove('err');
  if(UI.view === 'input' && e.target.closest('#app')) refreshForm();
});
document.addEventListener('change', e => {
  /* 검진표 사진을 고른 순간. 같은 파일을 다시 고를 수도 있어야 하므로
     처리한 뒤 값을 비웁니다(안 비우면 change 가 다시 일어나지 않습니다). */
  if(e.target.id === 'examImageInput'){
    const file = e.target.files && e.target.files[0];
    e.target.value = '';
    handleExamImageFile(file);
    return;
  }
  if(UI.view !== 'input' || !e.target.closest('#app')) return;
  refreshForm();
});

document.addEventListener('click', e => {
  const el = e.target.closest('button, a[data-act]');
  if(!el) return;
  const act = el.dataset.act;

  /* --- 어느 화면에서나 --- */
  if(act === 'home'){ e.preventDefault(); go('home'); return; }
  if(act === 'start-input'){ e.preventDefault(); UI.sample = false; go('input'); return; }
  if(act === 'login'){ e.preventDefault(); openAuthGate({mode:'login'}); return; }
  if(act === 'signup'){ e.preventDefault(); openAuthGate({mode:'signup'}); return; }
  if(act === 'edit'){ e.preventDefault(); UI.sample = false; UI.focus = el.dataset.to; go('input'); return; }
  if(act === 'print'){
    e.preventDefault();
    /* 미리보기 창처럼 인쇄가 막힌 환경도 있습니다. */
    try { window.print(); }
    catch(err){ console.warn('[print] 이 환경에서는 인쇄 창을 열 수 없습니다.', err); }
    return;
  }
  if(act === 'cancel'){ e.preventDefault(); analyzeSeq++; clearInterval(stepTimer); UI.sample = false; go('input'); return; }
  if(act === 'retry'){
    e.preventDefault();
    (UI.retryAction || (() => analyze(UI.lastInput || snapshot())))();
    return;
  }
  if(act === 'fresh'){
    e.preventDefault();
    UI.sample = false; UI.report = null;
    resetChat();
    go('input');
    return;
  }
  if(act === 'mode-chat'){ e.preventDefault(); UI.inputMode = 'chat'; go('input', {push:false}); return; }
  if(act === 'mode-form'){ e.preventDefault(); UI.inputMode = 'form'; go('input', {push:false}); return; }

  /* --- 로그인이 끊겼을 때 --- */
  if(act === 'relogin'){
    e.preventDefault();
    UI.pendingAfterLogin = UI.retryAction;
    go('input', {push:false});
    openAuthGate({message:'세션이 만료되었습니다. 다시 로그인해 주세요.'});
    return;
  }

  /* --- 로그인 모달 안 --- */
  if(act === 'auth-switch'){
    e.preventDefault();
    AUTH.mode = el.dataset.mode === 'signup' ? 'signup' : 'login';
    AUTH.formError = '';
    paintAuthModal(true);
    return;
  }

  /* --- 상단바 · 지난 리포트 --- */
  if(act === 'acct-menu'){
    e.preventDefault();
    const menu = document.getElementById('acctMenu');
    if(menu) menu.hidden = !menu.hidden;
    return;
  }
  if(act === 'logout'){
    e.preventDefault();
    const menu = document.getElementById('acctMenu');
    if(menu) menu.hidden = true;
    (async () => {
      try { await API.logout(); }
      catch(err){ console.warn('[logout] 실패했지만 화면은 로그아웃 상태로 되돌립니다.', err); }
      AUTH.user = null;
      saveSessionUser(null);      /* 서버 호출이 실패했더라도 사본은 반드시 지웁니다 */
      resetToGuest();
      paintTopbar();
      go('home', {push:false});
    })();
    return;
  }
  if(act === 'history'){
    e.preventDefault();
    const menu = document.getElementById('acctMenu');
    if(menu) menu.hidden = true;
    showHistory();
    return;
  }
  if(act === 'new-report'){
    e.preventDefault();
    UI.sample = false; UI.report = null;
    resetChat();
    go('input');
    return;
  }
  if(act === 'open-report'){
    e.preventDefault();
    openReport(el.dataset.id);
    return;
  }
  /* 지난 리포트 삭제 — 되돌릴 수 없으므로 카드 안에서 한 번 더 확인받습니다.
     (브라우저 기본 confirm 창은 화면 밖에 떠서 무엇을 지우는 중인지
      보이지 않으므로 쓰지 않습니다) */
  if(act === 'ask-delete-report'){ e.preventDefault(); UI.deleteAsk = el.dataset.id; paint(); return; }
  if(act === 'cancel-delete-report'){ e.preventDefault(); UI.deleteAsk = null; paint(); return; }
  if(act === 'confirm-delete-report'){ e.preventDefault(); deleteReport(el.dataset.id); return; }

  if(UI.view !== 'input') return;

  /* 검진표 사진 고르기 — 숨겨 둔 파일 입력칸을 대신 눌러 줍니다. */
  if(act === 'pick-exam-image'){
    e.preventDefault();
    const input = document.getElementById('examImageInput');
    if(input) input.click();
    return;
  }

  /* 폼 화면의 '전체 초기화' — 대화형과 똑같이 한 번 더 확인받고 지웁니다.
     지울 때는 입력값(state)과 대화 진행 상태를 함께 되돌립니다. 폼에서
     지웠는데 대화로 돌아가면 예전 대화가 그대로 남아 있으면 안 됩니다. */
  if(act === 'form-clear'){ e.preventDefault(); UI.confirmClear = true; paint(); return; }
  if(act === 'form-clear-no'){ e.preventDefault(); UI.confirmClear = false; paint(); return; }
  if(act === 'form-clear-yes'){
    e.preventDefault();
    UI.confirmClear = false;
    clearInputState();
    resetChat();
    queueSave();
    paint();
    return;
  }

  /* --- 대화형 입력 화면 전용 ---
     성분 추가·삭제(data-add-ing/data-del-ing)는 폼과 똑같은 마크업을
     그대로 쓰므로 여기서 가로채지 않고 아래 '입력 화면 전용' 처리에
     그대로 맡깁니다. */
  if(act === 'chat-clear'){ e.preventDefault(); chatRequestClear(); return; }
  if(act === 'chat-clear-yes'){ e.preventDefault(); chatConfirmClear(); return; }
  if(act === 'chat-clear-no'){ e.preventDefault(); chatCancelClear(); return; }
  if(act === 'chat-edit-cancel'){ e.preventDefault(); chatCancelEdit(); return; }
  if(el.dataset.chatEdit !== undefined){ e.preventDefault(); chatStartEdit(Number(el.dataset.chatEdit)); return; }
  if(el.dataset.chatSkip !== undefined){ chatSubmitSkip(); return; }
  if(el.dataset.chatReply !== undefined){ chatSubmitReply(el.dataset.chatReply); return; }
  if(el.dataset.chatYn !== undefined){ chatSubmitYesNo(el.dataset.chatYn === 'yes'); return; }
  if(el.dataset.chatChip !== undefined){ chatToggleChip(el.dataset.chatChip); return; }
  if(el.dataset.chatChipNone !== undefined){ chatToggleChipNone(); return; }
  if(el.dataset.chatConfirmMulti !== undefined){ chatSubmitChipMulti(); return; }
  if(el.dataset.chatConfirm === 'examGroupDetail'){ chatConfirmExamGroup(); return; }
  if(el.dataset.chatConfirm === 'prodIngredients'){ chatConfirmProduct(); return; }
  if(el.dataset.chatFinish !== undefined){ chatFinish(); return; }

  /* --- 입력 화면 전용 --- */
  if(el.dataset.addProd !== undefined) $('#prod-list').insertAdjacentHTML('beforeend', prodCard());
  else if(el.dataset.addMed !== undefined) $('#med-list').insertAdjacentHTML('beforeend', medRow());
  else if(el.dataset.addIng !== undefined)
    el.closest('[data-prod]').querySelector('[data-items]').insertAdjacentHTML('beforeend', ingRow());
  else if(el.dataset.delProd !== undefined){
    const list = $('#prod-list');
    el.closest('[data-prod]').remove();
    if(!list.children.length) list.insertAdjacentHTML('beforeend', prodCard());   // 최소 한 칸은 남깁니다
  }
  else if(el.dataset.delMed !== undefined) el.closest('[data-med]').remove();
  else if(el.dataset.delIng !== undefined){
    const box = el.closest('[data-items]');
    el.closest('[data-ing]').remove();
    if(!box.children.length) box.insertAdjacentHTML('beforeend', ingRow());
  }
  else if(el.id === 'go-report'){
    readForm();
    clearTimeout(saveTimer); doSave();          // 마지막 입력까지 저장하고
    analyze(snapshot());                        // 분석 요청
    return;
  }
  else return;

  refreshForm();
});

/* 브라우저 뒤로가기 */
window.addEventListener('popstate', () => {
  if(UI.view === 'report' || UI.view === 'error' || UI.view === 'history' || UI.view === 'home'){ UI.sample = false; go('input', {push:false}); }
  else if(UI.view === 'analyzing'){ analyzeSeq++; clearInterval(stepTimer); go('input', {push:false}); }
});

/* 로그인 · 회원가입 폼 제출 */
document.addEventListener('submit', e => {
  if(e.target.id === 'chatTextForm'){ e.preventDefault(); chatSubmitText(); return; }
  if(e.target.id === 'chatFreeForm'){ e.preventDefault(); chatSubmitFreeText(); return; }
  if(e.target.id === 'chatExamFreeForm'){ e.preventDefault(); chatSubmitExamFree(); return; }
  if(e.target.id === 'chatProdFreeForm'){ e.preventDefault(); chatSubmitProdFree(); return; }
  if(e.target.id !== 'authForm') return;
  e.preventDefault();
  if(AUTH.busy) return;

  const mode = AUTH.mode;
  const email = ($('#au-email') && $('#au-email').value.trim()) || '';
  const pw    = ($('#au-pw')    && $('#au-pw').value) || '';
  const name  = ($('#au-name')  && $('#au-name').value.trim()) || '';

  /* 실패해서 폼을 다시 그리더라도 방금 적은 값이 남아 있도록 먼저 저장합니다. */
  AUTH.email = email; AUTH.pw = pw; AUTH.name = name;
  AUTH.busy = true; AUTH.formError = '';
  paintAuthModal();

  const req = mode === 'signup' ? API.signup(name, email, pw) : API.login(email, pw);
  req.then(user => {
    AUTH.user = user;
    saveSessionUser(user);        /* 서버 세션과 별개로, 화면이 바로 읽을 사본 */
    AUTH.busy = false;
    AUTH.name = ''; AUTH.email = ''; AUTH.pw = '';
    closeAuthGate();
    paintTopbar();
    return afterLogin();
  }).catch(err => {
    AUTH.busy = false;
    AUTH.formError = (err && err.message) || '처리하지 못했습니다. 다시 시도해 주세요.';
    paintAuthModal();
  });
});

/* 계정 메뉴 바깥을 누르면 닫습니다 */
document.addEventListener('click', e => {
  const menu = document.getElementById('acctMenu');
  if(!menu || menu.hidden) return;
  if(e.target.closest('.tb-acct')) return;
  menu.hidden = true;
});

/* 저장하지 않은 입력을 두고 창을 닫으려 할 때 */
window.addEventListener('beforeunload', e => {
  if(UI.view === 'input' && saveTimer && state.products.length){ e.preventDefault(); e.returnValue = ''; }
});


/* ---- 시작 ----------------------------------------------------------------
   여기서 지켜야 할 규칙이 하나 있습니다.
   ★ 무슨 일이 있어도 마지막에는 화면이 떠야 합니다.
     준비 단계(성분 목록·저장된 입력·주소 기록)는 전부 '있으면 좋은 것'이라
     하나가 실패해도 화면까지 멈추면 안 됩니다. 그래서 각 단계를 따로
     감싸고, 마지막 전환은 finally 에 두었습니다.

   처음 들어왔을 때는 로그인 여부와 상관없이 메인 화면(home)부터 보여
   줍니다. 로그인·회원가입은 더 이상 여기서 자동으로 띄우지 않고, 메인
   화면에서 사용자가 버튼을 눌러야 시작됩니다 — 로그인하지 않은 사람도
   서비스가 무엇을 하는지 먼저 보고 나서 가입 여부를 정할 수 있어야
   하기 때문입니다. */
(async function start(){
  UI.view = 'loading';
  paint();

  try {
    /* 성분 추천 목록 */
    try {
      const boot = await API.bootstrap();
      APP.hints = (boot && boot.nutHints) || [];
    } catch(e){
      console.warn('[bootstrap] 실패 — 성분 추천 없이 진행합니다.', e);
    }
    rebuildHints();

    /* 로그인 여부 확인 — 이 서비스는 로그인해야만 쓸 수 있습니다.
       실패(LOGIN_REQUIRED 포함)해도 화면은 열려야 하므로, 로그인 안 됨으로
       보고 계속 진행합니다.

       순서가 둘입니다. 먼저 브라우저에 남아 있는 사본으로 상단바를 그려
       두고(=이름이 즉시 보입니다), 그 다음 서버에 진짜인지 물어봅니다.
       서버 대답이 우선이며, 아니라고 하면 사본도 함께 버립니다. */
    AUTH.user = loadSessionUser();
    if(AUTH.user) paintTopbar();
    try {
      AUTH.user = await API.me();
      saveSessionUser(AUTH.user);
    } catch(e){
      AUTH.user = null;
      saveSessionUser(null);
    }
    paintTopbar();

    /* 저장해 둔 입력 이어받기 — 로그인되어 있을 때만 의미가 있습니다. */
    if(AUTH.user){
      try {
        const draft = await API.loadDraft();
        if(draft) Object.assign(state, draft);
      } catch(e){
        console.warn('[draft] 실패 — 빈 화면으로 시작합니다.', e);
      }
    }

    /* 주소 기록 (막히면 nav 안에서 조용히 넘어갑니다) */
    let hash = '';
    try { hash = location.hash; } catch(e){ /* 접근이 막힌 환경 */ }
    nav('replaceState', 'home', hash || '#home');

  } catch(e){
    console.error('[start] 예기치 못한 오류 — 그래도 메인 화면은 엽니다.', e);
  } finally {
    go('home', {push:false});
  }
})();

