# pipeline — 프롬프트 → 데이터(JSON) → HTML

`src/report.html` 은 뼈대만 있고, 실제 화면은 `src/app.js` 의 `renderReport(m)` 가
**Report 객체 하나**로부터 만들어 냅니다. 이 폴더는 그 Report 객체를
LLM 에게 받아 파일로 남기고, Node 에서 정적 HTML 로 뽑아 내는 세 단계를 담습니다.

```
generatePromptTemplate()  주제 → LLM 프롬프트 문자열
        ↓  (LLM 호출)
saveDataToFile()          응답(JSON) → out/report-data.json
        ↓
renderHtmlFromData()      데이터 → out/output.html   ← styles.css 를 심어 파일 하나로 완결
```

## 실행

```bash
node pipeline/example.js
```

만들어지는 것 — `pipeline/out/`

| 파일 | 내용 |
|---|---|
| `prompt.txt` | LLM 에 보낼 프롬프트 (스키마 포함, 약 22,000자) |
| `report-data.json` | 저장된 가변 데이터 |
| `output.html` | 완성된 리포트 (CSS 내장, 브라우저에서 바로 열림) |
| `output-empty.html` | 데이터가 거의 없을 때의 기본값 동작 확인용 |

## 파일

| 파일 | 하는 일 |
|---|---|
| `schema.js` | 가변 데이터 규격 — JSON Schema + 가변요소 목록 + tone/level 이름 |
| `prompt.js` | `generatePromptTemplate(topic, params)` |
| `storage.js` | `saveDataToFile(data, path, opts)` · `loadDataFromFile` · `validateReport` |
| `renderer.js` | `renderHtmlFromData(data, opts)` — app.js 와 같은 마크업 |
| `sample-data.json` | 스키마를 다 채운 예시 데이터 (example.js 가 LLM 응답 대신 씁니다) |
| `index.js` | 세 함수를 묶은 진입점 |

## 규칙 두 가지

1. **색값은 데이터에 넣지 않습니다.** `tone` 이름(`green` `orange` `red` `crit`
   `blue` `gray`)만 주고, 실제 색은 `renderer.js` 의 `TONE` 표가 정합니다.
   app.js 의 `[A] 화면 토큰` 과 같은 약속입니다.
2. **좌표는 LLM 이 계산하지 않습니다.** `supp` `meal` `rda` `ul` 숫자만 주면
   `bar`(막대 길이·눈금 위치)·`gauge`(게이지 비율)·`level`·`cols`·`worst` 를
   렌더러가 app.js 와 똑같은 식으로 계산합니다.

## 실제 LLM 붙이기

`example.js` 의 `callLlm()` 을 이렇게 바꾸면 됩니다.

```js
const Anthropic = require('@anthropic-ai/sdk');
const client = new Anthropic();               // ANTHROPIC_API_KEY 환경변수

async function callLlm(prompt){
  const res = await client.messages.create({
    model: 'claude-opus-5',
    max_tokens: 8000,
    system: SYSTEM_PROMPT,
    messages: [{role: 'user', content: prompt}],
  });
  return res.content.map(b => b.text || '').join('');
}
```

응답에 ```` ```json ```` 코드펜스가 붙어 와도 `saveDataToFile` 이 벗겨 냅니다.

## 서버(Python)와의 관계

`server.py` 가 내려주는 `/api/analyze` 응답이 이 스키마와 같은 모양입니다.
서버 응답을 그대로 `renderHtmlFromData()` 에 넣으면 브라우저 없이도
같은 화면을 PDF·메일용 정적 HTML 로 만들 수 있습니다.
