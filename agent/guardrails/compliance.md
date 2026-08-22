# Compliance 가드레일 (최종 = 포맷 + PII)

## pre
- `aggregated_report`가 state에 존재.

## post — 포맷
- `final_report.html`는 비어있지 않은 str.
- `final_report.disclaimer`에 "의료법상" 정문구 포함.

## post — PII (항상 차단)
- 원본 name/birth_date(normalized_data)가 html에 평문으로 나타나지 않음.
- `final_report.user_profile.name`이 원본과 다름(마스킹됨).
- 주민등록번호(예: 000000-0000000)·전화번호(01x-xxxx-xxxx) 정규식 패턴 미노출.

PII 범위: 이름·생년월일·주민등록번호·전화번호. 입력 필드가 늘면 여기에 추가.
