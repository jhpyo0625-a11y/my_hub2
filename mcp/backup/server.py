import os
from typing import Dict, Any, Optional
from fastmcp import FastMCP

# 1. FastMCP 인스턴스 생성
mcp = FastMCP("Precision Nutrition & Supplement Server")

# -----------------------------------------------------------------------------
# TOOL 1: 체중당 영양소 섭취 산출 툴 (Nutrient Intake Calculator)
# -----------------------------------------------------------------------------
@mcp.tool()
async def calculate_precision_nutrition(
    gender: str = "male",
    weight_kg: Optional[float] = None,
    height_cm: Optional[float] = None,
    age_years: Optional[int] = None,
    activity_level: str = "moderately_active",
    is_menstruating: bool = False,
    is_postmenopausal: bool = False
) -> Dict[str, Any]:
    """
    임상 가이드라인(Mifflin-St Jeor) 수식을 기반으로 사용자의 기초대사량(BMR), 
    일일 총 에너지 소비량(TDEE), 매크로 영양소 그람수 및 미크로 영양소 권장량을 정밀 산출합니다.
    신체 정보가 누락된 경우 가이드북의 성인 표준 기준(남성, 40세, 80kg, 175cm, 2400kcal 수준)을 자동 적용합니다.
    
    :param gender: 'male' 또는 'female'
    :param weight_kg: 체중 (kg)
    :param height_cm: 신장 (cm)
    :param age_years: 나이 (세)
    :param activity_level: 'sedentary', 'lightly_active', 'moderately_active', 'very_active', 'extra_active'
    :param is_menstruating: 여성인 경우 월경 여부 (가임기 철분 산출용)
    :param is_postmenopausal: 여성인 경우 완경 여부 (칼슘 산출용)
    """

    # 0. 정보가 누락되었을 경우 가이드북의 '성인 표준 프로필' 강제 주입
    is_default_profile = False
    if weight_kg is None or height_cm is None or age_years is None:
        weight_kg = 80.0
        height_cm = 175.0
        age_years = 40
        activity_level = "moderately_active" # 80kg 기준 약 2400kcal를 맞추기 위한 활동량
        is_default_profile = True

    # 1. BMR 계산 (Mifflin-St Jeor)
    if gender.lower() == "male":
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years) - 161

    # 2. TDEE 계산 (활동 계수 반영)
    pal_factors = {
        "sedentary": 1.20,
        "lightly_active": 1.375,
        "moderately_active": 1.55,
        "very_active": 1.725,
        "extra_active": 1.90
    }
    pal = pal_factors.get(activity_level.lower(), 1.20)
    tdee = bmr * pal

    # 3. 매크로 영양소 산출 (Atwater 계수 및 가이드라인 반영)
    # 탄수화물 60%, 단백질 15%, 지방 25% 할당 기준
    carbs_g = (tdee * 0.60) / 4
    protein_g = (tdee * 0.15) / 4
    fats_g = (tdee * 0.25) / 9
    saturated_fat_g = (tdee * 0.07) / 9  # 포화지방 7% 제한
    fiber_g = (tdee / 1000) * 14          # 식이섬유 공식

    # 4. 미크로 영양소 산출 (가이드북 수식 반영)
    # Type A: 에너지 처리 의존성 (1,000 kcal당 할당)
    vitamin_b1_mg = 0.5 * (tdee / 1000)
    vitamin_b2_mg = 0.6 * (tdee / 1000)
    vitamin_b3_mg = 6.6 * (tdee / 1000)

    # Type B: 섭취 단백질량 의존성 (단백질 1g당 0.02mg)
    vitamin_b6_mg = 0.02 * protein_g

    # 철분(Iron) 판정
    if gender.lower() == "male":
        iron_mg = 10.0
    else:
        iron_mg = 16.0 if is_menstruating else 10.0  # 가임기 14~18mg 중간값 적용

    # Type C: 생애주기 의존성 (칼슘, 비타민D)
    # 칼슘(Calcium) 판정
    if age_years <= 18:
        calcium_mg = 1150.0  # 성장기 평균
    elif gender.lower() == "female" and is_postmenopausal:
        calcium_mg = 1000.0  # 완경 여성 증가 양상
    else:
        calcium_mg = 750.0   # 성인 표준

    # 비타민 D 판정
    vitamin_d_mcg = 20.0 if age_years > 65 else 10.0

    # 나트륨 제한선
    sodium_cap_mg = 1500.0 if age_years <= 10 else 2300.0

    return {
        "energy_metrics": {
            "bmr_kcal": round(bmr, 1),
            "tdee_kcal": round(tdee, 1)
        },
        "macronutrients_g": {
            "carbohydrates": round(carbs_g, 1),
            "protein": round(protein_g, 1),
            "fats": round(fats_g, 1),
            "saturated_fat_limit": round(saturated_fat_g, 1),
            "dietary_fiber_goal": round(fiber_g, 1)
        },
        "micronutrients_target": {
            "vitamin_b1_thiamine_mg": round(vitamin_b1_mg, 2),
            "vitamin_b2_riboflavin_mg": round(vitamin_b2_mg, 2),
            "vitamin_b3_niacin_mg": round(vitamin_b3_mg, 2),
            "vitamin_b6_pyridoxine_mg": round(vitamin_b6_mg, 2),
            "iron_fe_mg": round(iron_mg, 1),
            "calcium_ca_mg": round(calcium_mg, 1),
            "vitamin_d_mcg": round(vitamin_d_mcg, 1),
            "sodium_na_limit_mg": sodium_cap_mg
        }
    }

# -----------------------------------------------------------------------------
# TOOL 2: KDRI 기반 코드 단위 비교 및 환산 툴
# -----------------------------------------------------------------------------
@mcp.tool()
async def normalize_supplement_component(nutrient_code: str, current_value: float, current_unit: str) -> Dict[str, Any]:
    """
    영양소 표준 코드(nutrient_code)를 기반으로 현재 단위와 KDRI 표준 단위를 비교한 후,
    일치하지 않을 경우 표준 단위 규격에 맞게 값을 정밀 환산(Conversion)합니다.
    
    :param nutrient_code: 영양소 고유 코드 (예: thiamin, vitamin_d, iron, calcium, folate 등)
    :param current_value: 현재 영양제 제품에 표기된 수치값 (예: 400, 1.5, 500)
    :param current_unit: 현재 영양제 제품에 표기된 단위 (예: IU, g, mg, mcg, ug, ㎍)
    """
    # 1. 2025 KDRI 스펙 명세 (코드 타겟 매핑)
    kdri_specs = {
        "alpha_linolenic_acid": {"ko": "알파-리놀렌산", "unit": "g"},
        "biotin": {"ko": "비오틴", "unit": "μg"},
        "calcium": {"ko": "칼슘", "unit": "mg"},
        "carbohydrate": {"ko": "탄수화물", "unit": "g"},
        "chloride": {"ko": "염소", "unit": "mg"},
        "choline": {"ko": "콜린", "unit": "mg"},
        "chromium": {"ko": "크롬", "unit": "μg"},
        "copper": {"ko": "구리", "unit": "μg"},
        "dietary_fiber": {"ko": "식이섬유", "unit": "g"},
        "energy": {"ko": "에너지", "unit": "kcal"},
        "epa_dha": {"ko": "EPA+DHA", "unit": "mg"},
        "fluoride": {"ko": "불소", "unit": "mg"},
        "folate": {"ko": "엽산", "unit": "μg DFE"},
        "histidine": {"ko": "히스티딘", "unit": "g"},
        "iodine": {"ko": "요오드", "unit": "μg"},
        "iron": {"ko": "철", "unit": "mg"},
        "isoleucine": {"ko": "이소류신", "unit": "g"},
        "leucine": {"ko": "류신", "unit": "g"},
        "linoleic_acid": {"ko": "리놀레산", "unit": "g"},
        "lipid": {"ko": "지질", "unit": "g"},
        "lysine": {"ko": "라이신", "unit": "g"},
        "magnesium": {"ko": "마그네슘", "unit": "mg"},
        "manganese": {"ko": "망간", "unit": "mg"},
        "methionine_cysteine": {"ko": "메티오닌+시스테인", "unit": "g"},
        "molybdenum": {"ko": "몰리브덴", "unit": "μg"},
        "niacin": {"ko": "니아신", "unit": "mg NE"},
        "pantothenic_acid": {"ko": "판토텐산", "unit": "mg"},
        "phenylalanine_tyrosine": {"ko": "페닐알라닌+티로신", "unit": "g"},
        "phosphorus": {"ko": "인", "unit": "mg"},
        "potassium": {"ko": "칼륨", "unit": "mg"},
        "protein": {"ko": "단백질", "unit": "g"},
        "riboflavin": {"ko": "리보플라빈", "unit": "mg"},
        "selenium": {"ko": "셀레늄", "unit": "μg"},
        "sodium": {"ko": "나트륨", "unit": "mg"},
        "thiamin": {"ko": "티아민", "unit": "mg"},
        "threonine": {"ko": "트레오닌", "unit": "g"},
        "tryptophan": {"ko": "트립토판", "unit": "g"},
        "valine": {"ko": "발린", "unit": "g"},
        "vitamin_a": {"ko": "비타민 A", "unit": "μg RAE"},
        "vitamin_b12": {"ko": "비타민 B12", "unit": "μg"},
        "vitamin_b6": {"ko": "비타민 B6", "unit": "mg"},
        "vitamin_c": {"ko": "비타민 C", "unit": "mg"},
        "vitamin_d": {"ko": "비타민 D", "unit": "μg"},
        "vitamin_e": {"ko": "비타민 E", "unit": "mg α-TE"},
        "vitamin_k": {"ko": "비타민 K", "unit": "μg"},
        "water": {"ko": "수분", "unit": "mL"},
        "zinc": {"ko": "아연", "unit": "mg"}
    }

    # 2. 코드 존재 여부 검증
    target_code = nutrient_code.lower().strip()
    if target_code not in kdri_specs:
        return {
            "status": "error",
            "message": f"입력된 영양소 코드 '{nutrient_code}'는 시스템 표준 규격에 존재하지 않습니다."
        }

    spec = kdri_specs[target_code]
    standard_unit = spec["unit"]

    # 3. 단위 문자열 정규화 처리 (ug, ㎍, MG 등 기호 표기 통일)
    def clean_unit_string(u: str) -> str:
        u_lower = u.lower().strip().replace(" ", "")
        if u_lower in ["ug", "㎍", "mcg"]: return "μg"
        if u_lower == "mgne": return "mg ne"
        if u_lower == "mgα-te": return "mg α-te"
        if u_lower == "μgdfe": return "μg dfe"
        if u_lower == "μgrae": return "μg rae"
        return u_lower

    input_unit_clean = clean_unit_string(current_unit)
    standard_unit_clean = clean_unit_string(standard_unit)

    # 4. 단위 일치 여부 확인 및 환산 로직
    is_matching = (input_unit_clean == standard_unit_clean)
    converted_value = current_value

    if not is_matching:
        # A. 비타민 D 특수 변환 (현재 단위가 IU인 경우 표준 단위인 μg로 환산)
        if target_code == "vitamin_d" and input_unit_clean == "iu":
            converted_value = current_value / 40.0
        # B. 비타민 A 특수 변환 (현재 단위가 IU인 경우 표준 단위인 μg RAE로 환산)
        elif target_code == "vitamin_a" and input_unit_clean == "iu":
            converted_value = current_value / 3.33
        # C. 비타민 E 특수 변환 (현재 단위가 IU인 경우 표준 단위인 mg α-TE로 환산)
        elif target_code == "vitamin_e" and input_unit_clean == "iu":
            converted_value = current_value / 1.49
        
        # D. 일반 무게 스케일 변환 (g -> mg)
        elif input_unit_clean == "g" and "mg" in standard_unit_clean:
            converted_value = current_value * 1000.0
        # E. 일반 무게 스케일 변환 (mg -> μg)
        elif input_unit_clean == "mg" and "μg" in standard_unit_clean:
            converted_value = current_value * 1000.0
        # F. 일반 무게 스케일 변환 (μg -> mg)
        elif input_unit_clean == "μg" and "mg" in standard_unit_clean:
            converted_value = current_value / 1000.0
        # G. 그 외 변환할 수 없는 예외 단위 처리
        else:
            return {
                "status": "warning",
                "message": f"현재 단위 '{current_unit}'에서 표준 단위 '{standard_unit}'(으)로의 환산 규칙이 정의되지 않았습니다.",
                "is_unit_matched": False,
                "original_input": {"code": target_code, "value": current_value, "unit": current_unit},
                "standard_spec": {"nutrient_ko": spec["ko"], "standard_unit": standard_unit}
            }

    # 5. 최종 데이터 모델 리턴
    return {
        "status": "success",
        "is_unit_matched": is_matching,
        "nutrient_info": {
            "nutrient_code": target_code,
            "nutrient_ko": spec["ko"]
        },
        "conversion_result": {
            "original_input": f"{current_value} {current_unit}",
            "standard_value": round(converted_value, 2),
            "standard_unit": standard_unit
        }
    }


if __name__ == "__main__":
    mcp.run()
