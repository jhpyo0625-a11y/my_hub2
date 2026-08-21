#!/usr/bin/env node
'use strict';
/* =========================================================================
   example.js — 전체 파이프라인 한 번에 돌려 보기
   -------------------------------------------------------------------------
     $ node pipeline/example.js

     [1] 프롬프트 생성   generatePromptTemplate()  → out/prompt.txt
     [2] LLM 호출        (여기서는 가짜 응답. 실제 호출 코드는 아래 주석)
     [3] 데이터 저장     saveDataToFile()          → out/report-data.json
     [4] HTML 렌더       renderHtmlFromData()      → out/output.html

   마지막에 '데이터가 거의 비었을 때'도 한 장 그려서, 기본값 처리가
   실제로 동작하는지 눈으로 확인할 수 있게 해 둡니다 → out/output-empty.html
   ========================================================================= */

const path = require('path');
const fs = require('fs');

const {
  generatePromptTemplate, SYSTEM_PROMPT,
  saveDataToFile, loadDataFromFile,
  renderHtmlFromData,
} = require('./index');

const OUT = path.join(__dirname, 'out');
const rel = p => path.relative(process.cwd(), p).replace(/\\/g, '/');

/* =========================================================================
   [1] 프롬프트 생성
   ========================================================================= */
const prompt = generatePromptTemplate('30대 직장인 남성의 영양제 섭취 리포트', {
  persona : '사무직 · 야근이 잦고 배달 음식을 자주 먹음',
  age     : 34,
  sex     : '남성',
  date    : '2026-08-21',
  products: ['종합비타민 A', '마그네슘 400', '오메가3 1000'],
  meds    : ['와파린'],
  countMeal: true,
  nutrientCount: 6,
  examSummary : '혈압·공복혈당·LDL 이 기준을 벗어남',
  extra   : '마그네슘이 상한을 넘는 상황을 포함할 것',
});

fs.mkdirSync(OUT, {recursive: true});
fs.writeFileSync(path.join(OUT, 'prompt.txt'), prompt, 'utf8');
console.log(`[1] 프롬프트 ${prompt.length.toLocaleString()}자 → ${rel(path.join(OUT, 'prompt.txt'))}`);

/* =========================================================================
   [2] LLM 호출
   -------------------------------------------------------------------------
   실제로는 아래처럼 부릅니다. 여기서는 예제를 오프라인에서 돌릴 수 있도록
   같은 모양의 응답을 그대로 적어 두었습니다(코드펜스까지 붙여서 —
   parseMaybeJson 이 벗겨 냅니다).

     const Anthropic = require('@anthropic-ai/sdk');
     const client = new Anthropic();                      // ANTHROPIC_API_KEY
     const res = await client.messages.create({
       model: 'claude-opus-5',
       max_tokens: 8000,
       system: SYSTEM_PROMPT,
       messages: [{role: 'user', content: prompt}],
     });
     const raw = res.content.map(b => b.text || '').join('');
   ========================================================================= */
async function callLlm(_prompt){
  return '```json\n' + JSON.stringify(SAMPLE_RESPONSE, null, 2) + '\n```';
}

/* =========================================================================
   [3][4] 저장 → 렌더
   ========================================================================= */
async function main(){
  const raw = await callLlm(prompt);
  console.log(`[2] LLM 응답 ${raw.length.toLocaleString()}자 (코드펜스 포함)`);

  /* 문자열 그대로 넘겨도 됩니다 — 코드펜스를 벗기고 JSON 으로 읽습니다. */
  const saved = saveDataToFile(raw, path.join(OUT, 'report-data.json'), {backup: true});
  console.log(`[3] 데이터 저장 ${saved.bytes.toLocaleString()}B → ${rel(saved.path)}` +
              (saved.missing.length ? `  (빠진 필드 ${saved.missing.length}개)` : '  (필수 필드 이상 없음)'));

  /* 저장한 파일에서 다시 읽어 렌더 — 파일만 있으면 언제든 같은 화면이 나옵니다 */
  const data = loadDataFromFile(saved.path);
  const html = renderHtmlFromData(data, {
    outFile: path.join(OUT, 'output.html'),
    title  : `MyHerb · ${data.input.name} 님의 리포트`,
  });
  console.log(`[4] HTML 렌더 ${html.length.toLocaleString()}자 → ${rel(path.join(OUT, 'output.html'))}`);

  /* -----------------------------------------------------------------------
     기본값(Fallback) 확인 — 필드가 거의 없는 데이터로도 화면이 서는지
     ----------------------------------------------------------------------- */
  const bare = {input: {name: '', products: [], meds: []}, nutrients: [{name: '비타민C', unit: 'mg', supp: 500}]};
  renderHtmlFromData(bare, {outFile: path.join(OUT, 'output-empty.html'), title: 'MyHerb · 빈 데이터 테스트'});
  console.log(`[+] 빈 데이터 렌더 → ${rel(path.join(OUT, 'output-empty.html'))}`);

  console.log('\n브라우저에서 out/output.html 을 열어 보세요.');
}

/* =========================================================================
   가짜 LLM 응답 — 스키마를 그대로 채운 예시
   (bar·gauge·total·cols·worst 는 일부러 넣지 않았습니다. 렌더러가 계산합니다)
   실제 파일: pipeline/sample-data.json
   ========================================================================= */
const SAMPLE_RESPONSE = require('./sample-data.json');

main().catch(e => { console.error(e); process.exit(1); });
