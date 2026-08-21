'use strict';
/* =========================================================================
   storage.js — [2] 데이터 파일 저장
   -------------------------------------------------------------------------
   LLM 이 돌려준 인풋 데이터(JS 객체 또는 JSON 문자열)를 .json 파일로
   남깁니다. 파이프라인의 중간 산출물이자, 나중에 같은 리포트를 다시
   그릴 때 쓰는 원본입니다.
   ========================================================================= */

const fs = require('fs');
const path = require('path');

const {REPORT_JSON_SCHEMA} = require('./schema');

/* -------------------------------------------------------------------------
   LLM 응답 다듬기 — 코드펜스나 앞뒤 잡소리가 붙어 와도 살려 냅니다.
   ------------------------------------------------------------------------- */
function parseMaybeJson(input){
  if(input && typeof input === 'object') return input;
  let s = String(input ?? '').trim();

  /* ```json ... ``` 로 감싸 온 경우 */
  const fence = s.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if(fence) s = fence[1].trim();

  try { return JSON.parse(s); } catch(e){ /* 아래에서 한 번 더 시도 */ }

  /* 문장 사이에 객체만 박혀 온 경우 — 첫 { 부터 마지막 } 까지 */
  const a = s.indexOf('{'), b = s.lastIndexOf('}');
  if(a >= 0 && b > a){
    try { return JSON.parse(s.slice(a, b + 1)); } catch(e){ /* fallthrough */ }
  }
  throw new Error('JSON 으로 읽을 수 없는 데이터입니다. LLM 응답을 확인하세요.');
}

/* -------------------------------------------------------------------------
   가벼운 검사 — 스키마의 required 만 훑습니다.
   못 채운 필드가 있어도 던지지 않고 목록으로 알려 줍니다(렌더러가 기본값으로
   메우기 때문에, 여기서 막으면 오히려 화면을 못 보게 됩니다).
   strict:true 로 부르면 그때는 예외를 던집니다.
   ------------------------------------------------------------------------- */
function validateReport(data, {strict = false} = {}){
  const missing = [];
  const req = REPORT_JSON_SCHEMA.required || [];
  req.forEach(k => { if(data == null || data[k] === undefined) missing.push(k); });

  const input = (data && data.input) || {};
  (((REPORT_JSON_SCHEMA.properties.input || {}).required) || [])
    .forEach(k => { if(input[k] === undefined) missing.push(`input.${k}`); });

  if(Array.isArray(data && data.nutrients)){
    data.nutrients.forEach((n, i) => {
      ['name', 'unit', 'supp', 'meal'].forEach(k => {
        if(n == null || n[k] === undefined) missing.push(`nutrients[${i}].${k}`);
      });
    });
  }

  if(strict && missing.length)
    throw new Error(`필수 필드가 빠졌습니다: ${missing.join(', ')}`);
  return {ok: missing.length === 0, missing};
}

/**
 * 인풋 데이터를 .json 파일로 저장합니다.
 *
 * @param {object|string} data      JS 객체 또는 JSON 문자열(코드펜스 허용)
 * @param {string} filePath         저장 경로. 확장자가 없으면 .json 을 붙입니다.
 * @param {object} [opts]
 *   pretty   {boolean|number} 기본 2칸 들여쓰기. false 면 한 줄로.
 *   backup   {boolean} 같은 이름이 이미 있으면 .bak 으로 밀어 둡니다. 기본 false.
 *   stamp    {boolean} 파일명 뒤에 -YYYYMMDD-HHmmss 를 붙입니다. 기본 false.
 *   validate {boolean} 저장 전에 필수 필드를 확인합니다. 기본 true(경고만).
 *   strict   {boolean} 필수 필드가 빠지면 저장하지 않고 예외를 던집니다.
 * @returns {{path:string, bytes:number, missing:string[]}}
 */
function saveDataToFile(data, filePath, opts = {}){
  const {
    pretty = 2, backup = false, stamp = false,
    validate = true, strict = false,
  } = opts;

  if(!filePath) throw new Error('저장 경로(filePath)가 필요합니다.');
  const obj = parseMaybeJson(data);

  let missing = [];
  if(validate){
    const r = validateReport(obj, {strict});
    missing = r.missing;
    if(missing.length) console.warn('[saveDataToFile] 빠진 필드:', missing.join(', '));
  }

  /* 경로 정리 — 확장자 · 타임스탬프 · 상위 폴더 */
  let out = path.resolve(filePath);
  if(!path.extname(out)) out += '.json';
  if(stamp){
    const d = new Date(), z = n => String(n).padStart(2, '0');
    const tag = `${d.getFullYear()}${z(d.getMonth() + 1)}${z(d.getDate())}-` +
                `${z(d.getHours())}${z(d.getMinutes())}${z(d.getSeconds())}`;
    const ext = path.extname(out);
    out = path.join(path.dirname(out), `${path.basename(out, ext)}-${tag}${ext}`);
  }
  fs.mkdirSync(path.dirname(out), {recursive: true});

  if(backup && fs.existsSync(out)) fs.copyFileSync(out, out + '.bak');

  const json = pretty === false
    ? JSON.stringify(obj)
    : JSON.stringify(obj, null, typeof pretty === 'number' ? pretty : 2);

  /* 같은 폴더에 임시로 쓴 뒤 바꿔치기 — 쓰다 만 파일이 남지 않게 */
  const tmp = out + '.tmp';
  fs.writeFileSync(tmp, json + '\n', 'utf8');
  fs.renameSync(tmp, out);

  return {path: out, bytes: Buffer.byteLength(json, 'utf8'), missing};
}

/** 저장해 둔 .json 을 다시 읽습니다. */
function loadDataFromFile(filePath){
  const p = path.resolve(filePath);
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

module.exports = {saveDataToFile, loadDataFromFile, parseMaybeJson, validateReport};
