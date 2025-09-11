# -*- coding: utf-8 -*-
"""
AI 시민제안 Co-Pilot - Flask 백엔드 서버
김포도시관리공사 프로토타입

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
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY, TA_RIGHT

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
        model = genai.GenerativeModel('gemini-1.5-flash')
        logger.info("Gemini API가 성공적으로 설정되었습니다.")
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
        # Windows 기본 한글 폰트 경로들
        font_paths = [
            'C:/Windows/Fonts/malgun.ttf',  # 맑은 고딕
            'C:/Windows/Fonts/gulim.ttc',   # 굴림
            'C:/Windows/Fonts/batang.ttc',  # 바탕
            'C:/Windows/Fonts/dotum.ttc',   # 돋움
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
        logger.error(f"폰트 등록 오류: {e}")
        return False

# 폰트 등록 실행
register_korean_fonts()


def crawl_gimpo_facilities():
    """
    김포도시관리공사 홈페이지에서 시설물 정보를 크롤링
    
    Returns:
        dict: 시설물 정보 딕셔너리
    """
    try:
        logger.info("김포도시관리공사 홈페이지 크롤링 시작...")
        
        # 김포도시관리공사 홈페이지 URL
        base_url = "https://www.guc.or.kr"
        
        # 시설물 정보를 저장할 딕셔너리
        facilities = {}
        
        # 기본 시설물 정보 추가 (크롤링이 실패할 경우를 대비)
        default_facilities = {
            "태산패밀리파크": {
                "type": "가족공원",
                "description": "물놀이장, 조각공원, 야외공연장 등을 갖춘 김포시의 대표적인 가족 레저 시설",
                "url": "https://www.guc.or.kr"
            },
            "무지개 뜨는 언덕": {
                "type": "공설봉안당",
                "description": "추모와 사색을 위한 경건한 공간으로 유가족들이 편안하게 머물 수 있는 시설",
                "url": "https://www.guc.or.kr"
            },
            "김포시청": {
                "type": "행정시설",
                "description": "김포시의 행정 중심지로 시민 서비스를 제공하는 공공 건물",
                "url": "https://www.guc.or.kr"
            },
            "시민회관": {
                "type": "문화시설",
                "description": "김포시의 문화행사와 시민활동을 위한 공공시설",
                "url": "https://www.guc.or.kr"
            },
            "사우광장": {
                "type": "광장",
                "description": "김포시의 중심가에 위치한 시민들의 휴식과 문화활동 공간",
                "url": "https://www.guc.or.kr"
            }
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
        # 먼저 크롤링된 데이터에서 검색
        for facility_name, info in facility_database.items():
            if location_name in facility_name or facility_name in location_name:
                return f"{info['type']}으로 {info['description']}"
        
        # 크롤링 데이터에 없으면 Gemini로 분석
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        다음 장소에 대한 정보를 간단히 분석해주세요: {location_name}
        
        이 장소가 어떤 성격의 장소인지, 어떤 목적으로 사용되는지, 어떤 특징이 있는지 
        한 문장으로 요약해주세요.
        
        예시:
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
    problem_keywords = ["부족", "낡았", "어두워", "불편", "위험", "어려워", "좁아", "더러워"]
    core_problem = "불편"
    for keyword in problem_keywords:
        if keyword in problem:
            core_problem = keyword
            break
    
    return {
        "location": location,
        "problem_target": problem_target,
        "core_problem": core_problem,
        "requested_solution": solution
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
        # 장소 유형 파악
        location_context = get_location_context(core_location)
        
        # AI 모델 초기화
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # 정형화된 프롬프트 구성
        prompt = f"""
당신은 **김포시 정책기획실장**이자 **시민제안서 검토 전문가**입니다.

[최우선 원칙]
- 사용자가 제공한 핵심 정보를 절대 변경하거나 일반화하지 마세요
- 사용자의 의견을 최대한 보존하고 다듬기만 하세요
- 새로운 내용을 추가하거나 추측하지 마세요

[사용자 핵심 의견]
- 핵심 제안 장소: {core_location}
- 핵심 문제 대상: {core_target}
- 문제 유형: {problem_type if problem_type else '사용자가 명시하지 않음'}
- 주요 불편 대상: {affected_people if affected_people else '사용자가 명시하지 않음'}
- 요청 해결책: {solution_idea}

[맥락 정보]
- 제안 대상 장소: {core_location}
- 장소 유형 및 특징: {location_context}
- 수신 기관: 김포도시관리공사

[작성 지시]
위의 [핵심 제안 장소]와 [핵심 문제 대상]을 중심으로 김포도시관리공사에 제출하는 시민제안서 초안을 작성해주세요.

## 1. 제안명
- [핵심 제안 장소]의 [핵심 문제 대상] 개선을 위한 구체적이고 명확한 제목
- "~ 개선 제안", "~ 설치 요청", "~ 확충 제안", "~ 보강 제안" 등의 형태로 작성
- 15-25자 내외로 간결하고 핵심을 담은 제목 작성
- 사용자의 구어체 표현은 정중한 문체로 변환하여 작성
- 예시: "벤치가 낡았어요" → "벤치 교체", "주차공간이 부족해요" → "주차공간 확충"

## 2. 현행상의 문제점
- [핵심 제안 장소]의 [핵심 문제 대상]에 대한 구체적인 문제 상황
- {f"문제 유형이 '{problem_type}'인 경우, 해당 관점에서 문제점을 서술" if problem_type else ""}
- {f"주요 불편 대상이 '{affected_people}'인 경우, 해당 그룹의 관점에서 문제점을 서술" if affected_people else ""}
- 2-3문장으로 간결하게 작성

## 3. 개선 안
- 사용자가 제안한 해결책: "{solution_idea}"
- 김포도시관리공사에서 추진해 주실 것을 제안하는 구체적인 방안
- "김포도시관리공사에서 ~을 추진해 주실 것을 제안합니다" 형태로 작성
- 김포도시관리공사의 업무 범위와 역할을 고려한 현실적이고 실행 가능한 방안 제시

## 4. 효과
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
        proposal = parse_structured_proposal(response_text, core_location, core_target, solution_idea)
        
        return proposal
        
    except Exception as e:
        logger.error(f"정형화된 AI 제안서 생성 오류: {str(e)}")
        # 제안명 생성 로직 개선 - 핵심 내용 파악하여 적절한 제안명 생성
        title = generate_appropriate_title(core_location, core_target, solution_idea)
            
    return {
            'title': title,
            'problem': f"{core_location}의 {core_target}에 대한 문제가 지속적으로 제기되고 있습니다.",
            'solution': f"김포도시관리공사에서 {solution_idea}을 추진해 주실 것을 제안합니다.",
            'effect': f"{core_location}의 {core_target} 개선을 통해 시민 편의 증진과 시설 이용률 향상을 기대할 수 있습니다."
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
            sections['solution'] = f"김포도시관리공사에서 {solution_idea}을 추진해 주실 것을 제안합니다."
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
            'solution': f"김포도시관리공사에서 {solution_idea}을 추진해 주실 것을 제안합니다.",
            'effect': f"{core_location}의 {core_target} 개선을 통해 시민 편의 증진과 시설 이용률 향상을 기대할 수 있습니다."
        }

def generate_ai_proposal(problem, solution):
    """AI를 사용한 제안서 생성"""
    try:
        # 1단계: 장소 유형 파악
        location_elements = extract_key_elements(problem, solution)
        location_context = get_location_context(location_elements["location"])
        
        # 2단계: Gemini API를 사용한 제안서 생성
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        prompt = f"""
        # [최우선 원칙]
        너의 가장 중요한 임무는 사용자가 입력한 문장에서 **[핵심 제안 장소]**와 **[핵심 문제 대상]**을 정확히 추출하고, 이 두 가지를 제안서 모든 내용의 중심 주제로 삼는 것이다. 절대 이 정보를 일반화하거나 생략해서는 안 된다.
        
        사용자가 작성한 문장과 아이디어를 **최대한 원형 그대로 보존**하는 것이 두 번째 원칙이다. 
        너의 역할은 새로운 내용을 창조하는 것이 아니라, 사용자의 의견을 더 명확하고 논리적으로 보이도록 **'보완'하고 '다듬는'** 것이다. 
        내용을 추가해야 할 경우, 사용자의 원래 의도를 뒷받침하는 최소한의 논리적 연결과 간결한 근거만 덧붙이고, 
        **사용자가 전혀 언급하지 않은 새로운 주장이나 해결책을 임의로 만들어내지 마라.**

        # [역할]
        너는 시민의 아이디어를 논리적이고 설득력 있는 제안서로 발전시키는 AI 시민제안 Co-Pilot이야. 
        너의 임무는 사용자의 단순한 의견을 바탕으로, 주어진 장소의 맥락에 맞는 구체적이고 현실적인 제안서를 작성하는 것이다. 
        과장과 무논리는 절대 금물이다.

        # [맥락 정보]
        - 제안 대상 장소: {location_elements["location"]}
        - 장소 유형 및 특징: {location_context}
        - 수신 기관: 김포도시관리공사

        # [사용자 핵심 의견 분석]
        - 사용자 입력: "{problem} / {solution}"
        - 분석 결과:
          - **[핵심 제안 장소]**: {location_elements["location"]}
          - **[핵심 문제 대상]**: {location_elements["problem_target"]}
          - 핵심 문제: {location_elements["core_problem"]}
          - 요청 해결책: {location_elements["requested_solution"]}

        # [작성 지시]
        위에서 분석한 **[핵심 제안 장소]**와 **[핵심 문제 대상]**을 바탕으로, **[수신 기관]인 '김포도시관리공사'에 제출**하는 것을 전제로 제안서 초안을 작성해줘.

        ## 1. 제안명
        - 반드시 **[핵심 제안 장소]**와 **[핵심 문제 대상]**이 포함된 구체적인 제목을 만들어줘.
        - "김포시 {location_elements["location"]} {location_elements["problem_target"]} 개선을 위한 ○○ 제안" 형식

        ## 2. 현황 및 문제점
        - **[핵심 제안 장소]**의 현재 상황과, **[핵심 문제 대상]**으로 인해 발생하는 문제점을 구체적으로 서술해줘.
        - **사용자가 지적한 문제점**을 중심으로 문장을 다듬고, 그 문제가 왜 중요한지에 대한 **간결하고 직접적인 이유**만 덧붙여라.
        - (예: 사용자가 '주차 공간 부족'만 언급했다면, '불법 주차'나 '교통 혼잡' 정도의 직접적인 결과만 덧붙이고, 그 이상의 추측은 자제)
        - [장소 유형] 맥락에서 사용자 문제의 직접적 영향만 서술하고, 과도한 추론은 피해라.
        - 절대 '도시 발전 저해' 같은 과장된 표현은 사용하지 마.
        - 3-4문장으로 간결하고 직접적으로 작성

        ## 3. 개선 방안
        - **[핵심 제안 장소]**의 **[핵심 문제 대상]**에 대한 구체적인 개선 방안을 제시해줘.
        - **사용자가 제시한 해결책**을 명확하고 정중한 제안 문장으로 바꾸는 데 집중해라.
        - **반드시 [수신 기관]인 '김포도시관리공사'가 실행 주체**가 되도록 문장을 작성해줘.
        - 시민의 관점에서 '**김포도시관리공사에서** ~을 추진해 주실 것을 제안합니다' 와 같은 형식으로 작성해야 해.
        - '**~하겠습니다**' 라는 표현은 절대 사용하지 마.
        - 부가적인 절차 제안은 **사용자의 아이디어를 실행하는 데 반드시 필요한 최소한의 내용**으로 줄이거나, 사용자가 구체적인 아이디어를 냈을 경우엔 생략할 수도 있다.
        - 4-5문장으로 핵심적이고 실행 가능한 방안 제시

        ## 4. 기대 효과
        - **[핵심 제안 장소]**의 **[핵심 문제 대상]** 개선으로 인한 직접적인 효과를 서술해줘.
        - **사용자가 개선을 바랐던 바로 그 점**이 나아지는 것을 핵심 효과로 작성해라.
        - (예: "주차장이 생겼으면 좋겠다" -> "주차 편의성이 향상될 것입니다"가 핵심. '시설 이용률 증대' 등은 간결한 부가 효과로만 언급)
        - [장소 유형]의 목적에 맞는 직접적이고 구체적인 효과를 서술해줘.
        - '도시 경쟁력', '지역 경제 활성화' 같은 과장된 표현은 절대 금지.
        - 3-4문장으로 핵심적이고 현실적인 효과 제시

        [금지사항 - 절대 준수]
        - **[핵심 제안 장소]**를 일반화하거나 생략하는 것 절대 금지 (예: '무지개 뜨는 언덕 지하 2층'을 '김포시 시설'로 확대 해석 금지)
        - **[핵심 문제 대상]**을 일반화하거나 생략하는 것 절대 금지 (예: '벤치와 의자'를 '벤치'로 축소 해석 금지)
        - 사용자가 전혀 언급하지 않은 새로운 주장이나 해결책을 임의로 만들어내는 것 금지
        - 사용자의 핵심 의도를 무시하고 과도하게 내용을 확장하는 것 금지
        - "○○에 대한 개선방안을 제안합니다" 같은 패턴 사용 금지
        - 확인되지 않은 구체적 수치나 데이터 포함 금지
        - 과장되고 추상적인 내용으로 작성하는 것 금지
        - 장소의 특성과 무관한 일반적인 내용으로 작성하는 것 금지

        위 지침을 철저히 준수하여 장소의 맥락에 맞는 전문적인 제안서를 작성해주세요.
        """
        
        response = model.generate_content(prompt)
        content = response.text
        
        # 응답을 파싱하여 구조화된 데이터로 변환
        lines = content.split('\n')
        proposal = {
            "title": "",
            "problem": "",
            "solution": "",
            "effect": ""
        }
        
        current_section = None
        content_buffer = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # 섹션 헤더 감지 (더 정확한 패턴 매칭)
            if any(keyword in line for keyword in ['제안명', '제목', '1. 제안명', '1.제안명']):
                if content_buffer and current_section:
                    proposal[current_section] = ' '.join(content_buffer).strip()
                current_section = 'title'
                content_buffer = []
            elif any(keyword in line for keyword in ['현황', '문제점', '2. 현황', '2. 문제점', '2.현황', '2.문제점']):
                if content_buffer and current_section:
                    proposal[current_section] = ' '.join(content_buffer).strip()
                current_section = 'problem'
                content_buffer = []
            elif any(keyword in line for keyword in ['개선', '방안', '3. 개선', '3. 방안', '3.개선', '3.방안']):
                if content_buffer and current_section:
                    proposal[current_section] = ' '.join(content_buffer).strip()
                current_section = 'solution'
                content_buffer = []
            elif any(keyword in line for keyword in ['기대', '효과', '4. 기대', '4. 효과', '4.기대', '4.효과']):
                if content_buffer and current_section:
                    proposal[current_section] = ' '.join(content_buffer).strip()
                current_section = 'effect'
                content_buffer = []
            elif current_section and line and not line.startswith('[') and not line.startswith('**') and not line.startswith('-'):
                # 섹션 내용 추가 (불필요한 기호 제거)
                content_buffer.append(line)
        
        # 마지막 섹션 처리
        if content_buffer and current_section:
            proposal[current_section] = ' '.join(content_buffer).strip()
        
        # 기본값 설정 및 검증 (장소 맥락에 맞는 내용으로 재구성)
        if not proposal['title'] or len(proposal['title']) < 10:
            # 장소와 문제 대상을 포함한 제목 재구성
            location = location_elements["location"]
            target = location_elements["problem_target"]
            proposal['title'] = f"김포시 {location} {target} 개선을 위한 시설 개선 제안"
        
        if not proposal['problem'] or len(proposal['problem']) < 20:
            # 장소 맥락을 반영한 문제점 재구성
            location = location_elements["location"]
            context = location_context
            core_problem = location_elements["core_problem"]
            
            if "가족 공원" in context or "파크" in location:
                proposal['problem'] = f"김포시 {location}의 {core_problem}한 {location_elements['problem_target']}로 인해 가족 방문객들의 안전과 편의가 저해되고 있습니다. 특히 어린이들의 안전사고 위험과 가족 단위 휴식의 어려움이 지속적으로 제기되어 시급한 개선이 필요한 상황입니다."
            elif "봉안당" in context or "추모" in context:
                proposal['problem'] = f"김포시 {location}의 {core_problem}한 {location_elements['problem_target']}로 인해 유가족들의 추모 환경이 저해되고 있습니다. 경건한 분위기 조성과 편안한 휴식 공간 제공에 어려움이 있어 시급한 개선이 필요한 상황입니다."
            else:
                proposal['problem'] = f"김포시 {location}의 {core_problem}한 {location_elements['problem_target']}로 인해 시민들의 이용에 불편이 발생하고 있습니다. 이는 해당 시설의 이용률 저하와 시민 만족도 감소로 이어져 시급한 개선이 필요한 상황입니다."
        
        if not proposal['solution'] or len(proposal['solution']) < 20:
            # 장소 특성을 고려한 개선방안 재구성
            location = location_elements["location"]
            context = location_context
            target = location_elements["problem_target"]
            
            if "가족 공원" in context or "파크" in location:
                proposal['solution'] = f"김포도시관리공사에서 {location} {target} 개선을 추진해 주실 것을 제안합니다. 현장 실사를 통해 최적의 설치 위치를 결정하고, 아이들의 안전을 고려한 내구성 있는 재질과 밝고 친근한 디자인의 {target}을 설치해 주시기 바랍니다. 시민 의견 수렴을 통한 디자인 선정과 지속적인 관리 체계 구축을 요청드립니다."
            elif "봉안당" in context or "추모" in context:
                proposal['solution'] = f"김포도시관리공사에서 {location} {target} 개선을 추진해 주실 것을 제안합니다. 현장 실사를 통해 최적의 설치 위치를 결정하고, 경건한 분위기에 어울리는 차분한 색상과 편안한 디자인의 {target}을 설치해 주시기 바랍니다. 유가족의 편의를 최우선으로 고려한 시설 개선을 요청드립니다."
            else:
                proposal['solution'] = f"김포도시관리공사에서 {location} {target} 개선을 추진해 주실 것을 제안합니다. 현장 실사를 통해 최적의 설치 위치와 수량을 결정하고, 시민 편의를 고려한 디자인과 내구성을 갖춘 {target}을 설치해 주시기 바랍니다. 시민 참여를 통한 지속가능한 운영 방안 수립을 요청드립니다."
        
        if not proposal['effect'] or len(proposal['effect']) < 20:
            # 장소 목적에 맞는 기대효과 재구성
            location = location_elements["location"]
            context = location_context
            
            if "가족 공원" in context or "파크" in location:
                proposal['effect'] = f"이 제안이 실현될 경우 {location}을 방문하는 가족들의 안전과 편의가 크게 향상될 것으로 예상됩니다. 어린이들의 안전사고 위험 감소와 가족 단위 휴식 공간 확보를 통해 시설 이용률과 시민 만족도가 대폭 증진될 것입니다."
            elif "봉안당" in context or "추모" in context:
                proposal['effect'] = f"이 제안이 실현될 경우 {location}을 이용하는 유가족들의 추모 환경이 크게 개선될 것으로 예상됩니다. 경건하고 편안한 분위기 조성을 통해 유가족의 심리적 안정과 위로에 기여할 것입니다."
            else:
                proposal['effect'] = f"이 제안이 실현될 경우 {location}을 이용하는 시민들의 편의가 크게 향상될 것으로 예상됩니다. 시설 이용률 증대와 시민 만족도 향상을 통해 공공시설의 활용도가 대폭 개선될 것입니다."
        
        return proposal
        
    except Exception as e:
        logger.error(f"AI 제안서 생성 오류: {e}")
        # 오류 시 데모 데이터 반환
        return generate_demo_proposal()

def generate_demo_proposal():
    """데모용 제안서 생성"""
    return {
        "title": "시민회관 주차공간 확충을 위한 사우광장 임시주차장 조성 제안",
        "problem": "현재 시민회관 이용 시 주차공간이 부족하여 시민들의 불편이 지속되고 있습니다. 특히 행사가 있는 날에는 주차 문제로 인해 시민회관 이용을 포기하는 경우가 빈번하게 발생하고 있습니다.",
        "solution": "이러한 문제를 해결하기 위해 시민회관 바로 옆인 사우광장을 임시주차장으로 조성하는 것을 제안합니다. 사우광장은 시민회관과 인접하여 접근성이 우수하며, 기존 공원 기능을 유지하면서도 주차 공간으로 활용할 수 있는 최적의 장소입니다.",
        "effect": "사우광장 임시주차장 조성으로 시민회관 이용객의 주차 편의성이 크게 향상될 것으로 예상됩니다. 이를 통해 시민회관 이용률이 증가하고, 지역 주민들의 문화생활 참여도가 높아질 것입니다. 또한 주변 상권 활성화에도 긍정적인 영향을 미칠 것으로 기대됩니다."
    }

def create_pdf_file(title, problem, solution, effect, proposer_name):
    """
    PDF 파일 생성
    
    Args:
        title (str): 제안서 제목
        problem (str): 현황 및 문제점
        solution (str): 개선 방안
        effect (str): 기대 효과
        proposer_name (str): 제안자 성명
    
    Returns:
        str: 생성된 PDF 파일 경로
    """
    try:
        # 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"시민제안서_{proposer_name}_{timestamp}.pdf"
        filepath = os.path.join(os.getcwd(), filename)
        
        # PDF 문서 생성
        doc = SimpleDocTemplate(filepath, pagesize=A4, 
                              rightMargin=72, leftMargin=72, 
                              topMargin=72, bottomMargin=18)
        
        # 스타일 정의
        styles = getSampleStyleSheet()
        
        # 한글 폰트 설정
        try:
            korean_font = 'Korean'
        except:
            korean_font = 'Helvetica'  # 폴백 폰트
        
        # 제목 스타일
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontName=korean_font,
            fontSize=18,
            spaceAfter=30,
            alignment=TA_CENTER,
            textColor='#1e5f99'
        )
        
        # 섹션 제목 스타일
        section_style = ParagraphStyle(
            'CustomSection',
            parent=styles['Heading2'],
            fontName=korean_font,
            fontSize=14,
            spaceBefore=20,
            spaceAfter=12,
            textColor='#1e5f99',
            borderWidth=1,
            borderColor='#1e5f99',
            borderPadding=8,
            backColor='#f8fbff'
        )
        
        # 본문 스타일
        body_style = ParagraphStyle(
            'CustomBody',
            parent=styles['Normal'],
            fontName=korean_font,
            fontSize=12,
            spaceAfter=15,
            alignment=TA_JUSTIFY,
            leading=18
        )
        
        # 제안자 정보 스타일
        proposer_style = ParagraphStyle(
            'CustomProposer',
            parent=styles['Normal'],
            fontName=korean_font,
            fontSize=11,
            spaceAfter=10,
            alignment=TA_RIGHT,
            textColor='#666666'
        )
        
        # 동의서 스타일
        consent_style = ParagraphStyle(
            'CustomConsent',
            parent=styles['Normal'],
            fontName=korean_font,
            fontSize=10,
            spaceAfter=8,
            alignment=TA_LEFT,
            textColor='#666666',
            leftIndent=20
        )
        
        # 스토리 구성
        story = []
        
        # 제목
        story.append(Paragraph(title, title_style))
        story.append(Spacer(1, 20))
        
        # 제안자 정보
        proposer_info = f"제안자: {proposer_name}<br/>제안일: {datetime.now().strftime('%Y년 %m월 %d일')}"
        story.append(Paragraph(proposer_info, proposer_style))
        story.append(Spacer(1, 30))
        
        # 현황 및 문제점
        story.append(Paragraph("1. 현황 및 문제점", section_style))
        story.append(Paragraph(problem, body_style))
        story.append(Spacer(1, 20))
        
        # 개선 방안
        story.append(Paragraph("2. 개선 방안", section_style))
        story.append(Paragraph(solution, body_style))
        story.append(Spacer(1, 20))
        
        # 기대 효과
        story.append(Paragraph("3. 기대 효과", section_style))
        story.append(Paragraph(effect, body_style))
        story.append(Spacer(1, 30))
        
        # 제안자 서명 (제안서 본문 하단)
        signature_text = f"""
        <b>제안자 서명:</b> {proposer_name} (인)<br/>
        <b>제안일:</b> {datetime.now().strftime('%Y년 %m월 %d일')}
        """
        story.append(Paragraph(signature_text, proposer_style))
        story.append(Spacer(1, 30))
        
        # 구분선 추가
        story.append(Spacer(1, 20))
        story.append(Paragraph("─" * 50, body_style))
        story.append(Spacer(1, 20))
        
        # 개인정보 수집 및 이용 동의서
        story.append(Paragraph("개인정보 수집 및 이용 동의서", section_style))
        
        # 개인정보 수집 및 이용 동의서를 여러 Paragraph로 분리
        story.append(Paragraph("김포도시관리공사는 시민제안서 접수 및 처리 과정에서 다음과 같이 개인정보를 수집·이용합니다.", consent_style))
        story.append(Spacer(1, 10))
        
        # 1번 항목
        story.append(Paragraph("<b>1. 수집·이용 목적:</b>", consent_style))
        story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;시민제안서 접수, 검토, 처리 및 결과 통보", consent_style))
        story.append(Spacer(1, 8))
        
        # 2번 항목
        story.append(Paragraph("<b>2. 수집·이용 항목:</b>", consent_style))
        story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;성명, 연락처, 제안 내용", consent_style))
        story.append(Spacer(1, 8))
        
        # 3번 항목
        story.append(Paragraph("<b>3. 보유·이용 기간:</b>", consent_style))
        story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;제안서 접수일로부터 3년", consent_style))
        story.append(Spacer(1, 8))
        
        # 4번 항목
        story.append(Paragraph("<b>4. 개인정보 처리 거부권:</b>", consent_style))
        story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;개인정보 수집·이용에 동의하지 않을 수 있으나,", consent_style))
        story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;동의하지 않을 경우 제안서 접수가 제한될 수 있습니다.", consent_style))
        story.append(Spacer(1, 8))
        
        # 5번 항목
        story.append(Paragraph("<b>5. 개인정보보호법에 따른 고유식별정보 처리:</b>", consent_style))
        story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;해당 없음", consent_style))
        
        story.append(Spacer(1, 30))
        
        # 개인정보 동의서 서명란
        consent_signature_text = f"""
        <b>개인정보 수집·이용에 동의합니다.</b><br/><br/>
        <b>제안자 서명:</b> {proposer_name} (인)<br/>
        <b>동의일:</b> {datetime.now().strftime('%Y년 %m월 %d일')}
        """
        story.append(Paragraph(consent_signature_text, proposer_style))
        
        # PDF 생성
        doc.build(story)
        
        logger.info(f"PDF 파일 생성 완료: {filepath}")
        return filepath
        
    except Exception as e:
        logger.error(f"PDF 파일 생성 중 오류 발생: {str(e)}")
        raise Exception(f"PDF 생성 실패: {str(e)}")

@app.route('/generate-proposal', methods=['POST'])
def generate_proposal():
    """
    제안서 생성 API 엔드포인트
    """
    try:
        # 요청 데이터 검증
        if not request.is_json:
            return jsonify({'error': 'JSON 형식의 요청이 필요합니다.'}), 400
        
        data = request.get_json()
        required_fields = ['problem', 'solution']
        
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} 필드가 필요합니다.'}), 400
        
        problem = data['problem'].strip()
        solution = data['solution'].strip()
        
        if not problem or not solution:
            return jsonify({'error': '문제점과 해결방안을 모두 입력해주세요.'}), 400
        
        logger.info(f"제안서 생성 요청 받음 - 문제: {problem[:30]}..., 해결책: {solution[:30]}...")
        
        # AI를 사용한 제안서 생성
        if GEMINI_API_KEY and GEMINI_API_KEY != "demo_key_for_testing":
            proposal = generate_ai_proposal(problem, solution)
        else:
            # 데모 모드
            proposal = generate_demo_proposal()
        
        return jsonify({
            'success': True,
            'proposal': proposal
        }), 200
        
    except Exception as e:
        logger.error(f"제안서 생성 API 오류: {str(e)}")
        return jsonify({'error': '제안서 생성 중 오류가 발생했습니다.'}), 500


@app.route('/download-pdf', methods=['POST'])
def download_pdf():
    """
    PDF 다운로드 API 엔드포인트
    """
    try:
        # 요청 데이터 검증
        if not request.is_json:
            return jsonify({'error': 'JSON 형식의 요청이 필요합니다.'}), 400
        
        data = request.get_json()
        required_fields = ['title', 'problem', 'solution', 'effect', 'proposer_name']
        
        for field in required_fields:
            if field not in data:
                return jsonify({'error': f'{field} 필드가 필요합니다.'}), 400
        
        title = data['title'].strip()
        problem = data['problem'].strip()
        solution = data['solution'].strip()
        effect = data['effect'].strip()
        proposer_name = data['proposer_name'].strip()
        
        if not all([title, problem, solution, effect, proposer_name]):
            return jsonify({'error': '모든 필드를 입력해주세요.'}), 400
        
        logger.info(f"PDF 다운로드 요청 받음 - 제안자: {proposer_name}")
        
        # PDF 파일 생성
        filepath = create_pdf_file(title, problem, solution, effect, proposer_name)
        
        # 파일 전송
        return send_file(filepath, as_attachment=True, download_name=f"시민제안서_{proposer_name}.pdf")
        
    except Exception as e:
        logger.error(f"PDF 다운로드 API 오류: {str(e)}")
        return jsonify({'error': 'PDF 생성 중 오류가 발생했습니다.'}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """서버 상태 확인"""
    api_status = "실제 API" if GEMINI_API_KEY != "demo_key_for_testing" else "테스트 모드"
    return jsonify({
        'status': 'healthy',
        'api_mode': api_status,
        'facility_count': len(facility_database),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/facilities', methods=['GET'])
def get_facilities():
    """시설물 정보 조회"""
    return jsonify({
        'facilities': facility_database,
        'count': len(facility_database)
    })

@app.route('/facilities/refresh', methods=['POST'])
def refresh_facilities():
    """시설물 정보 새로고침"""
    global facility_database
    facility_database = crawl_gimpo_facilities()
    return jsonify({
        'message': '시설물 정보가 새로고침되었습니다.',
        'count': len(facility_database)
    })

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

if __name__ == '__main__':
    # 시설물 데이터 로드
    facility_database = crawl_gimpo_facilities()
    
    api_status = "실제 API" if GEMINI_API_KEY != "demo_key_for_testing" else "테스트 모드"
    logger.info(f"AI 시민제안 Co-Pilot 서버 시작 - {api_status}")
    logger.info("서버 주소: http://localhost:5000")
    logger.info("프론트엔드 주소: http://localhost:8000")
    app.run(debug=True, host='0.0.0.0', port=5000)