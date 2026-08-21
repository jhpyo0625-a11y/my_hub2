'use strict';
/* =========================================================================
   index.js — 파이프라인 진입점
   -------------------------------------------------------------------------
     generatePromptTemplate  주제 → LLM 프롬프트 문자열
     saveDataToFile          JS 객체 / JSON 문자열 → .json 파일
     renderHtmlFromData      JS 객체 → 완성된 HTML (원하면 output.html 로 저장)

   사용 예)
     const {generatePromptTemplate, saveDataToFile, renderHtmlFromData}
       = require('./pipeline');
   ========================================================================= */

const {generatePromptTemplate, SYSTEM_PROMPT} = require('./prompt');
const {saveDataToFile, loadDataFromFile, parseMaybeJson, validateReport} = require('./storage');
const {renderHtmlFromData, normalizeReport} = require('./renderer');
const schema = require('./schema');

module.exports = {
  /* [1] 프롬프트 */
  generatePromptTemplate, SYSTEM_PROMPT,
  /* [2] 저장 */
  saveDataToFile, loadDataFromFile, parseMaybeJson, validateReport,
  /* [3] 렌더 */
  renderHtmlFromData, normalizeReport,
  /* 규격 */
  schema,
};
