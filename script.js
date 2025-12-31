// AI시민제안 비서 - 김포도시공사 (정형화된 질문 세트)

// DOM 요소들
const structuredProposalForm = document.getElementById('structuredProposalForm');
const coreLocationInput = document.getElementById('core_location');
const coreTargetInput = document.getElementById('core_target');
const solutionIdeaInput = document.getElementById('solution_idea');
const proposerNameInput = document.getElementById('proposer_name');
const generateBtn = document.querySelector('.generate-btn');
const btnText = document.querySelector('.btn-text');
const btnLoading = document.querySelector('.btn-loading');
const loadingMessage = document.getElementById('loading-message');
const loadingText = loadingMessage ? loadingMessage.querySelector('.loading-text') : null;

// 결과 섹션 요소들
const resultSection = document.getElementById('result-section');
const resultTitle = document.getElementById('result-title');
const resultProblem = document.getElementById('result-problem');
const resultSolution = document.getElementById('result-solution');
const resultEffect = document.getElementById('result-effect');
const downloadPdfBtn = document.getElementById('download-pdf-btn');

// 체크박스 이벤트 처리
document.addEventListener('DOMContentLoaded', function() {
    // 문제 유형 기타 선택 시
    const problemTypeCheckboxes = document.querySelectorAll('input[name="problem_type"]');
    const problemTypeOther = document.getElementById('problem_type_other');
    
    problemTypeCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            if (this.value === '기타' && this.checked) {
                problemTypeOther.style.display = 'block';
                problemTypeOther.required = true;
            } else if (this.value === '기타' && !this.checked) {
                problemTypeOther.style.display = 'none';
                problemTypeOther.required = false;
                problemTypeOther.value = '';
            }
        });
    });
    
    // 불편 대상 기타 선택 시
    const affectedPeopleCheckboxes = document.querySelectorAll('input[name="affected_people"]');
    const affectedPeopleOther = document.getElementById('affected_people_other');
    
    affectedPeopleCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            if (this.value === '기타' && this.checked) {
                affectedPeopleOther.style.display = 'block';
                affectedPeopleOther.required = true;
            } else if (this.value === '기타' && !this.checked) {
                affectedPeopleOther.style.display = 'none';
                affectedPeopleOther.required = false;
                affectedPeopleOther.value = '';
            }
        });
    });
});

// 폼 제출 이벤트
structuredProposalForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const coreLocation = coreLocationInput.value.trim();
    const coreTarget = coreTargetInput.value.trim();
    const solutionIdea = solutionIdeaInput.value.trim();
    
    if (!coreLocation || !coreTarget || !solutionIdea) {
        alert('필수 항목을 모두 입력해주세요.');
        return;
    }
    
    // 선택된 문제 유형 수집
    const problemTypeCheckboxes = document.querySelectorAll('input[name="problem_type"]:checked');
    const problemTypes = Array.from(problemTypeCheckboxes).map(cb => cb.value);
    const problemTypeOther = document.getElementById('problem_type_other').value.trim();
    const problemType = problemTypes.length > 0 ? 
        (problemTypes.includes('기타') && problemTypeOther ? 
            problemTypes.filter(t => t !== '기타').concat(problemTypeOther).join(', ') : 
            problemTypes.join(', ')) : '';
    
    // 선택된 불편 대상 수집
    const affectedPeopleCheckboxes = document.querySelectorAll('input[name="affected_people"]:checked');
    const affectedPeopleTypes = Array.from(affectedPeopleCheckboxes).map(cb => cb.value);
    const affectedPeopleOther = document.getElementById('affected_people_other').value.trim();
    const affectedPeople = affectedPeopleTypes.length > 0 ? 
        (affectedPeopleTypes.includes('기타') && affectedPeopleOther ? 
            affectedPeopleTypes.filter(t => t !== '기타').concat(affectedPeopleOther).join(', ') : 
            affectedPeopleTypes.join(', ')) : '';
    
    try {
        setLoading(true);
        
        const response = await fetch('https://ai-citizen-proposal.onrender.com/generate-structured-proposal', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                core_location: coreLocation,
                core_target: coreTarget,
                problem_type: problemType,
                affected_people: affectedPeople,
                solution_idea: solutionIdea
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            displayStructuredResults(data.proposal);
            saveInputsToLocalStorage({
                core_location: coreLocation,
                core_target: coreTarget,
                problem_type: problemType,
                affected_people: affectedPeople,
                solution_idea: solutionIdea
            });
        } else {
            alert('제안서 생성에 실패했습니다: ' + (data.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('서버와의 통신 중 오류가 발생했습니다.');
    } finally {
        setLoading(false);
    }
});

// 정형화된 결과 표시
function displayStructuredResults(proposal) {
    resultTitle.value = proposal.title || '';
    resultProblem.value = proposal.problem || '';
    resultSolution.value = proposal.solution || '';
    resultEffect.value = proposal.effect || '';
    
    resultSection.style.display = 'block';
    resultSection.scrollIntoView({ behavior: 'smooth' });
}

// 로딩 메시지 배열
const loadingMessages = [
    "좋은 의견 주셔서 감사합니다",
    "인공지능이 소중한 시민 의견을 분석중입니다",
    "잠시만 기다려주세요",
    "시민 의견을 제안서로 다듬는 중입니다",
    "곧 변환이 완료됩니다"
];

// 로딩 메시지 전환 관리
let loadingMessageInterval = null;
let currentMessageIndex = 0;

// 로딩 메시지 시작
function startLoadingMessages() {
    if (!loadingMessage || !loadingText) return;
    
    loadingMessage.style.display = 'block';
    currentMessageIndex = 0;
    loadingText.textContent = loadingMessages[currentMessageIndex];
    
    // 2.5초마다 메시지 전환
    loadingMessageInterval = setInterval(() => {
        currentMessageIndex = (currentMessageIndex + 1) % loadingMessages.length;
        loadingText.textContent = loadingMessages[currentMessageIndex];
    }, 2500);
}

// 로딩 메시지 중지
function stopLoadingMessages() {
    if (loadingMessageInterval) {
        clearInterval(loadingMessageInterval);
        loadingMessageInterval = null;
    }
    if (loadingMessage) {
        loadingMessage.style.display = 'none';
    }
    if (loadingText) {
        loadingText.textContent = '';
    }
}

// 로딩 상태 설정
function setLoading(loading) {
    if (loading) {
        generateBtn.disabled = true;
        btnText.style.display = 'none';
        btnLoading.style.display = 'flex';
        startLoadingMessages();
    } else {
        generateBtn.disabled = false;
        btnText.style.display = 'block';
        btnLoading.style.display = 'none';
        stopLoadingMessages();
    }
}

// PDF 다운로드
async function downloadPdfFile() {
    const proposerName = proposerNameInput.value.trim();
    
    if (!proposerName) {
        alert('제안자 성명을 입력해주세요.');
        return;
    }
    
    const proposalData = {
        title: resultTitle.value,
        problem: resultProblem.value,
        solution: resultSolution.value,
        effect: resultEffect.value,
        proposer_name: proposerName
    };
    
    try {
        const response = await fetch('https://ai-citizen-proposal.onrender.com/download-pdf', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(proposalData)
        });
        
        if (response.ok) {
            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `시민제안서_${proposerName}_${new Date().toISOString().slice(0, 10)}.pdf`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(url);
            document.body.removeChild(a);
        } else {
            const errorData = await response.json();
            alert('PDF 생성에 실패했습니다: ' + (errorData.error || '알 수 없는 오류'));
        }
    } catch (error) {
        console.error('Error:', error);
        alert('PDF 다운로드 중 오류가 발생했습니다.');
    }
}

// 로컬 스토리지에 입력값 저장
function saveInputsToLocalStorage(inputs) {
    localStorage.setItem('proposalInputs', JSON.stringify(inputs));
}

// 로컬 스토리지에서 입력값 불러오기
function loadInputsFromLocalStorage() {
    const saved = localStorage.getItem('proposalInputs');
    if (saved) {
        const inputs = JSON.parse(saved);
        coreLocationInput.value = inputs.core_location || '';
        coreTargetInput.value = inputs.core_target || '';
        solutionIdeaInput.value = inputs.solution_idea || '';
        
        // 문제 유형 복원
        if (inputs.problem_type) {
            const problemTypes = inputs.problem_type.split(', ');
            problemTypes.forEach(type => {
                const checkbox = document.querySelector(`input[name="problem_type"][value="${type}"]`);
                if (checkbox) {
                    checkbox.checked = true;
                } else if (type && !document.querySelector(`input[name="problem_type"][value="${type}"]`)) {
                    // 기타 항목인 경우
                    const otherCheckbox = document.querySelector('input[name="problem_type"][value="기타"]');
                    const otherInput = document.getElementById('problem_type_other');
                    if (otherCheckbox && otherInput) {
                        otherCheckbox.checked = true;
                        otherInput.value = type;
                        otherInput.style.display = 'block';
                    }
                }
            });
        }
        
        // 불편 대상 복원
        if (inputs.affected_people) {
            const affectedPeople = inputs.affected_people.split(', ');
            affectedPeople.forEach(type => {
                const checkbox = document.querySelector(`input[name="affected_people"][value="${type}"]`);
                if (checkbox) {
                    checkbox.checked = true;
                } else if (type && !document.querySelector(`input[name="affected_people"][value="${type}"]`)) {
                    // 기타 항목인 경우
                    const otherCheckbox = document.querySelector('input[name="affected_people"][value="기타"]');
                    const otherInput = document.getElementById('affected_people_other');
                    if (otherCheckbox && otherInput) {
                        otherCheckbox.checked = true;
                        otherInput.value = type;
                        otherInput.style.display = 'block';
                    }
                }
            });
        }
    }
}

// 페이지 로드 시 입력값 리셋 (저장된 값 불러오지 않음)
document.addEventListener('DOMContentLoaded', function() {
    // 입력값을 리셋하기 위해 폼 초기화
    structuredProposalForm.reset();
    
    // 로컬 스토리지에서 이전 데이터 삭제
    localStorage.removeItem('proposalInputs');
});

// PDF 다운로드 버튼 이벤트
if (downloadPdfBtn) {
    downloadPdfBtn.addEventListener('click', downloadPdfFile);
}

// 전역 함수로 내보내기
window.AIProposalCoPilot = {
    downloadPdfFile,
    displayStructuredResults,
    saveInputsToLocalStorage,
    loadInputsFromLocalStorage
};