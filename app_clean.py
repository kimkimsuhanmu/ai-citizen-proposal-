# -*- coding: utf-8 -*-
"""
AI시민제안 비서 - Flask 백엔드 서버
김포도시공사 프로토타입

주요 기능:
1. Google Gemini API를 통한 제안서 텍스트 생성
2. ReportLab을 통한 PDF 파일 생성 및 다운로드
3. 개인정보 수집 및 이용 동의서 포함
"""

import os
import re
import json
import logging
import time
from datetime import datetime
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
import google.generativeai as genai
import requests
from bs4 import BeautifulSoup
from fpdf import FPDF

# Flask 앱 초기화
app = Flask(__name__)
CORS(app)  # 프런트엔드와의 CORS 문제 해결

# 시설물 정보 저장소
facility_database = {}

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 환경 변수에서 Gemini API 키 가져오기
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

# 임시로 API 키를 직접 설정 (실제 키로 교체하세요)
if not GEMINI_API_KEY:
    # 여기에 실제 Gemini API 키를 입력하세요
    GEMINI_API_KEY = "AIzaSyCkmvlCtVGP6oOYr4wG0f87iEuoddG_P2Q"
    
if GEMINI_API_KEY == "your_actual_gemini_api_key_here" or not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY가 설정되지 않았습니다.")
    logger.info("테스트 모드로 실행됩니다. AI 텍스트 생성 기능은 제한됩니다.")
    GEMINI_API_KEY = "demo_key_for_testing"

# Gemini API 설정 (실제 키가 있을 때만)
if GEMINI_API_KEY != "demo_key_for_testing":
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        # 최신 API에서는 모델 이름이 다를 수 있으므로 여러 옵션 시도
        model_names = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro', 'gemini-1.5-pro']
        model = None
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                logger.info(f"Gemini API가 성공적으로 설정되었습니다. 모델: {model_name}")
                break
            except Exception as e:
                logger.warning(f"모델 {model_name} 초기화 실패: {e}")
                continue
        
        if model is None:
            raise Exception("사용 가능한 Gemini 모델을 찾을 수 없습니다")
    except Exception as e:
        logger.error(f"Gemini API 설정 오류: {e}")
        model = None
        GEMINI_API_KEY = "demo_key_for_testing"
else:
    model = None

# 한글 폰트 등록
def register_korean_fonts():
    """한글 폰트 등록"""
    try:
        # 나눔고딕 폰트 경로 (루트 디렉토리)
        font_paths = [
            'NanumGothic.otf',
            'NanumGothicBold.otf', 
            'NanumGothicExtraBold.otf',
            'NanumGothicLight.otf'
        ]
        
        for font_path in font_paths:
            if os.path.exists(font_path):
                try:
                    if font_path.endswith('.ttf'):
                        pdfmetrics.registerFont(TTFont('Korean', font_path))
                    else:  # .ttc 파일
                        pdfmetrics.registerFont(TTFont('Korean', font_path))
                    logger.info(f"한글 폰트 등록 성공: {font_path}")
                    return True
                except Exception as e:
                    logger.warning(f"폰트 등록 실패 {font_path}: {e}")
                    continue
        
        logger.warning("한글 폰트를 찾을 수 없습니다. 기본 폰트를 사용합니다.")
        return False
    except Exception as e:
        logger.error(f"폰트 등록 중 오류: {e}")
        return False

        # 폰트 등록 실행
register_korean_fonts()

def crawl_gimpo_facilities():
    """김포도시공사 홈페이지 크롤링 (시뮬레이션)"""
    logger.info("김포도시공사 홈페이지 크롤링 시작...")
    
    try:
        # 실제 크롤링 로직 (현재는 시뮬레이션)
        facilities = {}
        
        # 기본 시설물 정보 (실제로는 크롤링으로 수집)
        default_facilities = {
            "태산패밀리파크": "물놀이장, 조각공원, 야외공연장 등을 갖춘 김포시의 대표적인 가족 공원",
            "무지개 뜨는 언덕": "김포시의 공설봉안당으로 추모와 사색을 위한 실내 시설",
            "시민회관": "김포시의 문화행사와 시민활동을 위한 공공시설",
            "생활체육관": "김포시민들의 체육활동과 건강관리를 위한 종합체육시설",
            "도서관": "김포시민들의 독서와 학습을 위한 공공도서관"
        }
        
        # 기본 시설물 정보 사용
        facilities.update(default_facilities)
        
        logger.info(f"총 {len(facilities)}개 시설물 정보 수집 완료")
        return facilities
        
    except Exception as e:
        logger.error(f"시설물 크롤링 중 오류 발생: {str(e)}")
        return {}

def get_location_context(location_name):
    """장소 유형 및 특징 파악 (크롤링 데이터 우선 사용)"""
    try:
        # 크롤링 데이터에서 먼저 확인
        if location_name in facility_database:
            return facility_database[location_name]
        
        # AI를 통한 장소 분석 (크롤링 데이터가 없는 경우)
        if model is None:
            return "일반적인 공공시설"
        
        prompt = f"""
        다음 장소의 유형과 특징을 한 문장으로 요약해주세요:
        - "태산패밀리파크" → "물놀이장, 조각공원, 야외공연장 등을 갖춘 김포시의 대표적인 가족 공원"
        - "무지개 뜨는 언덕" → "김포시의 공설봉안당으로 추모와 사색을 위한 실내 시설"
        - "시민회관" → "김포시의 문화행사와 시민활동을 위한 공공시설"
        """
        
        response = model.generate_content(prompt)
        return response.text.strip()
        
    except Exception as e:
        logger.error(f"장소 정보 분석 오류: {e}")
        return "일반적인 공공시설"

def extract_key_elements(problem, solution):
    """사용자 입력에서 핵심 요소 추출"""
    # 장소명 추출 (간단한 패턴 매칭)
    location_patterns = [
        r'([가-힣]+(?:파크|공원|회관|관|센터|센타|광장|언덕|봉안당|도서관|체육관))',
        r'([가-힣]+(?:지하|층))',
        r'([가-힣]+(?:동|리|마을))'
    ]
    
    location = "김포시 시설"
    for pattern in location_patterns:
        match = re.search(pattern, problem + " " + solution)
        if match:
            location = match.group(1)
            break
    
    # 문제 대상 추출
    problem_targets = ["벤치", "의자", "주차장", "조명", "공간", "시설", "공원", "길", "도로"]
    problem_target = "시설"
    for target in problem_targets:
        if target in problem or target in solution:
            problem_target = target
            break
    
    # 핵심 문제 추출
    core_problem = problem.strip()
    
    # 요청 해결책 추출
    requested_solution = solution.strip()
    
    return {
        'location': location,
        'problem_target': problem_target,
        'core_problem': core_problem,
        'requested_solution': requested_solution
    }

def generate_appropriate_title(core_location, core_target, solution_idea):
    """핵심 내용을 파악하여 적절한 제안명 생성"""
    # 안전 관련
    if any(keyword in core_target for keyword in ["방화문", "안전문", "문이 열려", "문이 열린", "문 열림"]):
        return f"{core_location} 안전시설 점검 및 보강 제안"
    elif any(keyword in core_target for keyword in ["안전", "위험", "사고", "부상"]):
        return f"{core_location} 안전시설 보강 제안"
    
    # 주차 관련
    elif any(keyword in core_target for keyword in ["주차", "주차공간", "주차장"]):
        if any(keyword in core_target for keyword in ["부족", "없음", "많이"]):
            return f"{core_location} 주차공간 확충 제안"
        else:
            return f"{core_location} 주차시설 개선 제안"
    
    # 휴게시설 관련
    elif any(keyword in core_target for keyword in ["벤치", "의자", "앉을 곳", "휴게"]):
        if any(keyword in core_target for keyword in ["낡", "부족", "없음", "많이"]):
            return f"{core_location} 휴게시설 개선 제안"
        else:
            return f"{core_location} 휴게시설 설치 제안"
    
    # 편의시설 관련
    elif any(keyword in core_target for keyword in ["편의", "화장실", "음수대", "매점"]):
        return f"{core_location} 편의시설 설치 제안"
    
    # 조명 관련
    elif any(keyword in core_target for keyword in ["조명", "밝기", "어둡", "불빛"]):
        return f"{core_location} 조명시설 개선 제안"
    
    # 접근성 관련
    elif any(keyword in core_target for keyword in ["접근", "이동", "길", "보도"]):
        return f"{core_location} 접근성 개선 제안"
    
    # 청결/환경 관련
    elif any(keyword in core_target for keyword in ["청결", "깨끗", "쓰레기", "환경"]):
        return f"{core_location} 환경정리 및 청결관리 개선 제안"
    
    # 일반적인 시설 개선
    else:
        return f"{core_location} 시설 개선 제안"

def refine_user_input(core_location, core_target, problem_type, affected_people, solution_idea):
    """
    사용자 입력을 자연스러운 문장으로 변환 (1단계: 입력 정제)
    
    Args:
        core_location (str): 핵심 장소 (예: 태산패밀리파크)
        core_target (str): 핵심 대상 (예: 벤치가 낡았어요)
        problem_type (str): 문제 유형 (안전, 불편, 미관 등)
        affected_people (str): 주요 불편 대상 (어린이, 어르신 등)
        solution_idea (str): 해결책 아이디어 (예: 새로 바꿔주세요)
        
    Returns:
        dict: 정제된 사용자 입력
            {
                'refined_location': str,
                'refined_target': str,
                'refined_problem_description': str,
                'refined_solution': str,
                'success': bool
            }
    """
    try:
        # API 키 확인 및 모델 초기화
        api_key = os.getenv('GEMINI_API_KEY') or GEMINI_API_KEY
        
        if not api_key or api_key == "demo_key_for_testing":
            logger.warning("Gemini API 키가 없어 입력 정제를 건너뜁니다.")
            return {
                'refined_location': core_location,
                'refined_target': core_target,
                'refined_problem_description': f"{core_location}의 {core_target}에 대한 문제가 있습니다.",
                'refined_solution': solution_idea if solution_idea else "개선이 필요합니다.",
                'success': False
            }
        
        # AI 모델 초기화 (API 키가 있으면 항상 시도)
        try:
            # 최신 API에서는 모델 이름이 다를 수 있으므로 여러 옵션 시도
            model_names = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro', 'gemini-1.5-pro']
            ai_model = None
            for model_name in model_names:
                try:
                    ai_model = genai.GenerativeModel(model_name)
                    logger.info(f"입력 정제를 위한 Gemini 모델 초기화 완료: {model_name}")
                    break
                except Exception as e:
                    logger.warning(f"모델 {model_name} 초기화 실패: {e}")
                    continue
            
            if ai_model is None:
                raise Exception("사용 가능한 Gemini 모델을 찾을 수 없습니다")
        except Exception as e:
            logger.error(f"Gemini 모델 초기화 실패: {e}")
            return {
                'refined_location': core_location,
                'refined_target': core_target,
                'refined_problem_description': f"{core_location}의 {core_target}에 대한 문제가 있습니다.",
                'refined_solution': solution_idea if solution_idea else "개선이 필요합니다.",
                'success': False
            }
        
        # 입력 정제 프롬프트 구성 (개선된 버전)
        refine_prompt = f"""당신은 시민제안서 작성을 돕는 전문 AI 어시스턴트입니다.

[임무]
사용자가 입력한 구어체나 단편적인 내용을 공공기관 제안서에 적합한 자연스럽고 전문적인 문장으로 완전히 변환하세요.

[사용자 원본 입력]
- 장소: {core_location}
- 문제 대상: {core_target}
- 문제 유형: {problem_type if problem_type else '명시되지 않음'}
- 불편 대상: {affected_people if affected_people else '명시되지 않음'}
- 해결책: {solution_idea}

[변환 원칙]
1. **구어체 완전 제거**: 모든 구어체 표현을 정중한 문어체로 변환
   - "벤치가 낡았어요" → "벤치가 노후화되어"
   - "삐그덕거리고" → "불안정하고"
   - "보기에 안좋고" → "미관상 좋지 않고"
   - "위험해 보임" → "안전상 위험할 수 있어"

2. **단편적 표현 완전 확장**: 불완전한 문장을 완전한 문장으로 변환
   - "벤치교체 요함" → "기존 노후 벤치를 새로운 벤치로 교체할 것을 제안합니다"
   - "새로 바꿔주세요" → "기존 시설을 새로운 것으로 교체해 주실 것을 제안합니다"

3. **핵심 정보 보존**: 장소명, 대상, 요청사항은 절대 변경하지 않음
   - "{core_location}"는 그대로 유지
   - 문제 대상의 핵심은 유지하되 표현만 정제

4. **자연스러운 문장 구성**: 읽기 쉽고 논리적인 문장으로 작성
   - 문장을 2-3개로 나누어 명확하게 서술
   - 원인-결과 관계를 자연스럽게 연결

5. **공공기관 어조**: 정중하고 전문적인 표현 사용
   - "~해 주세요" → "~해 주실 것을 제안합니다"
   - "~요함" → "~할 것을 제안합니다"

6. **불필요한 표현 제거**: 감정적 표현, 과장된 표현 제거
   - "매우", "정말", "너무" 등의 강조 표현 최소화

[구체적 변환 예시]
입력: "놀이터 근처 벤치가 삐그덕거리고 노후돼서 보기에 안좋고 위험해 보임, 벤치교체 요함"
출력: "태산패밀리파크 놀이터 근처에 설치된 벤치가 노후화되어 불안정한 상태이며, 미관상 좋지 않고 안전상 위험할 수 있습니다. 따라서 기존 노후 벤치를 새로운 벤치로 교체할 것을 제안합니다."

[출력 형식]
다음 JSON 형식으로만 출력하세요:
{{
    "refined_location": "정제된 장소명",
    "refined_target": "정제된 문제 대상 (구어체 완전 제거)",
    "refined_problem_description": "문제 상황을 자연스럽고 전문적인 문장으로 설명 (2-3문장, 구어체 없음)",
    "refined_solution": "해결책을 자연스럽고 전문적인 문장으로 설명 (1-2문장, 구어체 없음)"
}}

중요: 
- JSON 형식만 출력 (마크다운, 설명 없음)
- 모든 구어체를 완전히 제거
- 자연스럽고 읽기 쉬운 전문 문장으로 작성"""
        
        # Gemini API 호출
        response = ai_model.generate_content(refine_prompt)
        response_text = response.text.strip()
        
        # JSON 파싱 시도
        try:
            # JSON 코드 블록 제거 (있는 경우)
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            # JSON 파싱
            refined_data = json.loads(response_text)
            
            # 필수 필드 검증
            required_fields = ['refined_location', 'refined_target', 'refined_problem_description', 'refined_solution']
            for field in required_fields:
                if field not in refined_data or not refined_data[field]:
                    logger.warning(f"정제된 데이터에 필수 필드 '{field}'가 없거나 비어있습니다. 원본 사용.")
                    return {
                        'refined_location': core_location,
                        'refined_target': core_target,
                        'refined_problem_description': f"{core_location}의 {core_target}에 대한 문제가 있습니다.",
                        'refined_solution': solution_idea if solution_idea else "개선이 필요합니다.",
                        'success': False
                    }
            
            refined_data['success'] = True
            logger.info("사용자 입력 정제 성공")
            return refined_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {e}")
            logger.debug(f"응답 텍스트: {response_text[:200]}")
            # JSON 파싱 실패 시 원본 반환
            return {
                'refined_location': core_location,
                'refined_target': core_target,
                'refined_problem_description': f"{core_location}의 {core_target}에 대한 문제가 있습니다.",
                'refined_solution': solution_idea if solution_idea else "개선이 필요합니다.",
                'success': False
            }
            
    except Exception as e:
        logger.error(f"사용자 입력 정제 오류: {str(e)}")
        # 에러 발생 시 원본 반환
        return {
            'refined_location': core_location,
            'refined_target': core_target,
            'refined_problem_description': f"{core_location}의 {core_target}에 대한 문제가 있습니다.",
            'refined_solution': solution_idea if solution_idea else "개선이 필요합니다.",
            'success': False
        }

def generate_structured_ai_proposal(core_location, core_target, problem_type, affected_people, solution_idea):
    """
    정형화된 질문 세트 기반 AI 제안서 생성
    
    Args:
        core_location (str): 핵심 장소 (예: 태산패밀리파크)
        core_target (str): 핵심 대상 (예: 낡은 벤치)
        problem_type (str): 문제 유형 (안전, 불편, 미관 등)
        affected_people (str): 주요 불편 대상 (어린이, 어르신 등)
        solution_idea (str): 해결책 아이디어
        
    Returns:
        dict: 제안서 내용
    """
    try:
        # 1단계: 사용자 입력 정제 (자연스러운 문장으로 변환)
        logger.info("1단계: 사용자 입력 정제 시작...")
        refined_input = refine_user_input(core_location, core_target, problem_type, affected_people, solution_idea)
        
        # 정제 성공 여부에 따라 사용할 데이터 결정
        if refined_input['success']:
            use_location = refined_input['refined_location']
            use_target = refined_input['refined_target']
            use_problem_desc = refined_input['refined_problem_description']
            use_solution = refined_input['refined_solution']
            logger.info("사용자 입력 정제 완료 - 정제된 내용 사용")
        else:
            # 정제 실패 시 원본 사용
            use_location = core_location
            use_target = core_target
            use_problem_desc = f"{core_location}의 {core_target}에 대한 문제가 있습니다."
            use_solution = solution_idea if solution_idea else "개선이 필요합니다."
            logger.info("사용자 입력 정제 실패 - 원본 내용 사용")
        
        # 장소 유형 파악
        location_context = get_location_context(use_location)
        
        # AI 모델 초기화 (전역 model 사용 또는 새로 생성)
        if model is not None:
            ai_model = model
        else:
            # 전역 model이 없으면 새로 생성 시도
            model_names = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro', 'gemini-1.5-pro']
            ai_model = None
            for model_name in model_names:
                try:
                    ai_model = genai.GenerativeModel(model_name)
                    logger.info(f"제안서 생성을 위한 Gemini 모델 초기화: {model_name}")
                    break
                except Exception as e:
                    logger.warning(f"모델 {model_name} 초기화 실패: {e}")
                    continue
            
            if ai_model is None:
                raise Exception("사용 가능한 Gemini 모델을 찾을 수 없습니다")
        
        # 2단계: 정제된 내용 기반 제안서 생성 프롬프트 구성 (개선된 버전)
        prompt = f"""
당신은 **김포시 정책기획실장**이자 **시민제안서 검토 전문가**입니다.

[최우선 원칙]
- 정제된 사용자 의견의 핵심 정보를 절대 변경하거나 일반화하지 마세요
- 구체적이고 현실적인 내용으로 작성하되, 과장하지 마세요
- 각 섹션을 자연스럽고 읽기 쉬운 전문 문장으로 작성하세요

[정제된 사용자 핵심 의견]
- 핵심 제안 장소: {use_location}
- 핵심 문제 대상: {use_target}
- 문제 상황 설명: {use_problem_desc}
- 요청 해결책: {use_solution}
- 문제 유형: {problem_type if problem_type else '사용자가 명시하지 않음'}
- 주요 불편 대상: {affected_people if affected_people else '사용자가 명시하지 않음'}

[맥락 정보]
- 제안 대상 장소: {use_location}
- 장소 유형 및 특징: {location_context}
- 수신 기관: 김포도시공사

[작성 지시]
위의 [정제된 사용자 핵심 의견]을 바탕으로 김포도시공사에 제출하는 시민제안서 초안을 작성해주세요.

## 1. 제안명
- {use_location}의 {use_target}과 관련된 구체적이고 명확한 제목
- "~ 개선 제안", "~ 교체 제안", "~ 설치 요청", "~ 확충 제안", "~ 보강 제안" 등의 형태
- 15-25자 내외로 간결하고 핵심을 담은 제목
- 예시: "태산패밀리파크 놀이터 주변 휴게시설 교체 제안"

## 2. 현행상의 문제점
**중요**: 일반적인 표현("문제가 지속적으로 제기되고 있습니다")을 절대 사용하지 마세요.

다음 내용을 바탕으로 구체적이고 자연스러운 문장으로 작성:
- 정제된 문제 상황: {use_problem_desc}
{f"- 문제 유형 '{problem_type}' 관점에서 구체적으로 서술" if problem_type else ""}
{f"- 불편 대상 '{affected_people}'의 관점에서 구체적으로 서술" if affected_people else ""}

**작성 예시 (참고용)**:
- 좋은 예: "{use_location} 놀이터 근처에 설치된 벤치가 노후화되어 불안정한 상태이며, 이용객의 안전을 위협할 수 있습니다. 또한 시설의 노후로 인해 미관상 좋지 않아 공원의 전반적인 이미지에도 영향을 미치고 있습니다."
- 나쁜 예: "{use_location}의 벤치 개선에 대한 문제가 지속적으로 제기되고 있습니다."

**요구사항**:
- 2-3문장으로 구체적이고 자연스럽게 작성
- 문제의 원인과 결과를 논리적으로 연결
- 장소와 대상의 구체적 정보를 포함
- 일반적이거나 추상적인 표현 지양

## 3. 개선 안
**중요**: 정제된 해결책의 내용을 그대로 복사하지 말고, 자연스럽게 재구성하세요.

다음 내용을 바탕으로 작성:
- 정제된 해결책: {use_solution}

**작성 형식**:
"김포도시공사에서 [구체적 개선 방안]을 추진해 주실 것을 제안합니다."

**작성 예시 (참고용)**:
- 좋은 예: "김포도시공사에서 {use_location} 놀이터 근처의 노후 벤치를 안전하고 내구성이 우수한 새로운 벤치로 교체해 주실 것을 제안합니다."
- 나쁜 예: "김포도시공사에서 {use_solution}을 추진해 주실 것을 제안합니다." (정제된 내용을 그대로 사용)

**요구사항**:
- 정제된 해결책의 핵심을 유지하되, 자연스럽게 재구성
- 김포도시공사의 업무 범위를 고려한 현실적 방안
- 구체적이고 실행 가능한 내용으로 작성

## 4. 기대 효과
{use_location}의 {use_target} 개선을 통한 구체적인 기대 효과를 다음 관점에서 서술:
1. 직접적 편익: 이용객의 안전과 편의 증진
{f"2. 불편 대상 '{affected_people}'에 대한 구체적 편익" if affected_people else "2. 시설 이용객에 대한 구체적 편익"}
3. 시설 활성화: 개선을 통한 이용률 향상
4. 사회적 가치: 공공시설의 품질 향상

**요구사항**:
- 구체적이고 현실적인 효과 제시
- 과장된 표현 지양
- 2-3문장으로 간결하게 작성

[금지사항 - 절대 준수]
- "{use_location}"와 "{use_target}"을 일반화하거나 생략하는 것 금지
- "문제가 지속적으로 제기되고 있습니다" 같은 일반적 표현 사용 금지
- 정제된 내용을 그대로 복사-붙여넣기하는 것 금지
- 과장되고 추상적인 내용 작성 금지
- 구체적인 수치, 예산, 일정 등을 임의로 작성하는 것 금지
- "~하겠습니다" 형태의 1인칭 표현 사용 금지

위 지침을 철저히 준수하여 전문적이고 자연스러운 제안서를 작성해주세요.
"""
        logger.info("2단계: 제안서 생성 시작...")
        response = ai_model.generate_content(prompt)
        response_text = response.text.strip()
        
        # 응답 파싱 (정제된 내용 사용)
        proposal = parse_structured_proposal(response_text, use_location, use_target, use_solution)
        
        return proposal
        
    except Exception as e:
        logger.error(f"정형화된 AI 제안서 생성 오류: {str(e)}")
        
        # 에러 발생 시 정제 시도 (아직 시도하지 않은 경우)
        try:
            logger.info("에러 발생 - 입력 정제 재시도...")
            refined_input = refine_user_input(core_location, core_target, problem_type, affected_people, solution_idea)
            if refined_input['success']:
                use_location = refined_input['refined_location']
                use_target = refined_input['refined_target']
                use_solution = refined_input['refined_solution']
            else:
                use_location = core_location
                use_target = core_target
                use_solution = solution_idea if solution_idea else "개선이 필요합니다."
        except:
            # 정제도 실패한 경우 원본 사용
            use_location = core_location
            use_target = core_target
            use_solution = solution_idea if solution_idea else "개선이 필요합니다."
        
        # 폴백: 기본 제안서 생성
        title = generate_appropriate_title(use_location, use_target, use_solution)
            
        return {
            'title': title,
            'problem': f"{use_location}의 {use_target}에 대한 문제가 지속적으로 제기되고 있습니다.",
            'solution': f"김포도시공사에서 {use_solution}을 추진해 주실 것을 제안합니다.",
            'effect': f"{use_location}의 {use_target} 개선을 통해 시민 편의 증진과 시설 이용률 향상을 기대할 수 있습니다."
        }

def parse_structured_proposal(response_text, core_location, core_target, solution_idea):
    """정형화된 제안서 응답 파싱"""
    try:
        # 섹션별로 분리
        sections = {
            'title': '',
            'problem': '',
            'solution': '',
            'effect': ''
        }
        
        lines = response_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 섹션 헤더 감지
            if '제안명' in line or '제목' in line:
                current_section = 'title'
                continue
            elif '현행상의 문제점' in line or '문제점' in line:
                current_section = 'problem'
                continue
            elif '개선 안' in line or '개선방안' in line:
                current_section = 'solution'
                continue
            elif '효과' in line or '기대효과' in line:
                current_section = 'effect'
                continue
            
            # 섹션 내용 추가
            if current_section and not line.startswith('##') and not line.startswith('#'):
                if sections[current_section]:
                    sections[current_section] += ' ' + line
                else:
                    sections[current_section] = line
        
        # 기본값 설정 - 제안명 생성 로직 개선
        if not sections['title']:
            sections['title'] = generate_appropriate_title(core_location, core_target, solution_idea)
        if not sections['problem']:
            sections['problem'] = f"{core_location}의 {core_target}에 대한 문제가 지속적으로 제기되고 있습니다."
        if not sections['solution']:
            sections['solution'] = f"김포도시공사에서 {solution_idea}을 추진해 주실 것을 제안합니다."
        if not sections['effect']:
            sections['effect'] = f"{core_location}의 {core_target} 개선을 통해 시민 편의 증진과 시설 이용률 향상을 기대할 수 있습니다."
        
        return sections
        
    except Exception as e:
        logger.error(f"정형화된 제안서 파싱 오류: {str(e)}")
        # 제안명 생성 로직 개선 - 핵심 내용 파악하여 적절한 제안명 생성
        title = generate_appropriate_title(core_location, core_target, solution_idea)
            
        return {
            'title': title,
            'problem': f"{core_location}의 {core_target}에 대한 문제가 지속적으로 제기되고 있습니다.",
            'solution': f"김포도시공사에서 {solution_idea}을 추진해 주실 것을 제안합니다.",
            'effect': f"{core_location}의 {core_target} 개선을 통해 시민 편의 증진과 시설 이용률 향상을 기대할 수 있습니다."
        }

def generate_ai_proposal(problem, solution):
    """AI를 사용한 제안서 생성"""
    try:
        # 1단계: 장소 유형 파악
        location_elements = extract_key_elements(problem, solution)
        location_context = get_location_context(location_elements['location'])
        
        # 2단계: AI 모델 초기화
        # 여러 모델 이름 시도
        model_names = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-pro', 'gemini-1.5-pro']
        model = None
        for model_name in model_names:
            try:
                model = genai.GenerativeModel(model_name)
                logger.info(f"Gemini 모델 초기화 성공: {model_name}")
                break
            except Exception as e:
                logger.warning(f"모델 {model_name} 초기화 실패: {e}")
                continue
        
        if model is None:
            raise Exception("사용 가능한 Gemini 모델을 찾을 수 없습니다")
        
        # 3단계: 마스터 프롬프트 구성
        prompt = f"""
당신은 **김포시 정책기획실장**이자 **시민제안서 검토 전문가**입니다.

[최우선 원칙]
- 사용자가 제공한 핵심 정보를 절대 변경하거나 일반화하지 마세요
- 사용자의 의견을 최대한 보존하고 다듬기만 하세요
- 새로운 내용을 추가하거나 추측하지 마세요

[사용자 핵심 의견 분석]
- 핵심 제안 장소: {location_elements['location']}
- 핵심 문제 대상: {location_elements['problem_target']}
- 핵심 문제: {location_elements['core_problem']}
- 요청 해결책: {location_elements['requested_solution']}

[맥락 정보]
- 제안 대상 장소: {location_elements['location']}
- 장소 유형 및 특징: {location_context}
- 수신 기관: 김포도시공사

[작성 지시]
위의 [핵심 제안 장소]와 [핵심 문제 대상]을 중심으로 김포도시공사에 제출하는 시민제안서 초안을 작성해주세요.

## 1. 제안명
- [핵심 제안 장소]의 [핵심 문제 대상]과 관련된 구체적이고 명확한 제목
- "~ 개선 제안", "~ 설치 요청" 등의 형태로 작성

## 2. 현황 및 문제점
- [핵심 제안 장소]의 [핵심 문제 대상]에 대한 구체적인 문제 상황
- 장소 유형에 맞는 불편함이나 위험성을 논리적으로 추론하여 서술
- 2-3문장으로 간결하게 작성

## 3. 개선 방안
- 사용자가 제안한 해결책: "{location_elements['requested_solution']}"
- 김포도시공사에서 추진해 주실 것을 제안하는 구체적인 방안
- "김포도시공사에서 ~을 추진해 주실 것을 제안합니다" 형태로 작성
- 김포도시공사의 업무 범위와 역할을 고려한 현실적이고 실행 가능한 방안 제시
- 구체적인 수치나 예산은 제시하지 말고 "현장 실사 후 결정", "관련 부서 검토 필요" 등으로 표현

## 4. 기대 효과
- [핵심 제안 장소]의 [핵심 문제 대상] 개선을 통한 구체적인 기대 효과
- 직접적 편익, 시설 활성화 측면, 사회적/공익적 가치로 구분하여 서술

[금지사항 - 절대 준수]
- [핵심 제안 장소]와 [핵심 문제 대상]을 일반화하거나 생략하는 것 금지
- 과장되고 추상적인 내용 작성 금지
- 장소의 특성과 무관한 일반적인 내용 작성 금지
- 김포시와 무관한 일반적인 내용으로 작성하는 것 금지
- 구체적인 수치, 예산, 일정 등을 임의로 작성하는 것 금지
- "~하겠습니다" 형태의 1인칭 표현 사용 금지

위 지침에 따라 제안서를 작성해주세요.
"""
        
        response = model.generate_content(prompt)
        response_text = response.text.strip()
        
        # 응답 파싱
        proposal = parse_ai_response(response_text, location_elements)
        
        return proposal
        
    except Exception as e:
        logger.error(f"AI 제안서 생성 오류: {str(e)}")
        return {
            'title': f"{location_elements['location']} {location_elements['problem_target']} 개선 제안",
            'problem': f"{location_elements['location']}의 {location_elements['problem_target']}에 대한 문제가 지속적으로 제기되고 있습니다.",
            'solution': f"김포도시공사에서 {location_elements['requested_solution']}을 추진해 주실 것을 제안합니다.",
            'effect': f"{location_elements['location']}의 {location_elements['problem_target']} 개선을 통해 시민 편의 증진과 시설 이용률 향상을 기대할 수 있습니다."
        }

def parse_ai_response(response_text, location_elements):
    """AI 응답 파싱"""
    try:
        # 섹션별로 분리
        sections = {
            'title': '',
            'problem': '',
            'solution': '',
            'effect': ''
        }
        
        lines = response_text.split('\n')
        current_section = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 섹션 헤더 감지
            if '제안명' in line or '제목' in line:
                current_section = 'title'
                continue
            elif '현황' in line or '문제점' in line:
                current_section = 'problem'
                continue
            elif '개선' in line and '방안' in line:
                current_section = 'solution'
                continue
            elif '효과' in line or '기대' in line:
                current_section = 'effect'
                continue
            
            # 섹션 내용 추가
            if current_section and not line.startswith('##') and not line.startswith('#'):
                if sections[current_section]:
                    sections[current_section] += ' ' + line
                else:
                    sections[current_section] = line
        
        # 기본값 설정
        if not sections['title']:
            sections['title'] = f"{location_elements['location']} {location_elements['problem_target']} 개선 제안"
        if not sections['problem']:
            sections['problem'] = f"{location_elements['location']}의 {location_elements['problem_target']}에 대한 문제가 지속적으로 제기되고 있습니다."
        if not sections['solution']:
            sections['solution'] = f"김포도시공사에서 {location_elements['requested_solution']}을 추진해 주실 것을 제안합니다."
        if not sections['effect']:
            sections['effect'] = f"{location_elements['location']}의 {location_elements['problem_target']} 개선을 통해 시민 편의 증진과 시설 이용률 향상을 기대할 수 있습니다."
        
        return sections
        
    except Exception as e:
        logger.error(f"AI 응답 파싱 오류: {str(e)}")
        return {
            'title': f"{location_elements['location']} {location_elements['problem_target']} 개선 제안",
            'problem': f"{location_elements['location']}의 {location_elements['problem_target']}에 대한 문제가 지속적으로 제기되고 있습니다.",
            'solution': f"김포도시공사에서 {location_elements['requested_solution']}을 추진해 주실 것을 제안합니다.",
            'effect': f"{location_elements['location']}의 {location_elements['problem_target']} 개선을 통해 시민 편의 증진과 시설 이용률 향상을 기대할 수 있습니다."
        }

def create_pdf_file(title, problem, solution, effect, proposer_name):
    """PDF 파일 생성 - 전문적이고 세련된 시민제안서 양식"""
    try:
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"시민제안서_{proposer_name}_{timestamp}.pdf"
        filepath = os.path.join(os.getcwd(), filename)
        
        # PDF 문서 생성 (A4, 여백 최적화)
        doc = SimpleDocTemplate(filepath, pagesize=A4, 
                              rightMargin=40, leftMargin=40, 
                              topMargin=40, bottomMargin=40)
        story = []
        
        # 스타일 정의
        styles = getSampleStyleSheet()
        
        # 최적화된 스타일 정의
        title_style = ParagraphStyle(
            'Title',
            parent=styles['Heading1'],
            fontName='Korean',
            fontSize=24,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor='#000000',
            leading=28,
            borderWidth=1,
            borderColor='#000000',
            borderPadding=15,
            backColor='#ffffff'
        )
        
        subtitle_style = ParagraphStyle(
            'Subtitle',
            parent=styles['Heading2'],
            fontName='Korean',
            fontSize=14,
            spaceAfter=20,
            spaceBefore=0,
            alignment=TA_CENTER,
            textColor='#333333',
            leading=18,
            borderWidth=0,
            borderColor='#000000',
            borderPadding=0,
            backColor='#ffffff'
        )
        
        info_header_style = ParagraphStyle(
            'InfoHeader',
            parent=styles['Heading3'],
            fontName='Korean',
            fontSize=16,
            spaceAfter=15,
            spaceBefore=20,
            alignment=TA_LEFT,
            textColor='#000000',
            leading=20,
            borderWidth=1,
            borderColor='#000000',
            borderPadding=10,
            backColor='#f5f5f5'
        )
        
        section_header_style = ParagraphStyle(
            'SectionHeader',
            parent=styles['Heading3'],
            fontName='Korean',
            fontSize=16,
            spaceAfter=12,
            spaceBefore=20,
            textColor='#ffffff',
            leading=20,
            borderWidth=0,
            borderColor='#000000',
            borderPadding=12,
            backColor='#2c3e50',
            alignment=TA_LEFT
        )
        
        body_style = ParagraphStyle(
            'Body',
            parent=styles['Normal'],
            fontName='Korean',
            fontSize=12,
            spaceAfter=15,
            alignment=TA_JUSTIFY,
            leading=18,
            leftIndent=0,
            textColor='#000000'
        )
        
        info_style = ParagraphStyle(
            'InfoText',
            parent=styles['Normal'],
            fontName='Korean',
            fontSize=11,
            spaceAfter=8,
            alignment=TA_LEFT,
            textColor='#333333',
            leading=16
        )
        
        signature_style = ParagraphStyle(
            'Signature',
            parent=styles['Normal'],
            fontName='Korean',
            fontSize=12,
            spaceAfter=15,
            alignment=TA_RIGHT,
            textColor='#000000',
            leading=16
        )
        
        consent_style = ParagraphStyle(
            'ConsentText',
            parent=styles['Normal'],
            fontName='Korean',
            fontSize=11,
            spaceAfter=10,
            alignment=TA_JUSTIFY,
            leading=16,
            leftIndent=0,
            textColor='#333333'
        )
        
        # 특별 스타일
        document_header_style = ParagraphStyle(
            'DocumentHeader',
            parent=styles['Heading2'],
            fontName='Korean',
            fontSize=18,
            spaceAfter=20,
            spaceBefore=15,
            alignment=TA_CENTER,
            textColor='#000000',
            leading=22,
            borderWidth=0,
            borderColor='#000000',
            borderPadding=0,
            backColor='#ffffff'
        )
        
        numbered_list_style = ParagraphStyle(
            'NumberedList',
            parent=styles['Normal'],
            fontName='Korean',
            fontSize=12,
            spaceAfter=10,
            alignment=TA_LEFT,
            leading=18,
            leftIndent=15,
            textColor='#000000'
        )
        
        # 1. 제안서 기본 정보 (표지 없이 바로 시작)
        current_date = datetime.now().strftime('%Y년 %m월 %d일')
        story.append(Paragraph("제안서 기본 정보", info_header_style))
        
        # 정보를 표 형태로 구성 (컬럼 폭 조정)
        info_table_data = [
            ['제안일자', current_date, '문서번호', f'PRO-{timestamp[:8]}'],
            ['제안자명', proposer_name, '수신기관', '김포도시공사'],
            ['제안분야', '시설물 개선', '처리기한', '접수 후 30일 이내']
        ]
        
        from reportlab.platypus import Table, TableStyle
        from reportlab.lib import colors
        
        info_table = Table(info_table_data, colWidths=[70, 130, 70, 130])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Korean'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 25))
        
        # 2. 제안명
        story.append(Paragraph("제안명", info_header_style))
        story.append(Spacer(1, 12))
        story.append(Paragraph(title, body_style))
        story.append(Spacer(1, 25))
        
        # 3. 현황 및 문제점
        story.append(Paragraph("1. 현황 및 문제점", section_header_style))
        story.append(Spacer(1, 10))
        story.append(Paragraph(problem, body_style))
        story.append(Spacer(1, 25))
        
        # 4. 개선 방안
        story.append(Paragraph("2. 개선 방안", section_header_style))
        story.append(Spacer(1, 10))
        story.append(Paragraph(solution, body_style))
        story.append(Spacer(1, 25))
        
        # 5. 기대 효과
        story.append(Paragraph("3. 기대 효과", section_header_style))
        story.append(Spacer(1, 10))
        
        # 기대 효과를 체계적으로 정리
        effect_keywords = effect.split('。') if '。' in effect else effect.split('.')
        if len(effect_keywords) > 1:
            for i, keyword in enumerate(effect_keywords, 1):
                keyword = keyword.strip()
                if keyword:
                    story.append(Paragraph(f"{i}. {keyword}", numbered_list_style))
        else:
            story.append(Paragraph(effect, body_style))
        
        story.append(Spacer(1, 30))
        
        # 6. 제안자 서명란
        story.append(Paragraph("제안자 서명", info_header_style))
        story.append(Spacer(1, 15))
        
        # 서명란을 표로 구성 (컬럼 폭 조정)
        signature_data = [
            ['제안자', proposer_name, '서명', '_________________'],
            ['제안일', current_date, '연락처', '_________________'],
            ['주소', '_________________', '이메일', '_________________']
        ]
        
        signature_table = Table(signature_data, colWidths=[50, 140, 50, 140])
        signature_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Korean'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ]))
        
        story.append(signature_table)
        story.append(Spacer(1, 30))
        
        # 7. 새 페이지 - 개인정보 수집 및 이용 동의서 (한 페이지에 맞춤)
        story.append(PageBreak())
        
        # 개인정보 동의서 헤더
        story.append(Paragraph("개인정보 수집 및 이용 동의서", document_header_style))
        story.append(Paragraph("Personal Information Collection and Use Consent Form", subtitle_style))
        story.append(Spacer(1, 20))
        
        # 동의서 본문
        story.append(Paragraph("개인정보 수집 및 이용 안내", section_header_style))
        story.append(Spacer(1, 12))
        
        consent_intro = "김포도시공사는 시민제안서 접수 및 처리 과정에서 다음과 같이 개인정보를 수집·이용합니다."
        story.append(Paragraph(consent_intro, consent_style))
        story.append(Spacer(1, 15))
        
        # 동의서 항목들을 표로 구성 (텍스트 래핑 문제 해결)
        from reportlab.platypus import Paragraph as TableParagraph
        
        # 긴 텍스트를 수동으로 줄바꿈
        consent_data = [
            ['항목', '내용'],
            ['수집·이용 목적', '시민제안서 접수, 검토, 처리 및 결과 통보'],
            ['수집·이용 항목', '성명, 연락처, 제안 내용'],
            ['보유·이용 기간', '제안서 접수일로부터 3년'],
            ['개인정보 제3자 제공', '제공하지 않음'],
            ['개인정보 처리 거부권', '개인정보 수집·이용에 동의하지 않을 수 있으나,<br/>동의하지 않을 경우 제안서 접수가 제한될 수 있습니다.']
        ]
        
        # 각 셀을 Paragraph로 변환하여 텍스트 래핑 처리
        formatted_data = []
        for row in consent_data:
            formatted_row = []
            for cell in row:
                if row == consent_data[0]:  # 헤더 행
                    formatted_row.append(TableParagraph(f'<b>{cell}</b>', 
                        ParagraphStyle('TableHeader', fontName='Helvetica', fontSize=10, 
                        textColor=colors.white, alignment=TA_LEFT)))
                else:
                    formatted_row.append(TableParagraph(cell, 
                        ParagraphStyle('TableCell', fontName='Helvetica', fontSize=10, 
                        textColor=colors.black, alignment=TA_LEFT, leading=12)))
            formatted_data.append(formatted_row)
        
        consent_table = Table(formatted_data, colWidths=[120, 300])
        consent_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.darkblue),
            ('BACKGROUND', (0, 1), (-1, -1), colors.white),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ]))
        
        story.append(consent_table)
        story.append(Spacer(1, 20))
        
        # 동의 확인
        consent_confirm = f"<b>□ 위와 같이 개인정보 수집 및 이용에 동의합니다.</b>"
        story.append(Paragraph(consent_confirm, consent_style))
        story.append(Spacer(1, 20))
        
        # 동의자 서명란 (컬럼 폭 조정)
        story.append(Paragraph("동의자 서명", info_header_style))
        story.append(Spacer(1, 15))
        
        consent_signature_data = [
            ['동의자', proposer_name, '서명', '_________________'],
            ['동의일', current_date, '연락처', '_________________']
        ]
        
        consent_signature_table = Table(consent_signature_data, colWidths=[50, 140, 50, 140])
        consent_signature_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Korean'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 0), (0, -1), colors.lightgrey),
            ('BACKGROUND', (2, 0), (2, -1), colors.lightgrey),
        ]))
        
        story.append(consent_signature_table)
        
        # PDF 생성
        doc.build(story)
        
        logger.info(f"PDF 파일 생성 완료: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"PDF 생성 오류: {str(e)}")
        raise e

# API 엔드포인트들
@app.route('/')
def index():
    return send_file('index.html')

@app.route('/<path:filename>')
def static_files(filename):
    """정적 파일 서빙 (CSS, JS 등)"""
    try:
        return send_file(filename)
    except FileNotFoundError:
        return "File not found", 404

@app.route('/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'facilities_count': len(facility_database)
    })

@app.route('/facilities', methods=['GET'])
def get_facilities():
    """시설물 정보 조회"""
    return jsonify(facility_database)

@app.route('/facilities/refresh', methods=['POST'])
def refresh_facilities():
    """시설물 정보 새로고침"""
    global facility_database
    facility_database = crawl_gimpo_facilities()
    return jsonify({
        'message': '시설물 정보가 새로고침되었습니다.',
        'count': len(facility_database)
    })

@app.route('/generate-proposal', methods=['POST'])
def generate_proposal():
    """AI를 사용한 제안서 생성"""
    try:
        data = request.get_json()
        problem = data.get('problem', '')
        solution = data.get('solution', '')
        
        if not problem or not solution:
            return jsonify({'error': '문제와 해결방안을 모두 입력해주세요.'}), 400
        
        logger.info(f"제안서 생성 요청 - 문제: {problem[:50]}...")
        
        # AI 제안서 생성
        proposal = generate_ai_proposal(problem, solution)
        
        return jsonify({
            'success': True,
            'proposal': proposal
        })
        
    except Exception as e:
        logger.error(f"제안서 생성 오류: {str(e)}")
        return jsonify({'error': '제안서 생성 중 오류가 발생했습니다.'}), 500

@app.route('/generate-structured-proposal', methods=['POST'])
def generate_structured_proposal():
    """정형화된 질문 세트 기반 제안서 생성"""
    try:
        data = request.get_json()
        
        # 필수 필드 검증
        required_fields = ['core_location', 'core_target', 'solution_idea']
        for field in required_fields:
            if field not in data or not data[field].strip():
                return jsonify({'error': f'{field} 필드는 필수입니다.'}), 400
        
        # 선택적 필드들
        problem_type = data.get('problem_type', '')
        affected_people = data.get('affected_people', '')
        
        logger.info(f"정형화된 제안서 생성 요청 - 장소: {data['core_location']}, 대상: {data['core_target']}")
        
        # AI 제안서 생성
        proposal = generate_structured_ai_proposal(
            core_location=data['core_location'],
            core_target=data['core_target'],
            problem_type=problem_type,
            affected_people=affected_people,
            solution_idea=data['solution_idea']
        )
        
        return jsonify({
            'success': True,
            'proposal': proposal
        })
        
    except Exception as e:
        logger.error(f"정형화된 제안서 생성 오류: {str(e)}")
        return jsonify({'error': '제안서 생성 중 오류가 발생했습니다.'}), 500

@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    """PDF 파일 다운로드"""
    try:
        data = request.get_json()
        title = data.get('title', '')
        problem = data.get('problem', '')
        solution = data.get('solution', '')
        effect = data.get('effect', '')
        proposer_name = data.get('proposer_name', '')
        
        if not proposer_name:
            return jsonify({'error': '제안자 성명을 입력해주세요.'}), 400
        
        logger.info(f"PDF 다운로드 요청 받음 - 제안자: {proposer_name}")
        
        # PDF 파일 생성
        filepath = create_pdf_file(title, problem, solution, effect, proposer_name)
        
        # 파일 전송
        return send_file(filepath, as_attachment=True, download_name=os.path.basename(filepath))
        
    except Exception as e:
        logger.error(f"PDF 다운로드 오류: {str(e)}")
        return jsonify({'error': 'PDF 생성 중 오류가 발생했습니다.'}), 500

if __name__ == '__main__':
    # 시설물 정보 초기화
    facility_database = crawl_gimpo_facilities()
    
    # 서버 시작
    if GEMINI_API_KEY != "demo_key_for_testing":
        logger.info("AI시민제안 비서 서버 시작 - 실제 API")
    else:
        logger.info("AI시민제안 비서 서버 시작 - 테스트 모드")
    
    logger.info("서버 주소: http://localhost:5000")
    logger.info("프론트엔드 주소: http://localhost:8000")
    
    app.run(host='0.0.0.0', port=5000, debug=True)

