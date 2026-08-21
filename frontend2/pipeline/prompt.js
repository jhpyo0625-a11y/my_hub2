'use strict';
/* =========================================================================
   prompt.js — [1] 프롬프트 템플릿 생성
   -------------------------------------------------------------------------
   generatePromptTemplate(topic, params) 는 LLM 에게 보낼 '문자열 하나'를
   만듭니다. 그 답으로 받은 JSON 이 곧 renderer.js 가 그리는 가변 데이터가
   됩니다. 프롬프트 안에는 schema.js 의 JSON Schema 와 가변요소 목록이
   통째로 들어가므로, 스키마를 고치면 프롬프트도 함께 따라옵니다.
   ========================================================================= */

const {REPORT_JSON_SCHEMA, FIELD_MAP, TONES, LEVELS} = require('./schema');

/** 표 모양으로 정렬 — 프롬프트 안에서 읽기 쉽게 */
function fieldTable(){
  const w = Math.max(...FIELD_MAP.map(([k]) => k.length));
  return FIELD_MAP.map(([k, d]) => `  ${k.padEnd(w)}  ${d}`).join('\n');
}

/** 프롬프트에 넣을 파라미터 줄 — 값이 있는 것만 */
function paramLines(p){
  const rows = [
    ['대상 사용자',   p.persona],
    ['나이',         p.age],
    ['성별',         p.sex],
    ['기준 날짜',     p.date],
    ['등록 영양제',   Array.isArray(p.products) ? p.products.join(', ') : p.products],
    ['복용 중인 약',  Array.isArray(p.meds) ? p.meds.join(', ') : p.meds],
    ['만성질환',      Array.isArray(p.chronic) ? p.chronic.join(', ') : p.chronic],
    ['식사 추정 합산', typeof p.countMeal === 'boolean' ? (p.countMeal ? '켬' : '끔') : undefined],
    ['성분 카드 수',  p.nutrientCount],
    ['검진 결과',     p.examSummary],
    ['추가 지시',     p.extra],
  ].filter(([, v]) => v !== undefined && v !== null && v !== '');
  return rows.length
    ? rows.map(([k, v]) => `  - ${k}: ${v}`).join('\n')
    : '  - (지정 없음 — 현실적인 값으로 알아서 채우세요)';
}

/**
 * LLM 에게 보낼 프롬프트 문자열을 만듭니다.
 *
 * @param {string} topic   무엇에 대한 리포트인지. 예) '30대 직장인 종합비타민 사용자'
 * @param {object} [params]
 *   persona, age, sex, date, products[], meds[], chronic[], countMeal,
 *   nutrientCount, examSummary, extra  — 있는 것만 프롬프트에 실립니다.
 *   locale        기본 'ko-KR' (화면 문구가 한국어입니다)
 *   schema        스키마를 직접 갈아끼우고 싶을 때
 *   includeSchema 기본 true. false 면 필드 목록만 넣습니다(토큰 절약).
 * @returns {string} 그대로 LLM 에 넣을 수 있는 프롬프트
 */
function generatePromptTemplate(topic, params = {}){
  const p = params || {};
  const schema = p.schema || REPORT_JSON_SCHEMA;
  const locale = p.locale || 'ko-KR';
  const n = p.nutrientCount || '4~8';

  const schemaBlock = p.includeSchema === false
    ? '(스키마 생략 — 아래 필드 목록을 따르세요)'
    : JSON.stringify(schema, null, 2);

  return `당신은 영양·건강검진 리포트를 작성하는 임상영양 어시스턴트입니다.
아래 주제에 맞는 **MyHerb 영양제 섭취 리포트**의 가변 데이터를 JSON 으로 만들어 주세요.
이 JSON 은 사람이 읽는 글이 아니라, 이미 만들어져 있는 HTML 화면(report.html)에
그대로 주입되는 데이터입니다.

──────────────────────────────────────────────
[주제]
${topic}

[파라미터]
${paramLines(p)}
──────────────────────────────────────────────

[출력 규격 — JSON Schema (draft-07)]
${schemaBlock}

[가변 요소가 화면의 어디에 들어가는지]
${fieldTable()}

[반드시 지킬 것]
1. 출력은 **JSON 객체 하나**뿐입니다. 설명·인사말·\`\`\`json 같은 코드펜스를 붙이지 마세요.
2. 모든 문장은 ${locale} 로, 존댓말로 씁니다. 화면 폭이 좁으므로 note.body 는 두 문장 이내.
3. 색은 절대 넣지 마세요. tone 은 이름만 씁니다 → ${TONES.join(' | ')}
   (#15803D 같은 색값을 넣으면 디자인 토큰과 어긋납니다.)
4. nutrients[].level 은 다음 중 하나입니다 → ${LEVELS.join(' | ')}
   숫자와 어긋나지 않게 정하세요. 판정 규칙은 화면과 동일합니다.
     ul 이 있고 (ulSuppOnly ? supp : total) > ul          → over
     ul 이 있고 그 값이 ul 의 70% 이상                     → near
     rda 가 있고 total >= rda                             → met
     total 이 0                                          → none
     rda·ul 둘 다 없음                                    → unknown
     그 밖                                               → low
5. bar, gauge, cols, worst, total, ulAmount 는 **계산해서 넣지 마세요.**
   supp / meal / rda / ul 숫자만 정확히 주면 렌더러가 화면과 똑같은 식으로 계산합니다.
6. nutrients[].sources 에는 input.products[].name 에 실제로 있는 이름만 씁니다.
   issues[].med 도 input.meds[].name 과 글자까지 같아야 합니다(헤더 복약 열과 연결됨).
7. 성분 카드는 ${n}개. 위험한 것(over → near → low → met)부터 배열 앞에 놓습니다.
8. exam.rows 는 groups 안의 rows 를 모두 펼친 것과 같아야 하고,
   exam.abnormal 은 judge.code 가 'B' 또는 'D' 인 행만 담습니다.
   exam.filled 는 judge.code 가 빈 문자열이 아닌 행의 개수입니다.
9. 의학적 단정이나 처방을 하지 마세요. '권장량 대비 얼마'처럼 숫자로 설명되는 것만
   쓰고, 이상 소견이 있으면 recommend.advice 로 전문가 상담을 권합니다.
10. 값을 모르면 필드를 지우지 말고 빈 문자열 '' · 빈 배열 [] · null 을 넣으세요.
    렌더러가 기본값으로 대체합니다.

이제 위 주제에 맞는 JSON 을 출력하세요.`;
}

/** system 프롬프트로 따로 쓰고 싶을 때 (Anthropic Messages API 등) */
const SYSTEM_PROMPT =
  '당신은 정해진 JSON Schema 를 한 글자도 어기지 않고 채우는 데이터 생성기입니다. ' +
  '항상 JSON 객체 하나만 출력하고, 코드펜스나 설명을 덧붙이지 않습니다.';

module.exports = {generatePromptTemplate, SYSTEM_PROMPT};
