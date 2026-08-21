'use strict';
/* =========================================================================
   schema.js — 리포트 화면의 '가변 데이터' 규격
   -------------------------------------------------------------------------
   src/report.html 은 뼈대만 있고, 실제 내용은 app.js 의 renderReport(m) 가
   Report 객체 하나로부터 만들어 냅니다. 그 Report 객체가 곧 이 파일의
   스키마이며, LLM 이 채워야 하는 '가변 데이터'입니다.

   설계 원칙 두 가지
     1) 색값은 데이터에 넣지 않습니다. tone 이름(green/orange/red/crit/
        blue/gray)만 넣고, 실제 색은 TONE 표(renderer.js)가 정합니다.
        — app.js 의 [A] 화면 토큰 주석과 같은 약속입니다.
     2) 막대 길이·게이지 비율 같은 '기하값'은 LLM 이 계산하지 않습니다.
        supp / meal / total / rda / ul 숫자만 주면 renderer 가 app.js 와
        똑같은 식으로 bar·gauge 를 계산합니다. (derived 표시된 필드)
   ========================================================================= */

/** 데이터가 쓸 수 있는 색 이름 — 실제 색값은 renderer.js 의 TONE 이 정합니다. */
const TONES = ['green', 'orange', 'red', 'crit', 'blue', 'gray'];

/** 성분 섭취 수준 — 카드의 색과 문구가 이 키에서 나옵니다. */
const LEVELS = ['over', 'near', 'low', 'none', 'unknown', 'met'];

/** 건강검진 판정 코드 — A 정상A · B 경계 · D 질환의심 · '' 미입력 */
const JUDGE_CODES = ['A', 'B', 'D', ''];

/** 입력 화면으로 돌아가는 링크가 가리킬 수 있는 곳 */
const EDIT_TARGETS = ['profile', 'exam', 'meds', 'products'];

/* -------------------------------------------------------------------------
   가변 요소 목록 — HTML 의 어느 자리에 무엇이 들어가는지
   (프롬프트에 그대로 붙습니다. 누락 방지용 체크리스트이기도 합니다)
   ------------------------------------------------------------------------- */
const FIELD_MAP = [
  ['meta.generatedAt',        '리포트 생성 시각(ISO 8601). 화면에 직접 나오지는 않지만 이력에 씁니다.'],
  ['meta.source',             "'mock' 이면 화면 맨 위에 노란 경고 띠가 뜹니다. 실서비스는 'server'."],
  ['meta.engine',             '판정을 만든 엔진 이름. 기록용.'],

  ['input.name',              '헤더 아바타 글자와 이름. 비면 "이름 미입력".'],
  ['input.age',               '이름 옆 "OO세". 비면 "—".'],
  ['input.sex',               "'남성' | '여성'."],
  ['input.date',              '리포트 상단 "OOOO 기준" 과 헤더의 날짜.'],
  ['input.countMeal',         '식사 평균 추정치를 합산했는지. 섹션 제목·설명이 통째로 달라집니다.'],
  ['input.chronic[]',         '만성질환 이름들. 검진 종합판정 문장에 쓰입니다.'],
  ['input.products[]',        '{name, items:[{name, amount, unit}]} — 헤더 "등록한 영양제" 열.'],
  ['input.meds[]',            '{name, desc} — 헤더 "복약 정보" 열.'],

  ['badges[]',                '{text, tone} — 헤더 이름 밑 요약 배지 줄.'],

  ['exam.overall',            '{label, tone, desc} — 검진 종합 판정.'],
  ['exam.filled',             '입력된 검진 항목 수. 0 이면 검진 열이 빈 카드로 바뀝니다.'],
  ['exam.counts',             '{A, B, D} — 판정별 개수 태그.'],
  ['exam.groups[]',           '{group, rows:[검진행]} — 접이식 "검진 결과 전체" 표.'],
  ['exam.rows[]',             '{key, name, ref, value, judge:{code,text,tone,advice}} — 표의 한 줄.'],
  ['exam.abnormal[]',         'rows 중 B·D 인 것만. 헤더 요약에 위쪽 3개가 나옵니다.'],

  ['recommend.title',         '추천 섹션 제목.'],
  ['recommend.desc',          '제목 밑 설명. items 가 비면 이 문장이 본문 자리를 대신합니다.'],
  ['recommend.advice',        '검진 이상 소견이 있을 때의 상담 권고 띠. 없으면 빈 문자열.'],
  ['recommend.items[]',       '{name, amount, reason, caution, tone} — 추천 카드.'],
  ['recommend.more/moreText', '상위 N개만 보여 줄 때 남은 개수와 그 안내 문장.'],
  ['recommend.note',          '섹션 맨 아래 회색 주의 문구.'],

  ['hasSupp',                 'false 면 섭취량 섹션이 통째로 빈 카드가 됩니다.'],
  ['mealOnly',                'true 면 "식사 평균 추정치 기준" 제목·설명으로 바뀝니다.'],
  ['cols',                    '성분 카드 열 수(1~4). 없으면 renderer 가 계산합니다.'],
  ['worst',                   '가장 위험한 level. 없으면 renderer 가 계산합니다.'],

  ['nutrients[].name/unit',   '성분 카드 제목과 단위.'],
  ['nutrients[].supp/meal',   '영양제에서 온 양 / 식사 추정치. 막대 두 칸의 길이가 됩니다.'],
  ['nutrients[].total',       '합산량. 없으면 supp+meal.'],
  ['nutrients[].rda/ul',      '권장량 / 상한. 눈금 위치와 게이지 비율의 근거.'],
  ['nutrients[].level',       'over|near|low|none|unknown|met. 없으면 숫자로 계산합니다.'],
  ['nutrients[].ulSuppOnly',  '상한을 영양제분만으로 비교하는 성분인지(마그네슘 등).'],
  ['nutrients[].sources[]',   '이 성분이 들어 있는 제품 이름들. 캡션과 태그에 쓰입니다.'],
  ['nutrients[].unmapped[]',  '단위를 환산하지 못해 합산에서 뺀 입력.'],
  ['nutrients[].basis',       '"권장 400 · 상한 1,000µg" 같은 기준 요약 줄.'],
  ['nutrients[].caption',     '카드 위 회색 캡션 — 어느 제품에서 얼마씩 왔는지.'],
  ['nutrients[].note',        '{title, body} — 카드 맨 아래 색 코멘트. AI 가 쓰는 문장.'],
  ['nutrients[].bar/gauge',   '(derived) 막대·게이지 좌표. 주지 않으면 renderer 가 계산합니다.'],

  ['issues[]',                '{kind, tone, text, med} — 상호작용·중복 점검 한 줄.'],

  ['summary.text',            '종합 소견 문단. AI 가 통째로 씁니다.'],
  ['summary.chips[]',         '{text, tone} — 소견 밑 "핵심" 배지.'],
];

/* -------------------------------------------------------------------------
   JSON Schema (draft-07) — LLM 에게 그대로 보여 줄 응답 규격
   ------------------------------------------------------------------------- */
const examRowDef = {
  type: 'object',
  required: ['name', 'ref', 'value', 'judge'],
  properties: {
    key: {type: 'string'},
    name: {type: 'string'},
    ref: {type: 'string', description: '판정 기준 문구. 예) "120 미만 / 80 미만"'},
    value: {type: 'string', description: '내 수치. 예) "128 / 84"'},
    judge: {
      type: 'object',
      required: ['code', 'text', 'tone'],
      properties: {
        code: {type: 'string', enum: JUDGE_CODES},
        text: {type: 'string'},
        tone: {type: 'string', enum: TONES},
        advice: {type: 'string', description: '있으면 헤더에 빨간 강조 줄로 올라갑니다.'},
      },
    },
  },
};

const nutrientDef = {
  type: 'object',
  required: ['name', 'unit', 'supp', 'meal', 'sources'],
  properties: {
    key: {type: 'string'},
    name: {type: 'string'},
    unit: {type: 'string'},
    level: {type: 'string', enum: LEVELS, description: 'derived 가능 — 생략하면 숫자로 계산'},
    supp: {type: 'number'},
    meal: {type: 'number'},
    total: {type: 'number', description: 'derived — 생략하면 supp+meal'},
    rda: {type: ['number', 'null']},
    ul: {type: ['number', 'null']},
    hasStd: {type: 'boolean'},
    ulSuppOnly: {type: 'boolean'},
    ulAmount: {type: 'number', description: 'derived'},
    sources: {type: 'array', items: {type: 'string'}},
    unmapped: {type: 'array', items: {type: 'string'}},
    basis: {type: 'string'},
    caption: {type: 'string'},
    note: {
      type: 'object',
      required: ['title', 'body'],
      properties: {title: {type: 'string'}, body: {type: 'string'}},
    },
    bar: {
      type: 'object',
      description: 'derived — 생략 권장',
      properties: {
        supp: {type: 'number'}, meal: {type: 'number'},
        rdaMark: {type: ['number', 'null']}, ulMark: {type: ['number', 'null']},
      },
    },
    gauge: {
      type: 'object',
      description: 'derived — 생략 권장',
      properties: {rda: {type: ['number', 'null']}, ul: {type: ['number', 'null']}},
    },
  },
};

const REPORT_JSON_SCHEMA = {
  $schema: 'http://json-schema.org/draft-07/schema#',
  title: 'MyHerbReport',
  type: 'object',
  required: ['input', 'badges', 'exam', 'nutrients', 'issues', 'recommend', 'summary'],
  properties: {
    meta: {
      type: 'object',
      properties: {
        generatedAt: {type: 'string', description: 'ISO 8601'},
        source: {type: 'string', enum: ['mock', 'server']},
        engine: {type: 'string'},
      },
    },
    input: {
      type: 'object',
      required: ['name', 'age', 'sex', 'date', 'products', 'meds'],
      properties: {
        name: {type: 'string'},
        age: {type: ['string', 'number']},
        sex: {type: 'string', enum: ['남성', '여성', '']},
        date: {type: 'string', description: 'YYYY-MM-DD'},
        countMeal: {type: 'boolean'},
        chronic: {type: 'array', items: {type: 'string'}},
        products: {
          type: 'array',
          items: {
            type: 'object',
            required: ['name', 'items'],
            properties: {
              name: {type: 'string'},
              items: {
                type: 'array',
                items: {
                  type: 'object',
                  required: ['name', 'amount', 'unit'],
                  properties: {
                    name: {type: 'string'},
                    amount: {type: 'number'},
                    unit: {type: 'string', enum: ['mg', 'µg', 'g', 'IU', 'mL', '억CFU']},
                  },
                },
              },
            },
          },
        },
        meds: {
          type: 'array',
          items: {
            type: 'object',
            required: ['name'],
            properties: {name: {type: 'string'}, desc: {type: 'string'}},
          },
        },
      },
    },
    hasSupp:  {type: 'boolean'},
    mealOnly: {type: 'boolean'},
    cols:     {type: 'integer', minimum: 1, maximum: 4, description: 'derived — 생략 가능'},
    worst:    {type: 'string', enum: LEVELS, description: 'derived — 생략 가능'},
    badges: {
      type: 'array',
      items: {
        type: 'object',
        required: ['text', 'tone'],
        properties: {text: {type: 'string'}, tone: {type: 'string', enum: TONES}},
      },
    },
    exam: {
      type: 'object',
      required: ['overall', 'filled', 'counts', 'groups', 'rows', 'abnormal'],
      properties: {
        overall: {
          type: 'object',
          required: ['label', 'tone', 'desc'],
          properties: {
            label: {type: 'string'},
            tone: {type: 'string', enum: TONES},
            desc: {type: 'string'},
          },
        },
        filled: {type: 'integer', minimum: 0},
        counts: {
          type: 'object',
          properties: {A: {type: 'integer'}, B: {type: 'integer'}, D: {type: 'integer'}},
        },
        groups: {
          type: 'array',
          items: {
            type: 'object',
            required: ['group', 'rows'],
            properties: {
              group: {type: 'string'},
              rows: {type: 'array', items: examRowDef},
            },
          },
        },
        rows:     {type: 'array', items: examRowDef},
        abnormal: {type: 'array', items: examRowDef},
      },
    },
    nutrients: {type: 'array', items: nutrientDef},
    issues: {
      type: 'array',
      items: {
        type: 'object',
        required: ['kind', 'tone', 'text'],
        properties: {
          kind: {type: 'string', description: '상한 초과 · 상한 근접 · 성분 중복 · 환산 불가 등'},
          tone: {type: 'string', enum: TONES},
          text: {type: 'string'},
          med:  {type: 'string', description: '이 경고를 일으킨 약 이름. 헤더 복약 열과 연결됩니다.'},
        },
      },
    },
    recommend: {
      type: 'object',
      required: ['title', 'desc', 'items'],
      properties: {
        title: {type: 'string'},
        desc: {type: 'string'},
        advice: {type: 'string'},
        more: {type: 'integer', minimum: 0},
        moreText: {type: 'string'},
        note: {type: 'string'},
        items: {
          type: 'array',
          maxItems: 6,
          items: {
            type: 'object',
            required: ['name', 'reason', 'tone'],
            properties: {
              name: {type: 'string'},
              amount: {type: 'string', description: '"120mg 더" 처럼 단위까지 포함한 문자열'},
              reason: {type: 'string'},
              caution: {type: 'string'},
              tone: {type: 'string', enum: TONES},
            },
          },
        },
      },
    },
    summary: {
      type: 'object',
      required: ['text', 'chips'],
      properties: {
        text: {type: 'string'},
        chips: {
          type: 'array',
          items: {
            type: 'object',
            required: ['text', 'tone'],
            properties: {text: {type: 'string'}, tone: {type: 'string', enum: TONES}},
          },
        },
      },
    },
  },
};

module.exports = {TONES, LEVELS, JUDGE_CODES, EDIT_TARGETS, FIELD_MAP, REPORT_JSON_SCHEMA};
