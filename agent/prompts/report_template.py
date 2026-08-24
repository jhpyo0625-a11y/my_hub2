# -*- coding: utf-8 -*-
"""결정적(Jinja2) 리포트 렌더러 — 숫자/표/게이지는 전부 여기서 그린다.

불변식(TB-1): **LLM은 숫자를 생성하지 않는다.** 이 템플릿이 받는 모든 값은
engine/MCP 결과(aggregated_report)에서 유래하며, LLM은 오직 `prose`(설명 산문)만
채운다. prose 조차 숫자 부분집합 검증을 통과한 것만 주입된다(nodes/compliance.py).

디자인은 prompts/report_1.html 의 섹션 구조(hero, card, intake 등)를 차용하되
226KB 인라인 CSS는 복사하지 않고 최소 스타일만 둔다.

case*.json 대비 채운/비운 섹션:
  채움  : hero(profile), 산문(prose, 선택), nutrients(권장/충족률), ul_check,
          timing(복용시간), lab_results, products, guidelines
  비움  : exam.groups/badges/summary.chips/nutrients.bar·gauge —
          현 aggregated_report 에 원천 데이터가 없어 조작하지 않고 생략한다.
"""
from jinja2 import Environment

_ENV = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)

_TEMPLATE = _ENV.from_string(
    """<section class="nutrition-report">
  <style>
    .nutrition-report{font-family:system-ui,'Malgun Gothic',sans-serif;max-width:860px;margin:0 auto;color:#1f2430;line-height:1.6}
    .nutrition-report .hero{background:#f4f7fb;border-radius:16px;padding:20px 24px;margin-bottom:20px}
    .nutrition-report h1{font-size:1.5rem;margin:0 0 6px}
    .nutrition-report h2{font-size:1.15rem;margin:26px 0 10px;border-left:4px solid #3b82f6;padding-left:10px}
    .nutrition-report .profile{color:#48506a;font-size:.95rem;margin:0}
    .nutrition-report .prose{white-space:pre-line;background:#fbfbfd;border:1px solid #e6e8ef;border-radius:12px;padding:14px 16px}
    .nutrition-report table{width:100%;border-collapse:collapse;font-size:.93rem}
    .nutrition-report th,.nutrition-report td{padding:7px 10px;border-bottom:1px solid #edeef3;text-align:left}
    .nutrition-report th{background:#f7f8fb;color:#5b6480}
    .nutrition-report .tag{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.8rem}
    .nutrition-report .tag.green{background:#e6f6ec;color:#1b7f42}
    .nutrition-report .tag.blue{background:#e7f0fe;color:#1c5bd0}
    .nutrition-report .tag.orange{background:#fdeede;color:#b5651b}
    .nutrition-report .tag.gray{background:#eef0f4;color:#6b7280}
    .nutrition-report .notice{background:#fff6e6;border:1px solid #f4d18a;border-radius:10px;padding:10px 14px;margin:14px 0;color:#8a5a12}
    .nutrition-report .cite{color:#8b93a7;font-size:.82rem}
    .nutrition-report .disclaimer{margin-top:28px;padding-top:14px;border-top:1px solid #e6e8ef;color:#7a8199;font-size:.85rem}
    .nutrition-report .empty{color:#9aa1b2;font-size:.9rem}
  </style>

  <div class="hero">
    <h1>{{ title }}</h1>
    <p class="profile">이름: {{ profile.name }} · 나이: {{ profile.age }} · 성별: {{ profile.gender }}{% if profile.weight %} · 체중: {{ profile.weight }}kg{% endif %}</p>
  </div>

  {% if failure_notice %}
  <div class="notice">일부 항목은 자동 검증을 완료하지 못해 이번 결과에서 제외되었습니다. 해당 항목은 전문가와 상담하시기를 권장드립니다.</div>
  {% endif %}

  {% if prose %}
  <h2>분석 요약</h2>
  <div class="prose">{{ prose }}</div>
  {% endif %}

  <h2>맞춤 권장 섭취량</h2>
  {% if nutrients %}
  <table>
    <thead><tr><th>영양소</th><th>맞춤 권장(RI)</th><th>충족률</th><th>상태</th></tr></thead>
    <tbody>
      {% for n in nutrients %}
      <tr>
        <td>{{ n.name }}</td>
        <td>{{ n.value }} {{ n.unit }}</td>
        <td>{% if n.pct is not none %}{{ n.pct }}%{% else %}—{% endif %}</td>
        <td>{% if n.status_label %}<span class="tag {{ n.status_tone }}">{{ n.status_label }}</span>{% else %}—{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="empty">산출된 목표치 없음</p>
  {% endif %}

  <h2>상한(UL) 안전 검증</h2>
  {% if ul_violations %}
  <table>
    <thead><tr><th>영양소</th><th>총 섭취</th><th>상한(UL)</th></tr></thead>
    <tbody>
      {% for u in ul_violations %}
      <tr><td>{{ u.nutrient }}</td><td>{{ u.total_intake }}</td><td>{{ u.ul_limit }}</td></tr>
      {% endfor %}
    </tbody>
  </table>
  {% else %}
  <p class="empty">상한 초과 항목 없음 — 안전합니다.</p>
  {% endif %}

  <h2>복용 시간</h2>
  <p>아침: {{ timing.am or '-' }} / 저녁: {{ timing.pm or '-' }}</p>
  {% if timing.cautions %}
  <ul>{% for c in timing.cautions %}<li>{{ c }}</li>{% endfor %}</ul>
  {% endif %}

  {% if lab_results %}
  <h2>검사 수치</h2>
  <table>
    <thead><tr><th>검사</th><th>값</th><th>판정</th></tr></thead>
    <tbody>
      {% for l in lab_results %}
      <tr><td>{{ l.test_name }}</td><td>{{ l.value }} {{ l.unit }}</td><td><span class="tag {{ l.flag_tone }}">{{ l.flag_label }}</span></td></tr>
      {% endfor %}
    </tbody>
  </table>
  {% endif %}

  <h2>추천 제품</h2>
  {% if products %}
  <ul>{% for p in products %}<li>{{ p.name }}{% if p.brand %} ({{ p.brand }}){% endif %}</li>{% endfor %}</ul>
  {% else %}
  <p class="empty">추천 제품 없음</p>
  {% endif %}

  <h2>참고 근거</h2>
  {% if guidelines %}
  <ul>{% for g in guidelines %}<li>{{ g.text }} <span class="cite">— {{ g.source }}</span></li>{% endfor %}</ul>
  {% else %}
  <p class="empty">참고 근거 없음</p>
  {% endif %}

  <footer class="disclaimer">{{ disclaimer }}</footer>
</section>"""
)


def render_report(context: dict) -> str:
    """결정적 HTML 렌더. context는 nodes/compliance._build_context 가 조립."""
    return _TEMPLATE.render(**context)
