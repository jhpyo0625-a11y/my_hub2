/* =========================================================================
   inputData.js — MyHerb 화면에 주입하는 '가변 Input 데이터' 규격 + 샘플
   -------------------------------------------------------------------------
   무엇인가요
     src/report.html · static/Live.html 은 뼈대만 있고, 화면에 실제로 찍히는
     글자·버튼 문구·링크·판정 결과는 전부 app.js / live-app.js 가 만들어
     넣습니다. 그중 '바뀔 수 있는 값' 만 이 파일 하나로 모았습니다.

     백엔드에서 이 파일을 import 해서
       · UI 카피(브랜드명 · 히어로 문구 · FAQ · 버튼 라벨 …) 를 내려보내거나
       · /api/bootstrap · /api/draft · /api/analyze 응답을 만들 때
         '어떤 모양이어야 하는지' 의 단일 기준으로 쓰면 됩니다.

   쓰는 법
     import inputData from './inputData.js';
     import inputData, { UI_COPY, SAMPLE_REPORT, EMPTY_INPUT } from './inputData.js';

     res.json(inputData.data.bootstrap);        // GET  /api/bootstrap
     res.json(inputData.data.draft);            // GET  /api/draft
     res.json(inputData.data.report);           // POST /api/analyze

   반드시 지켜야 할 것 (화면 코드가 전제로 하는 규칙)
     1. tone 은 색 이름만 보냅니다 — 'green'|'orange'|'red'|'crit'|'blue'|'gray'.
        #15803D 같은 색값을 서버가 보내면 안 됩니다. 실제 색은 app.js 의
        TONE 표가 정합니다.
     2. level 은 여섯 개 키 중 하나만 — 'over'|'near'|'low'|'none'|'unknown'|'met'.
        화면 문구('매우 과다' 등)와 정렬 순서는 app.js 의 LEVEL 표가 정합니다.
     3. bar 의 네 값(supp·meal·rdaMark·ulMark)은 **퍼센트(0~100)** 입니다.
        서버가 계산해서 내려보냅니다. 화면은 그대로 그리기만 합니다.
     4. 문장(caption · note · summary.text · recommend.*)은 서버(AI)가 씁니다.
        화면은 문장을 만들지 않습니다.
     5. unverified:true 인 동안에는 화면 맨 위에 '예시 기준값' 경고 띠가
        자동으로 뜹니다. 검증된 기준으로 바꾼 뒤 false 로 내려 주세요.

   ⚠️ 아래 샘플의 성분 기준값·상호작용 문구는 렌더링 확인용 예시입니다.
      실제 서비스 기준값이 아니므로 그대로 배포하지 마세요.
   ========================================================================= */


/* =========================================================================
   1. 타입 정의 (JSDoc)
   ========================================================================= */

/**
 * 색 토큰 이름. 실제 색값은 프런트(app.js 의 TONE)가 정합니다.
 * @typedef {'green'|'orange'|'red'|'crit'|'blue'|'gray'} Tone
 */

/**
 * 성분 섭취 수준. 화면 문구·정렬 순서는 프런트(app.js 의 LEVEL)가 정합니다.
 *   over 매우 과다 / near 상한 근접 / low 부족 / none 미섭취 /
 *   unknown 확인 불가(기준값 없음) / met 충족
 * @typedef {'over'|'near'|'low'|'none'|'unknown'|'met'} Level
 */

/**
 * 검진 판정 코드. '' 는 미입력.
 * @typedef {'A'|'B'|'D'|''} JudgeCode
 */

/**
 * 색이 붙은 짧은 라벨. 헤더 배지·종합 소견 칩에 씁니다.
 * @typedef  {Object} Badge
 * @property {string} text  화면에 그대로 찍히는 글자 (예: '영양제 2종')
 * @property {Tone}   tone
 */

/* ---- 입력(Input) — 화면 → 서버 --------------------------------------- */

/**
 * 영양제 제품 한 개에 든 성분 한 줄.
 * @typedef  {Object} ProductItem
 * @property {string} name    성분명. 사용자가 자유 입력 (예: '비타민 C')
 * @property {number|string} amount 함량
 * @property {string} unit    'mg'|'µg'|'g'|'IU'|'mL'|'억CFU' 중 하나
 */

/**
 * 영양제 제품 한 개.
 * @typedef  {Object} Product
 * @property {string} name          제품명 (비어 있을 수 있음)
 * @property {ProductItem[]} items  성분 목록
 */

/**
 * 복용 중인 약 한 건.
 * @typedef  {Object} Med
 * @property {string} name  약 이름 (예: '와파린 5mg')
 * @property {string} desc  복용법·메모 (선택)
 */

/**
 * 건강검진 입력값. key 는 app.js 의 EXAM[].items[].inputs[].key 와 같습니다.
 * 값은 전부 문자열이며, 입력하지 않은 항목은 아예 넣지 않습니다.
 * @typedef  {Object} ExamValues
 * @property {string} [sbp]    수축기 혈압 mmHg
 * @property {string} [dbp]    이완기 혈압 mmHg
 * @property {string} [height] 키 cm
 * @property {string} [weight] 몸무게 kg
 * @property {string} [waist]  허리둘레 cm
 * @property {string} [hb]     혈색소 g/dL
 * @property {string} [glu]    공복혈당 mg/dL
 * @property {string} [tc]     총콜레스테롤 mg/dL
 * @property {string} [hdl]    HDL 콜레스테롤 mg/dL
 * @property {string} [tg]     중성지방 mg/dL
 * @property {string} [ldl]    LDL 콜레스테롤 mg/dL
 * @property {string} [ast]    AST U/L
 * @property {string} [alt]    ALT U/L
 * @property {string} [ggt]    γ-GTP U/L
 * @property {string} [upro]   요단백 '음성(-)'|'약양성(±)'|'양성(+1) 이상'
 * @property {string} [cr]     혈청크레아티닌 mg/dL
 * @property {string} [egfr]   e-GFR mL/min
 * @property {string} [tscore] 골밀도 T-score
 * @property {string} [cxr]    흉부촬영 소견
 */

/**
 * 분석 요청 본문. PUT /api/draft 와 POST /api/analyze 가 같은 모양입니다.
 * @typedef  {Object} AnalysisInput
 * @property {string}           name      이름 (선택)
 * @property {string}           age       나이. 문자열로 보냅니다 (필수)
 * @property {''|'남성'|'여성'} sex       성별 (필수)
 * @property {string}           date      검진일 'YYYY-MM-DD'
 * @property {ExamValues}       exam      검진 수치
 * @property {string[]}         chronic   진단 후 약물 치료 중인 질환 목록
 * @property {Med[]}            meds      복용 중인 약
 * @property {Product[]}        products  복용 중인 영양제
 * @property {boolean}          countMeal 식사 평균 추정치를 함께 계산할지
 */

/* ---- 리포트(Report) — 서버 → 화면 ------------------------------------ */

/**
 * 검진 항목 하나의 판정.
 * @typedef  {Object} ExamJudge
 * @property {JudgeCode} code
 * @property {string}    text     '정상A'|'경계'|'질환의심'|'미입력' 또는 항목별 문구
 * @property {Tone}      tone
 * @property {string}    [advice] 있으면 리포트 헤더에 빨간 줄로 강조됩니다
 */

/**
 * 검진 표의 한 줄.
 * @typedef  {Object} ExamRow
 * @property {string}    key    항목 키 (예: 'bp')
 * @property {string}    name   항목 이름 (예: '혈압')
 * @property {string}    ref    판정 기준 문자열 (예: '120/80 미만')
 * @property {string}    value  사용자 수치를 사람이 읽는 형태로 (예: '132/84')
 * @property {ExamJudge} judge
 */

/**
 * 목표질환별 묶음. 순서가 곧 리포트 표의 구분줄 순서입니다.
 * @typedef  {Object} ExamGroup
 * @property {string}    group  (예: '이상지질혈증')
 * @property {ExamRow[]} rows
 */

/**
 * 검진 종합 판정.
 * @typedef  {Object} ExamOverall
 * @property {string} label  (예: '정상A' · '유질환자')
 * @property {Tone}   tone
 * @property {string} desc   한 줄 설명
 */

/**
 * 리포트의 검진 블록.
 * @typedef  {Object} ExamModel
 * @property {ExamGroup[]} groups   전체(미입력 포함). 화면이 알아서 걸러 그립니다
 * @property {ExamRow[]}   rows     groups 를 편 것
 * @property {{A:number,B:number,D:number}} counts
 * @property {ExamOverall} overall
 * @property {number}      filled   판정이 난 항목 수 (A+B+D)
 * @property {ExamRow[]}   abnormal D 또는 B 인 줄만
 */

/**
 * 막대 좌표. 전부 **퍼센트(0~100)** 입니다. 오른쪽 끝은 상한이 아닙니다 —
 * 상한 눈금 뒤에 여백이 있어 초과분이 눈금을 지나 뻗습니다.
 * @typedef  {Object} NutrientBar
 * @property {number}      supp    영양제에서 온 몫
 * @property {number}      meal    식사 추정치 몫 (supp 위에 이어 그립니다)
 * @property {number|null} rdaMark 권장 눈금 위치. 눈금자 밖이면 null
 * @property {number|null} ulMark  상한 눈금 위치. 상한이 없거나 밖이면 null
 */

/**
 * 반원 게이지 비율. 1 = 100%.
 * @typedef  {Object} NutrientGauge
 * @property {number|null} rda 권장량 대비 (게이지 가운데 숫자가 이 값입니다)
 * @property {number|null} ul  상한 대비
 */

/**
 * 성분 카드 아래 코멘트. 실서비스에서는 AI 가 씁니다.
 * @typedef  {Object} NutrientNote
 * @property {string} title 굵게 나오는 첫 마디 (예: '상한 초과.')
 * @property {string} body
 */

/**
 * 성분 카드 한 장.
 * @typedef  {Object} Nutrient
 * @property {string}   key        중복 없는 식별자 (예: 'zinc')
 * @property {string}   name       화면에 찍히는 이름 (예: '아연')
 * @property {string}   unit       'mg' 등. 아래 수치들의 단위
 * @property {Level}    level
 * @property {number}   supp       영양제 합산량
 * @property {number}   meal       식사 평균 추정치
 * @property {number}   total      supp + meal
 * @property {number|null} rda     권장섭취량. 없으면 null
 * @property {number|null} ul      상한섭취량. 없으면 null
 * @property {boolean}  hasStd     기준값이 등록된 성분인지
 * @property {boolean}  ulSuppOnly 상한을 영양제분만으로 비교했는지 (엽산·마그네슘 등)
 * @property {number}   ulAmount   상한과 실제로 비교한 값
 * @property {string[]} sources    이 성분이 나온 제품명들. 비면 식사 추정치만
 * @property {string[]} unmapped   환산 규칙이 없어 합산하지 못한 표기들
 * @property {string}   basis      기준 요약 문자열 (예: '권장 10 · 상한 35mg')
 * @property {NutrientBar}   bar
 * @property {NutrientGauge} gauge
 * @property {string}   caption    카드 위 작은 캡션 (어디서 얼마씩 왔는지)
 * @property {NutrientNote}  note
 */

/**
 * 상호작용 · 중복 점검 한 줄.
 * @typedef  {Object} Issue
 * @property {string} kind  왼쪽 배지 글자 (예: '상한 초과' · '복약 주의')
 * @property {Tone}   tone
 * @property {string} text  설명 문장
 * @property {string} [med] 이 경고를 낸 약 이름. 헤더의 약 카드와 연결됩니다
 */

/**
 * 추천 성분 한 개.
 * @typedef  {Object} RecommendItem
 * @property {string} name
 * @property {string} amount   (예: '310mg 더'). 비면 표시하지 않습니다
 * @property {string} reason   왜 골랐는지
 * @property {Tone}   tone     왼쪽 세로선 색
 * @property {string} caution  복약 주의. 비면 표시하지 않습니다
 */

/**
 * 추천 블록. 통째로 없으면(null) 화면에서 이 섹션이 빠집니다.
 * @typedef  {Object} Recommend
 * @property {string}          title
 * @property {string}          desc
 * @property {RecommendItem[]} items
 * @property {string}          advice   상단 강조 문구. 비면 표시하지 않습니다
 * @property {number}          more     목록에서 잘린 개수
 * @property {string}          moreText 잘렸다는 안내 문장
 * @property {string}          note     맨 아래 면책 문구
 */

/**
 * 종합 소견. 문장 전체를 서버(AI)가 씁니다.
 * @typedef  {Object} Summary
 * @property {string}  text
 * @property {Badge[]} chips
 */

/**
 * 리포트를 언제·무엇이 만들었는지.
 * @typedef  {Object} ReportMeta
 * @property {string} generatedAt ISO8601
 * @property {'mock'|'server'} source
 * @property {string} engine      사람이 읽는 엔진 설명
 */

/**
 * POST /api/analyze 와 GET /api/reports/:id 의 응답.
 * @typedef  {Object} Report
 * @property {ReportMeta}     meta
 * @property {AnalysisInput}  input     요청을 그대로 되돌려 줍니다 (헤더가 씁니다)
 * @property {boolean}        hasSupp   계산할 성분이 하나라도 있는지
 * @property {boolean}        mealOnly  영양제 없이 식사 기준만으로 본 결과인지
 * @property {number}         cols      성분 카드 열 수. 1~4
 * @property {Level}          worst     가장 위험한 수준
 * @property {Badge[]}        badges    헤더 요약 배지
 * @property {ExamModel}      exam
 * @property {Nutrient[]}     nutrients 위험한 것부터 정렬해서 보냅니다
 * @property {Issue[]}        issues
 * @property {Recommend|null} recommend
 * @property {Summary}        summary
 */

/* ---- 그 밖의 응답 ------------------------------------------------------ */

/**
 * GET /api/bootstrap — 화면 열 때 한 번.
 * @typedef  {Object} Bootstrap
 * @property {string[]} nutHints   성분명 자동완성 목록
 * @property {boolean}  unverified true 면 '예시 기준값' 경고 띠가 뜹니다
 */

/**
 * GET /api/me · POST /api/login · POST /api/signup 의 응답.
 * @typedef  {Object} SessionUser
 * @property {string} name
 * @property {string} email
 */

/**
 * 지난 리포트 카드에 찍히는 입력 요약.
 * @typedef  {Object} ReportInfo
 * @property {string}   name
 * @property {string}   age
 * @property {string}   sex
 * @property {string}   date
 * @property {boolean}  countMeal
 * @property {string[]} chronic
 * @property {string[]} products     앞 3개만
 * @property {number}   productCount
 * @property {string[]} meds         앞 3개만
 * @property {number}   medCount
 * @property {number}   examCount
 * @property {string}   examOverall
 * @property {number}   nutrientCount
 */

/**
 * GET /api/reports 의 한 줄.
 * @typedef  {Object} ReportListItem
 * @property {string}     id
 * @property {string}     createdAt ISO8601
 * @property {string}     summaryLine
 * @property {Level}      worst
 * @property {Badge[]}    badges
 * @property {ReportInfo} info
 */

/**
 * POST /api/exam-image — 검진표 사진 판독 결과.
 * @typedef  {Object} ExamReading
 * @property {string}     name
 * @property {string}     age
 * @property {string}     sex
 * @property {string}     date
 * @property {ExamValues} exam
 * @property {string[]}   chronic
 * @property {string[]}   groups  채워진 검진 그룹 이름들
 * @property {{group:string,name:string,text:string}[]} fields 말풍선에 읽어 줄 값
 * @property {'demo'|'model'} source demo 면 '예시 판독' 이라고 화면에 밝힙니다
 */

/* ---- UI 카피 ----------------------------------------------------------- */

/**
 * 브랜드 · 문서 머리 정보.
 * @typedef  {Object} BrandCopy
 * @property {string}      serviceName  상단바 로고 자리에 찍히는 글자
 * @property {string}      pageTitle    <title>
 * @property {string}      lang         <html lang>
 * @property {string}      fontCssUrl   웹폰트 CSS 주소
 * @property {string}      stylesheet   화면 스타일시트 경로
 * @property {string|null} logoImageUrl 이미지 로고를 쓸 때만. null 이면 글자 로고
 * @property {string}      logoAlt
 */


/* =========================================================================
   2. 가변 데이터 — 아래를 바꿔 끼우면 화면 문구·결과가 바뀝니다
   ========================================================================= */

/** 값이 비었을 때 화면이 시작하는 입력 초기값. @type {AnalysisInput} */
export const EMPTY_INPUT = {
  name: '',
  age : '',
  sex : '',                /* 기본값을 주지 않습니다 — 성별에 따라 판정이 달라집니다 */
  date: '',                /* 서버가 오늘 날짜(YYYY-MM-DD)로 채워 보내도 됩니다 */
  exam: {},
  chronic  : [],
  meds     : [],
  products : [],
  countMeal: true,
};

/** 화면에 찍히는 모든 고정 문구 · 링크 · 이미지 경로. */
export const UI_COPY = {

  /* ---- 브랜드 · 문서 머리 (report.html / Live.html) -------------------- */
  /** @type {BrandCopy} */
  brand: {
    serviceName : 'MyHerb',
    pageTitle   : 'MyHerb',
    lang        : 'ko',
    fontCssUrl  : 'https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.min.css',
    stylesheet  : 'styles.css',
    logoImageUrl: null,     /* 이미지 로고를 쓰려면 '/static/img/logo.svg' 처럼 적습니다 */
    logoAlt     : '메인 화면으로 이동',
  },

  /* ---- 상단바 --------------------------------------------------------- */
  topbar: {
    logoTitle  : '메인 화면으로 이동',
    guest      : {login:'로그인', signup:'회원가입'},
    accountMenu: [
      {act:'history', label:'지난 리포트'},
      {act:'logout',  label:'로그아웃'},
    ],
  },

  /* ---- 로그인 · 회원가입 모달 ----------------------------------------- */
  auth: {
    login: {
      title     : '로그인',
      defaultMsg: '입력하신 내용과 지난 리포트를 이어서 보려면 로그인해 주세요.',
      submit    : '로그인',
      switchText: '계정이 없으신가요? 회원가입',
    },
    signup: {
      title     : '회원가입',
      defaultMsg: '계정을 만들면 입력한 내용과 지난 리포트를 이어서 보실 수 있습니다.',
      submit    : '회원가입',
      switchText: '이미 계정이 있으신가요? 로그인',
    },
    fields: {
      name    : {label:'이름',     placeholder:'홍길동'},
      email   : {label:'이메일',   placeholder:'you@example.com'},
      password: {label:'비밀번호', placeholder:'4자 이상', minLength:4},
    },
    busyLabel: '처리 중…',
  },

  /* ---- 알림 띠 -------------------------------------------------------- */
  banners: {
    unverified: {
      tone : 'warn',
      title: '예시 기준값으로 계산 중입니다.',
      body : '성분 기준값과 상호작용 규칙이 아직 검증되지 않았습니다. 실제 판단에 사용하지 마세요.',
    },
    sample: {
      tone : 'info',
      title: '샘플 리포트입니다.',
      body : '예시로 만든 가상의 입력으로 만든 화면입니다.',
      cta  : '내 정보로 시작하기',
    },
  },

  /* ---- 메인(홈) 화면 --------------------------------------------------- */
  home: {
    hero: {
      eyebrow: '영양제 · 건강검진 통합 분석',
      title  : '내가 먹는 영양제, 정말 필요한 만큼일까요?',
      sub    : '나이·성별에 건강검진 결과와 지금 드시는 영양제·약을 더하면, 권장 섭취량과 상한선 대비 어디쯤인지, 약과 부딪히는 성분은 없는지 한 번에 확인해 드려요.',
      meta   : ['대화 또는 폼, 편한 방식으로 입력', '국가 건강검진 실시기준 반영', '지난 리포트는 이력에 저장돼요'],
      /* 로그인 여부에 따라 버튼이 갈립니다. act 는 화면이 아는 동작 이름입니다. */
      ctaGuest : [
        {act:'signup',      label:'무료로 시작하기',  style:'primary'},
        {act:'login',       label:'로그인',           style:'ghost'},
      ],
      ctaMember: [
        {act:'start-input', label:'입력 시작하기',    style:'primary'},
        {act:'history',     label:'지난 리포트 보기', style:'ghost'},
      ],
    },
    features: {
      eyebrow: 'FEATURES',
      title  : 'MyHerb가 확인해 드리는 것들',
      sub    : '입력한 내용을 바탕으로 아래 내용을 함께 보여드려요.',
      items  : [
        {t:'대화 또는 폼, 편한 방식으로', d:'질문에 답하듯 대화로 입력하거나, 원하는 항목만 골라 폼으로 입력하세요. 화면 위 토글로 언제든 바꿀 수 있고, 입력한 내용은 그대로 남아 있어요.'},
        {t:'국가 건강검진 기준 반영', d:'국가 건강검진 실시기준([별표 4])에 맞춰 혈압·혈당·콜레스테롤 같은 검진 항목의 판정을 함께 보여드려요.'},
        {t:'권장 대비 · 상한 대비, 두 기준', d:'먹는 영양제 성분을 권장 섭취량과 상한섭취량, 두 가지 기준으로 동시에 비교해서 보여드려요.'},
        {t:'복용 중인 약과 겹치는지 확인', d:'지금 드시는 약을 함께 적으면, 영양제 성분과 부딪힐 수 있는 조합이 있는지 같이 확인해요.'},
        {t:'지난 리포트는 이력에 저장', d:'분석할 때마다 이력에 남아, 로그인만 하면 언제든 다시 열어볼 수 있어요.'},
        {t:'인쇄해서 보관', d:'결과 화면을 그대로 인쇄하거나 파일로 저장해서 참고할 수 있어요.'},
      ],
    },
    steps: {
      eyebrow: 'HOW IT WORKS',
      title  : '이용 방법',
      items  : [
        {t:'기본 정보',     d:'나이와 성별만 있으면 시작할 수 있어요.'},
        {t:'건강검진 결과', d:'받으신 항목만 넣으시면 돼요. 선택 사항이에요.'},
        {t:'영양제 · 약',   d:'지금 드시는 것들을 적어 주세요. 이것도 선택이에요.'},
        {t:'결과 확인',     d:'권장 대비·상한 대비로 바로 확인하고, 필요하면 인쇄해 두세요.'},
      ],
    },
    usecases: {
      eyebrow: 'FOR YOU',
      title  : '이런 분들께 도움이 돼요',
      items  : [
        {t:'영양제를 여러 개 챙겨 드시는 분', d:'제품마다 겹치는 성분이 상한을 넘기고 있진 않은지 궁금하신 분께 도움이 돼요.'},
        {t:'건강검진 결과를 그냥 넘기셨던 분', d:'수치를 받아만 보고 무엇을 챙겨야 할지 몰랐던 분도, 넣기만 하면 바로 확인할 수 있어요.'},
        {t:'약을 꾸준히 드시는 분', d:'지금 먹는 약과 영양제가 부딪히지 않는지 궁금하신 분께 도움이 돼요.'},
      ],
    },
    faq: {
      eyebrow: 'FAQ',
      title  : '자주 묻는 질문',
      items  : [
        {q:'이 결과는 진단인가요?',
         a:'아니요. MyHerb는 참고용 정보를 보여드릴 뿐, 진단이나 처방이 아니에요. 건강 상태나 복약에 대한 판단은 반드시 의사·약사와 상의해 주세요.'},
        {q:'지금 보여주는 기준값은 실제 서비스 기준인가요?',
         /* unverified 값에 따라 둘 중 하나를 골라 씁니다 */
         a          : '실제 서비스에 연결된 기준으로 계산돼요.',
         aUnverified: '지금은 예시 기준값으로 동작하는 개발용 화면이에요. 화면 위에 안내 띠가 떠 있는 동안은 실제 판단에 사용하지 마세요.'},
        {q:'로그인해야만 쓸 수 있나요?',
         a:'네. 입력하신 내용과 지난 리포트를 안전하게 이어서 보시려면 로그인이 필요해요.'},
        {q:'입력한 정보는 어떻게 저장되나요?',
         a:'입력하는 동안 자동으로 저장되고, 분석한 리포트는 이력에 남아 언제든 다시 볼 수 있어요.'},
        {q:'대화형과 폼 중 어느 쪽이 더 정확한가요?',
         a:'둘 다 같은 정보를 모으는 방식만 다를 뿐, 계산 결과는 완전히 같아요. 편한 쪽을 고르시면 됩니다.'},
      ],
    },
    footer: '이 서비스는 참고용이며 진단이나 처방이 아닙니다. 건강 상태나 복약에 대한 판단은 반드시 의사·약사와 상의하시기 바랍니다.',
  },

  /* ---- 입력 화면 ------------------------------------------------------ */
  input: {
    modeToggle: {
      chat: '💬 대화로 입력',
      form: '📝 폼으로 입력',
    },
    hero: {
      title: '지금 나에게 부족한 영양소, 확인해 보세요',
      sub  : '나이와 성별만 넣으면 식사에서 섭취하는 평균 추정치로 부족한 성분을 찾아 드립니다. 복용 중인 영양제와 약을 더 넣으면 합산량·상한 초과·상호작용까지 함께 봅니다.',
      meta : ['나이와 성별만 있으면 시작', '약 1분', '넣는 정보가 많을수록 결과가 정확해집니다'],
      cta  : {act:'history', label:'지난 리포트 보기'},
    },
    /* 접이식 섹션 4개. n 이 화면에 찍히는 번호입니다. */
    sections: [
      {id:'profile',  n:1, title:'기본 정보',        required:true,
       hint:'나이와 성별에 따라 권장섭취량과 검진 판정 기준이 달라집니다. 이 두 가지만 있으면 결과를 볼 수 있습니다.'},
      {id:'exam',     n:2, title:'건강검진 결과',    required:false,
       hint:'받으신 항목만 넣으시면 됩니다. 국가 건강검진 판정기준(별표 4)으로 항목별 판정을 계산합니다.'},
      {id:'products', n:3, title:'복용 중인 영양제', required:false,
       hint:'제품 하나에 성분을 여러 개 넣을 수 있습니다. 제품 뒷면 영양정보의 함량을 그대로 적어 주세요.'},
      {id:'meds',     n:4, title:'복용 중인 약',     required:false,
       hint:'약 이름을 그대로 적어 주세요. 영양제와 함께 먹을 때 주의할 점을 찾아 드립니다.'},
    ],
    labels: {
      required        : '필수',
      optional        : '건너뛸 수 있음',
      name            : '이름 (선택)',
      age             : '나이 *',
      sex             : '성별 *',
      sexPlaceholder  : '선택해 주세요',
      date            : '검진일',
      chronicHead     : '진단 후 약물 치료 중인 질환',
      countMeal       : '식사에서 섭취하는 평균 추정치로 함께 계산',
      countMealNote   : '이 항목을 켜 두면 영양제를 넣지 않아도 식사만으로 부족한 성분을 찾아 드립니다.',
      addProduct      : '+ 영양제 추가',
      addIngredient   : '+ 성분 추가',
      addMed          : '+ 약 추가',
      submit          : '결과 보기',
      submitHintTitle : '나이와 성별을 입력해 주세요',
      submitHint      : '이 두 가지만 있으면 식사 기준으로 부족한 성분을 찾아 드립니다.',
    },
    placeholders: {
      name       : '홍길동',
      age        : '45',
      productName: '제품명 (예: 종합비타민)',
      ingName    : '예: 비타민 C',
      ingAmount  : '함량',
      medName    : '약 이름 (예: 와파린 5mg)',
      medDesc    : '복용법이나 메모 (선택)',
    },
    /* 성분 함량 단위 선택지. 순서가 그대로 <select> 순서입니다. */
    units  : ['mg', 'µg', 'g', 'IU', 'mL', '억CFU'],
    /* 성별 선택지 */
    sexes  : ['남성', '여성'],
    /* 만성질환 체크박스 */
    chronic: ['고혈압', '당뇨병', '이상지질혈증', '폐결핵', '우울증', '조기정신증', 'C형간염', '만성폐쇄성폐질환'],
  },

  /* ---- 검진표 사진 등록 ------------------------------------------------ */
  examImage: {
    buttonNew  : '검진표 이미지 등록',
    buttonAgain: '검진표 다시 올리기',
    buttonTitle: '건강검진 결과지 사진을 올리면 읽어서 자동으로 채워 드려요',
    hint       : '이미지 파일만 · 10MB 이하',
    hintDoneTpl: '사진에서 {count}개 항목을 채웠어요',
    busy       : '검진표를 읽고 있어요…',
    demoNotice : '예시 판독입니다(실제 사진을 읽은 결과가 아니에요)',
    errors     : {
      notImage: '이미지 파일만 올릴 수 있어요. (PNG · JPG · GIF · WEBP · HEIC)',
      tooBig  : '이미지가 너무 큽니다. 10MB 이하로 올려 주세요.',
    },
    accept  : 'image/png,image/jpeg,image/gif,image/webp,image/bmp,image/heic',
    maxBytes: 10 * 1024 * 1024,
  },

  /* ---- 상태 화면 ------------------------------------------------------- */
  states: {
    loading: {
      title: '불러오는 중입니다',
      sub  : '저장해 두신 입력이 있는지 확인하고 있습니다.',
    },
    analyzing: {
      title : '결과를 분석하고 있습니다',
      sub   : '입력하신 내용을 바탕으로 성분을 합산하고 주의사항을 확인하는 중입니다. 보통 몇 초면 끝납니다.',
      cancel: '취소하고 돌아가기',
      /* 진행 단계 문구. 실제 진행률이 아니라 기다림을 덜기 위한 장치입니다. */
      steps : [
        '입력하신 제품의 성분을 모으는 중',
        '성분별 섭취량을 합산하는 중',
        '복용 중인 약과의 상호작용을 확인하는 중',
        '검진 결과와 함께 소견을 정리하는 중',
      ],
    },
    error: {
      title      : '결과를 만들지 못했습니다',
      fallbackMsg: '알 수 없는 문제가 생겼습니다.',
      keepInput  : ' 입력하신 내용은 그대로 남아 있습니다.',
      afterLogin : ' 다시 로그인하면 이어서 진행됩니다.',
      retry      : '다시 시도',
      relogin    : '다시 로그인하기',
      back       : '입력으로 돌아가기',
    },
  },

  /* ---- 리포트 화면 ----------------------------------------------------- */
  report: {
    title        : '영양제 섭취 리포트',
    subTpl       : '{date} 기준 · 입력하신 내용으로 분석했습니다.',
    print        : '인쇄 · PDF 저장',
    editInput    : '입력 수정',
    columns      : {exam:'검진 결과', meds:'복약 정보', products:'등록한 영양제'},
    refLink      : '판정기준 출처 보기',
    examTableTpl : '검진 결과 전체 · {filled}개 항목',
    examTableHead: ['검사 항목', '내 수치', '판정 기준', '판정'],
    issuesTitle  : '상호작용 · 성분 중복 점검',
    summaryTitle : '종합 소견',
    summaryKeys  : '핵심',
    /* 막대 범례. swatch 가 '#' 로 시작하면 색값, 아니면 Tone 이름입니다. */
    legend: [
      {label:'영양제',         swatch:'#1E3A8A', kind:'sw'},
      {label:'식사 평균 추정', swatch:'#D8DBE0', kind:'sw'},
      {label:'권장',           swatch:'green',   kind:'ln'},
      {label:'상한',           swatch:'red',     kind:'ln'},
    ],
    intake: {
      titleNone    : '아직 계산할 섭취량이 없습니다',
      titleMealOnly: '식사 평균 추정치 기준 섭취량',
      title        : '표준 기준 대비 내 섭취량',
      descNone     : '영양제를 등록하거나 식사 평균 추정치 계산을 켜면 이 자리에 성분별 카드가 나타납니다.',
      descMealOnly : '복용 중인 영양제를 넣지 않으셔서, 일반적인 식사에서 섭취하는 평균 추정치만으로 권장량과 비교했습니다. 실제 식사 내용에 따라 다를 수 있습니다.',
    },
    empty: {
      exam    : {t:'검진 결과가 없습니다',     d:'건강검진 결과를 입력하면 별표 4 기준으로 항목별 판정을 계산합니다.'},
      meds    : {t:'등록된 약이 없습니다',     d:'복용 중인 약을 입력하면 영양제와의 상호작용을 함께 점검합니다.'},
      products: {t:'등록된 영양제가 없습니다', d:'제품명과 성분을 입력하면 성분별 합산량을 계산해 드립니다.'},
      issues  : {t:'점검된 항목이 없습니다',   d:'등록한 제품과 약 사이에서 겹치거나 부딪히는 성분이 발견되지 않았습니다.'},
    },
    footer: {
      unverified: '이 화면의 기준값과 상호작용 규칙은 검증되지 않은 예시입니다. 실제 판단에 사용하지 마세요.',
      disclaimer: '이 리포트는 입력하신 내용을 바탕으로 한 참고 자료이며, 진단이나 처방이 아닙니다. 건강 상태나 복약에 대한 판단은 반드시 의사·약사와 상의하시기 바랍니다.',
    },
  },

  /* ---- 지난 리포트 목록 ------------------------------------------------ */
  history: {
    title      : '지난 리포트',
    countTpl   : '{n}건',
    newReport  : '새 리포트 시작',
    open       : '다시 보기',
    delete     : '삭제',
    confirm    : '이 리포트를 지울까요?<br>되돌릴 수 없어요.',
    confirmYes : '지우기',
    confirmNo  : '취소',
    deleteError: '지우지 못했습니다.',
    empty      : {t:'아직 리포트가 없습니다', d:'영양제를 입력하고 결과 보기를 누르면 여기에 쌓입니다.'},
  },

  /* ---- 서버 오류 문구 -------------------------------------------------- */
  errors: {
    LOGIN_REQUIRED: '로그인이 필요합니다.',
    TIMEOUT       : '응답이 너무 오래 걸립니다. 잠시 후 다시 시도해 주세요.',
    NETWORK       : '서버에 연결하지 못했습니다. 인터넷 연결을 확인해 주세요.',
    SERVER        : '서버에 문제가 생겼습니다.',
    REQUEST       : '요청을 처리하지 못했습니다.',
  },
};

/** 서버 주소와 엔드포인트. 프런트의 [D] API 경계와 짝을 이룹니다. */
export const API_CONFIG = {
  base: '',                /* 같은 도메인이면 '' — 예: 'https://api.myherb.co.kr' */
  endpoints: {
    bootstrap   : {method:'GET',    path:'/api/bootstrap',   timeout:15000},
    me          : {method:'GET',    path:'/api/me',          timeout:15000},
    signup      : {method:'POST',   path:'/api/signup',      timeout:15000},
    login       : {method:'POST',   path:'/api/login',       timeout:15000},
    logout      : {method:'POST',   path:'/api/logout',      timeout:15000},
    loadDraft   : {method:'GET',    path:'/api/draft',       timeout:15000},
    saveDraft   : {method:'PUT',    path:'/api/draft',       timeout:15000},
    analyze     : {method:'POST',   path:'/api/analyze',     timeout:60000},
    listReports : {method:'GET',    path:'/api/reports',     timeout:15000},
    getReport   : {method:'GET',    path:'/api/reports/:id', timeout:15000},
    deleteReport: {method:'DELETE', path:'/api/reports/:id', timeout:15000},
    examImage   : {method:'POST',   path:'/api/exam-image',  timeout:60000},
  },
};


/* =========================================================================
   3. 샘플 데이터 — 렌더링 테스트에 그대로 쓸 수 있습니다
   -------------------------------------------------------------------------
   시나리오: 45세 남성, 와파린 복용 중, 영양제 2종.
     · 아연이 두 제품에 겹쳐 들어 있어 상한 초과   → issues 2건
     · 와파린 × 비타민 K 상호작용                  → issues 1건
     · 칼슘 부족                                   → recommend 1건
     · 공복혈당 132 → 검진 종합판정 '질환의심'
     · 비타민 K 는 상한이 없는 성분(ul·ulMark 가 null)의 표시 예시입니다
   ========================================================================= */

/** @type {AnalysisInput} */
export const SAMPLE_INPUT = {
  name: '홍길동',
  age : '45',
  sex : '남성',
  date: '2026-03-10',
  exam: {
    sbp:'132', dbp:'84', height:'175', weight:'88', waist:'94',
    hb:'15.1', glu:'132',
    tc:'226', hdl:'42', tg:'189', ldl:'146',
    ast:'38', alt:'45', ggt:'71',
    upro:'음성(-)', cr:'1.0', egfr:'88',
  },
  chronic : [],
  meds    : [
    {name:'와파린 5mg', desc:'매일 저녁 1정'},
  ],
  products: [
    {name:'종합비타민', items:[
      {name:'비타민 C', amount:500, unit:'mg'},
      {name:'비타민 K', amount:80,  unit:'µg'},
      {name:'아연',     amount:15,  unit:'mg'},
    ]},
    {name:'미네랄 복합', items:[
      {name:'아연',     amount:15,   unit:'mg'},
      {name:'비타민 D', amount:2000, unit:'IU'},
    ]},
  ],
  countMeal: true,
};

/** 검진 표. 미입력 항목(judge.code === '')도 함께 보냅니다. @type {ExamGroup[]} */
const SAMPLE_EXAM_GROUPS = [
  {group:'고혈압', rows:[
    {key:'bp', name:'혈압', ref:'120/80 미만', value:'132/84',
     judge:{code:'B', text:'경계', tone:'orange'}},
  ]},
  {group:'비만', rows:[
    {key:'bmi', name:'체질량지수(BMI)', ref:'18.5~24.9', value:'28.7 kg/m²',
     judge:{code:'B', text:'경계', tone:'orange'}},
    {key:'waist', name:'허리둘레', ref:'90 미만', value:'94 cm',
     judge:{code:'B', text:'경계', tone:'orange'}},
  ]},
  {group:'빈혈', rows:[
    {key:'hb', name:'혈색소', ref:'13.0~16.5', value:'15.1 g/dL',
     judge:{code:'A', text:'정상A', tone:'green'}},
  ]},
  {group:'당뇨병', rows:[
    /* advice 가 붙은 줄은 리포트 헤더에 빨간 박스로 한 번 더 강조됩니다. */
    {key:'glu', name:'공복혈당', ref:'100 미만', value:'132 mg/dL',
     judge:{code:'D', text:'질환의심', tone:'red',
            advice:'공복혈당이 당뇨병 진단 기준에 해당합니다. 내과 진료로 확진 검사를 받아 보세요.'}},
  ]},
  {group:'이상지질혈증', rows:[
    {key:'tc',  name:'총콜레스테롤',   ref:'200 미만', value:'226 mg/dL',
     judge:{code:'B', text:'경계', tone:'orange'}},
    {key:'hdl', name:'HDL 콜레스테롤', ref:'60 이상',  value:'42 mg/dL',
     judge:{code:'B', text:'경계', tone:'orange'}},
    {key:'tg',  name:'중성지방',       ref:'150 미만', value:'189 mg/dL',
     judge:{code:'B', text:'경계', tone:'orange'}},
    {key:'ldl', name:'LDL 콜레스테롤', ref:'130 미만', value:'146 mg/dL',
     judge:{code:'B', text:'경계', tone:'orange'}},
  ]},
  {group:'간장질환', rows:[
    {key:'ast', name:'AST(SGOT)', ref:'40 이하', value:'38 U/L',
     judge:{code:'A', text:'정상A', tone:'green'}},
    {key:'alt', name:'ALT(SGPT)', ref:'35 이하', value:'45 U/L',
     judge:{code:'B', text:'경계', tone:'orange'}},
    {key:'ggt', name:'γ-GTP',     ref:'11~63',   value:'71 U/L',
     judge:{code:'B', text:'경계', tone:'orange'}},
  ]},
  {group:'신장질환', rows:[
    {key:'upro', name:'요단백',                ref:'음성(-)',  value:'음성(-)',
     judge:{code:'A', text:'정상A', tone:'green'}},
    {key:'cr',   name:'혈청크레아티닌',        ref:'1.5 이하', value:'1.0 mg/dL',
     judge:{code:'A', text:'정상A', tone:'green'}},
    {key:'egfr', name:'신사구체여과율(e-GFR)', ref:'60 이상',  value:'88 mL/min/1.73m²',
     judge:{code:'A', text:'정상A', tone:'green'}},
  ]},
  {group:'골다공증', rows:[
    /* 미입력 — 화면이 '미입력 1개 항목은 표시하지 않았습니다' 로 세어 줍니다. */
    {key:'tscore', name:'골밀도 T-score', ref:'-1 이상', value:'—',
     judge:{code:'', text:'미입력', tone:'gray'}},
  ]},
];

const SAMPLE_EXAM_ROWS = SAMPLE_EXAM_GROUPS.flatMap(g => g.rows);

/** @type {ExamModel} */
const SAMPLE_EXAM = {
  groups  : SAMPLE_EXAM_GROUPS,
  rows    : SAMPLE_EXAM_ROWS,
  counts  : {A:5, B:9, D:1},
  filled  : 15,
  overall : {
    label: '고혈압·당뇨병·이상지질혈증 질환의심',
    tone : 'red',
    desc : '해당 항목이 기준을 벗어나 진료와 검사가 필요합니다.',
  },
  abnormal: SAMPLE_EXAM_ROWS.filter(r => r.judge.code === 'D' || r.judge.code === 'B'),
};

/** 위험한 것부터 정렬해서 내려보냅니다. @type {Nutrient[]} */
const SAMPLE_NUTRIENTS = [
  {
    key:'zinc', name:'아연', unit:'mg', level:'over',
    supp:30, meal:9.5, total:39.5, rda:10, ul:35,
    hasStd:true, ulSuppOnly:false, ulAmount:39.5,
    sources:['종합비타민', '미네랄 복합'], unmapped:[],
    basis:'권장 10 · 상한 35mg',
    bar  :{supp:66.04, meal:20.91, rdaMark:22.01, ulMark:77.05},
    gauge:{rda:3.95, ul:1.1286},
    caption:'종합비타민 · 미네랄 복합 · 영양제 30mg + 식사 9.5mg',
    note :{title:'상한 초과.',
           body :'39.5mg, 상한 35mg을 넘었습니다. 제품 수를 줄이거나 함량이 낮은 제품으로 바꿔 보세요.'},
  },
  {
    key:'calcium', name:'칼슘', unit:'mg', level:'low',
    supp:0, meal:490, total:490, rda:800, ul:2500,
    hasStd:true, ulSuppOnly:false, ulAmount:490,
    sources:[], unmapped:[],
    basis:'권장 800 · 상한 2,500mg',
    bar  :{supp:0, meal:15.68, rdaMark:25.60, ulMark:80.00},
    gauge:{rda:0.6125, ul:0.196},
    caption:'식사 평균 추정 490mg · 등록한 제품 없음',
    note :{title:'식사만으로는 모자랍니다.',
           body :'권장량 800mg까지 310mg이 부족합니다. 위의 추천을 참고해 보세요.'},
  },
  {
    key:'vitaminC', name:'비타민 C', unit:'mg', level:'met',
    supp:500, meal:78, total:578, rda:100, ul:2000,
    hasStd:true, ulSuppOnly:false, ulAmount:578,
    sources:['종합비타민'], unmapped:[],
    basis:'권장 100 · 상한 2,000mg',
    bar  :{supp:20.00, meal:3.12, rdaMark:4.00, ulMark:80.00},
    gauge:{rda:5.78, ul:0.289},
    caption:'종합비타민 · 영양제 500mg + 식사 78mg',
    note :{title:'충분합니다.', body:'현재 구성을 유지해도 괜찮습니다.'},
  },
  {
    key:'vitaminD', name:'비타민 D', unit:'µg', level:'met',
    supp:50, meal:4.2, total:54.2, rda:10, ul:100,
    hasStd:true, ulSuppOnly:false, ulAmount:54.2,
    sources:['미네랄 복합'], unmapped:[],
    basis:'권장 10 · 상한 100µg',
    bar  :{supp:40.00, meal:3.36, rdaMark:8.00, ulMark:80.00},
    gauge:{rda:5.42, ul:0.542},
    caption:'미네랄 복합 · 영양제 50µg + 식사 4.2µg',
    note :{title:'충분합니다.', body:'현재 구성을 유지해도 괜찮습니다.'},
  },
  {
    /* 상한이 정해지지 않은 성분 — ul 과 bar.ulMark 가 모두 null 입니다.
       이때 화면에는 상한 눈금이 그려지지 않습니다. */
    key:'vitaminK', name:'비타민 K', unit:'µg', level:'met',
    supp:80, meal:42, total:122, rda:75, ul:null,
    hasStd:true, ulSuppOnly:false, ulAmount:122,
    sources:['종합비타민'], unmapped:[],
    basis:'권장 75µg 이상',
    bar  :{supp:57.02, meal:29.94, rdaMark:53.46, ulMark:null},
    gauge:{rda:1.6267, ul:1.6267},
    caption:'종합비타민 · 영양제 80µg + 식사 42µg',
    note :{title:'충분합니다.', body:'현재 구성을 유지해도 괜찮습니다.'},
  },
];

/** @type {Issue[]} */
const SAMPLE_ISSUES = [
  {kind:'상한 초과', tone:'red',
   text:'아연 합산량 39.5mg이 상한 35mg을 넘습니다. 제품 구성을 조정해 보세요.'},
  {kind:'성분 중복', tone:'blue',
   text:'아연이 종합비타민 · 미네랄 복합 에 함께 들어 있습니다.'},
  /* med 를 넣어야 리포트 헤더의 해당 약 카드에 '주의 n건' 배지가 붙습니다. */
  {kind:'복약 주의', tone:'red', med:'와파린 5mg',
   text:'와파린 5mg · 와파린 복용 중 비타민 K 섭취량이 갑자기 바뀌면 응고 지표가 흔들릴 수 있습니다. 담당 의료진과 상의하세요.'},
];

/** @type {Recommend} */
const SAMPLE_RECOMMEND = {
  title : '이런 성분을 더 챙겨 보세요',
  desc  : '식사 평균 추정치 · 복용 중인 영양제 · 복용 중인 약 1건 · 검진 15개 항목을 기준으로, 권장량에 못 미치는 성분을 모자란 순서로 골랐습니다. 이미 드시는 영양제로 채워지는 성분은 뺐습니다.',
  advice: '건강검진에서 10개 항목이 기준을 벗어났습니다. 영양제를 고르기 전에 의사·약사와 상의하시기를 권합니다.',
  items : [
    {name:'칼슘', amount:'310mg 더', tone:'blue', caution:'',
     reason:'식사 추정치로 490mg, 권장량 800mg의 61%입니다.'},
  ],
  more    : 0,
  moreText: '',
  note    : '권장섭취량에 견준 계산 결과일 뿐, 특정 제품이나 복용을 권하는 것이 아닙니다. 복용을 시작하기 전에 의사·약사와 상의하세요.',
};

/** POST /api/analyze · GET /api/reports/:id 응답 샘플. @type {Report} */
export const SAMPLE_REPORT = {
  meta: {
    generatedAt: '2026-03-10T09:24:11.000Z',
    source     : 'server',
    engine     : '예시 데이터 (렌더링 확인용)',
  },
  input   : SAMPLE_INPUT,
  hasSupp : true,
  mealOnly: false,
  cols    : 4,
  worst   : 'over',
  badges  : [
    {text:'고혈압·당뇨병·이상지질혈증 질환의심', tone:'red'},
    {text:'복약 1건',       tone:'orange'},
    {text:'영양제 2종',     tone:'green'},
    {text:'성분 상한 초과', tone:'red'},
    {text:'보충 권장 1',    tone:'blue'},
  ],
  exam     : SAMPLE_EXAM,
  nutrients: SAMPLE_NUTRIENTS,
  issues   : SAMPLE_ISSUES,
  recommend: SAMPLE_RECOMMEND,
  summary  : {
    text : "건강검진 종합 판정은 '고혈압·당뇨병·이상지질혈증 질환의심' 입니다. 등록한 2개 제품과 식사 평균 추정치에서 5개 성분을 확인했습니다. 아연은 상한을 넘어 조정이 필요합니다. 칼슘은 권장량에 미치지 못합니다. 나머지 3개 성분은 권장 범위 안에 있습니다. 점검에서 3건이 확인됐습니다.",
    chips: [
      {text:'상한 초과 1', tone:'red'},
      {text:'적정 3',      tone:'green'},
      {text:'부족 1',      tone:'blue'},
    ],
  },
};

/** GET /api/bootstrap 응답 샘플. @type {Bootstrap} */
export const SAMPLE_BOOTSTRAP = {
  nutHints: [
    '비타민 A', '비타민 B1', '비타민 B2', '나이아신', '비타민 B6', '엽산', '비타민 B12',
    '비타민 C', '비타민 D', '비타민 E', '비타민 K', '비오틴', '판토텐산',
    '칼슘', '마그네슘', '아연', '철', '셀레늄', '구리', '망간', '요오드', '크롬',
    '오메가3', '루테인', '유산균', '밀크씨슬', '코엔자임Q10',
  ],
  unverified: true,      /* 검증된 기준값으로 바꾼 뒤 false 로 내려 주세요 */
};

/** GET /api/reports 응답 샘플. @type {{reports: ReportListItem[]}} */
export const SAMPLE_REPORT_LIST = {
  reports: [
    {
      id         : 'r20260310a1b2c',
      createdAt  : '2026-03-10T09:24:11.000Z',
      summaryLine: '고혈압·당뇨병·이상지질혈증 질환의심 · 성분 5개',
      worst      : 'over',
      badges     : SAMPLE_REPORT.badges,
      info       : {
        name:'홍길동', age:'45', sex:'남성', date:'2026-03-10',
        countMeal:true, chronic:[],
        products:['종합비타민', '미네랄 복합'], productCount:2,
        meds:['와파린 5mg'], medCount:1,
        examCount:17,
        examOverall:'고혈압·당뇨병·이상지질혈증 질환의심',
        nutrientCount:5,
      },
    },
  ],
};

/** POST /api/exam-image 응답 샘플. @type {ExamReading} */
export const SAMPLE_EXAM_READING = {
  name   : '홍길동',
  age    : '45',
  sex    : '남성',
  date   : '2026-03-10',
  exam   : SAMPLE_INPUT.exam,
  chronic: [],
  groups : ['고혈압', '비만', '빈혈', '당뇨병', '이상지질혈증', '간장질환', '신장질환'],
  fields : [
    {group:'고혈압',       name:'혈압',            text:'132/84'},
    {group:'비만',         name:'체질량지수(BMI)', text:'28.7 kg/m²'},
    {group:'당뇨병',       name:'공복혈당',        text:'132 mg/dL'},
    {group:'이상지질혈증', name:'총콜레스테롤',    text:'226 mg/dL'},
  ],
  source: 'demo',        /* 'demo' 면 화면이 '예시 판독입니다' 라고 밝힙니다 */
};

/** GET /api/me · login · signup 응답 샘플. @type {SessionUser} */
export const SAMPLE_USER = {name:'홍길동', email:'hong@example.com'};


/* =========================================================================
   4. LLM 프롬프트 템플릿 (선택)
   -------------------------------------------------------------------------
   AI 에게 위 Report 규격에 맞는 JSON 을 만들게 할 때 쓰는 틀입니다.
     const prompt = buildAnalyzePrompt(userInput);
   ========================================================================= */

export const ANALYZE_PROMPT_TEMPLATE = `당신은 영양 섭취 리포트를 작성하는 분석 엔진입니다.
사용자의 입력(JSON)을 받아 화면이 그대로 그릴 수 있는 Report JSON 하나만 출력하세요.

[반드시 지킬 것]
1. 출력은 JSON 객체 하나뿐입니다. 설명·머리말·코드펜스를 붙이지 마세요.
2. tone 은 다음 중 하나만: "green" | "orange" | "red" | "crit" | "blue" | "gray".
   색상 코드(#15803D 등)를 절대 쓰지 마세요. 실제 색은 화면이 정합니다.
3. level 은 다음 중 하나만: "over" | "near" | "low" | "none" | "unknown" | "met".
   판정 규칙 — 기준값이 없으면 unknown / 섭취량이 0 이면 none /
   상한 초과면 over / 상한의 70% 이상이면 near / 권장량 이상이면 met / 그 외 low.
4. bar 의 supp·meal·rdaMark·ulMark 는 0~100 사이 퍼센트 숫자입니다.
   눈금자 최대치 scale = max(total×1.15, ulAmount×1.15, rda×1.6, ul×1.25, 1) 로 잡고
   각 값을 scale 로 나눠 백분율로 만드세요. 눈금이 scale 을 넘으면 null 을 넣습니다.
   bar.meal 은 bar.supp 위에 이어 그리므로 supp + meal 이 100 을 넘지 않게 자르세요.
5. nutrients 는 위험한 것부터 정렬합니다: over → near → low → none → unknown → met.
   같은 수준이면 실제로 복용 중인(sources 가 있는) 성분을 앞에, 그다음 이름순.
6. cols 는 min(max(성분 수, 1), 4) 입니다.
7. 모든 문장(caption · note · summary.text · recommend.*)은 한국어 존댓말로 씁니다.
   조사(은/는, 이/가, 을/를)를 앞말 받침에 맞게 쓰세요.
8. 근거 없는 임상적 단정을 하지 마세요. 검진 수치와 성분을 임의로 연결하지 말고,
   이상 소견이 있으면 "의사·약사와 상의하세요" 로 안내만 하세요.
9. 상한을 영양제 섭취분만으로 비교하는 성분(엽산·마그네슘 등)은
   ulSuppOnly 를 true 로 하고 ulAmount 에 영양제분만 넣으세요.
10. issues 중 특정 약에서 비롯된 항목은 med 에 그 약 이름을 정확히 넣으세요.
    (헤더의 약 카드와 연결하는 데 씁니다)

[출력 스키마]
{
  "meta": {"generatedAt": ISO8601, "source": "server", "engine": string},
  "input": <받은 입력을 그대로>,
  "hasSupp": boolean, "mealOnly": boolean, "cols": 1~4,
  "worst": Level,
  "badges": [{"text": string, "tone": Tone}],
  "exam": {
    "groups": [{"group": string, "rows": [ExamRow]}],
    "rows": [ExamRow],
    "counts": {"A": number, "B": number, "D": number},
    "overall": {"label": string, "tone": Tone, "desc": string},
    "filled": number,
    "abnormal": [ExamRow]
  },
  "nutrients": [{
    "key": string, "name": string, "unit": string, "level": Level,
    "supp": number, "meal": number, "total": number,
    "rda": number|null, "ul": number|null,
    "hasStd": boolean, "ulSuppOnly": boolean, "ulAmount": number,
    "sources": [string], "unmapped": [string], "basis": string,
    "bar": {"supp": number, "meal": number, "rdaMark": number|null, "ulMark": number|null},
    "gauge": {"rda": number|null, "ul": number|null},
    "caption": string,
    "note": {"title": string, "body": string}
  }],
  "issues": [{"kind": string, "tone": Tone, "text": string, "med": string?}],
  "recommend": {
    "title": string, "desc": string, "advice": string,
    "items": [{"name": string, "amount": string, "reason": string, "tone": Tone, "caution": string}],
    "more": number, "moreText": string, "note": string
  },
  "summary": {"text": string, "chips": [{"text": string, "tone": Tone}]}
}
ExamRow = {"key": string, "name": string, "ref": string, "value": string,
           "judge": {"code": "A"|"B"|"D"|"", "text": string, "tone": Tone, "advice": string?}}

[사용자 입력]
{{INPUT_JSON}}

[출력 예시 — 형태만 참고하고, 값은 위 입력에 맞게 새로 계산하세요]
{{SAMPLE_JSON}}
`;

/**
 * 프롬프트를 완성합니다.
 * @param {AnalysisInput} input
 * @param {Object}  [opts]
 * @param {boolean} [opts.withSample=true] 예시 Report 를 함께 넣을지
 * @returns {string}
 */
export function buildAnalyzePrompt(input, opts = {}){
  const withSample = opts.withSample !== false;
  return ANALYZE_PROMPT_TEMPLATE
    .replace('{{INPUT_JSON}}',  JSON.stringify(input, null, 2))
    .replace('{{SAMPLE_JSON}}', withSample ? JSON.stringify(SAMPLE_REPORT, null, 2) : '(생략)');
}


/* =========================================================================
   5. 기본 내보내기
   ========================================================================= */

const inputData = {
  schemaVersion: '1.0.0',
  locale       : 'ko-KR',

  /** 화면에 찍히는 고정 문구 · 링크 · 이미지 경로 */
  ui : UI_COPY,
  /** 서버 주소와 엔드포인트 */
  api: API_CONFIG,

  /** 실제로 주고받는 데이터 */
  data: {
    emptyInput : EMPTY_INPUT,
    bootstrap  : SAMPLE_BOOTSTRAP,
    user       : SAMPLE_USER,
    draft      : SAMPLE_INPUT,
    report     : SAMPLE_REPORT,
    reportList : SAMPLE_REPORT_LIST,
    examReading: SAMPLE_EXAM_READING,
  },

  /** LLM 에게 Report 를 생성시킬 때 쓰는 프롬프트 */
  prompt: {
    template: ANALYZE_PROMPT_TEMPLATE,
    build   : buildAnalyzePrompt,
  },
};

export default inputData;
