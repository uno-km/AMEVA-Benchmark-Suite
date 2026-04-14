# AMEVA-Benchmark-Suite

## 1. Overview
AMEVA-Benchmark-Suite는 독립되고 통제된 컨테이너 환경(Matrix) 내에서 로컬 대형 언어 모델(LLM)의 성능과 시스템 리소스 활용도를 평가하고 시각화하는 통합 벤치마크 플랫폼이다. 본 시스템은 클라우드 의존성을 배제하고, 온프레미스(On-Premise) 환경에서의 확정적(Deterministic)인 AI 모델 검증을 목적으로 설계되었다.

### 1.1. System Architecture
본 시스템은 크게 GUI 프론트엔드, 컨테이너 오케스트레이션 엔진, 그리고 평가 및 모니터링 모듈로 구성된다.

* **Frontend (UI Layer):** Python 3.12 기반의 PySide6를 채택하여 OS 네이티브 수준의 렌더링 성능을 확보하였으며, pyqtgraph를 통한 실시간 리소스 텔레메트리 시각화를 수행한다.
* **Backend (Core Layer):** MatrixEngine은 docker-py를 활용하여 대상 모델이 구동될 격리 환경을 동적으로 프로비저닝한다.
* **Evaluation (Benchmark Layer):** BenchmarkRunner 및 SystemMonitor 모듈을 통해 추론 속도, 토큰 생성 효율, CPU/Memory 점유율 등을 정밀하게 측정하며, pydantic을 이용하여 평가 데이터의 정합성을 검증한다.

### 1.2. Specifications
* **Language:** Python 3.12 (Strict compatibility enforced)
* **GUI Framework:** PySide6 (Qt6)
* **Containerization:** Docker Engine (via WSL2 on Windows)
* **Supported Models:** GGUF format Local LLMs (e.g., Qwen-2.5-0.5B, Llama-3.2-1B)
* **Data Processing:** Pandas, Pydantic, OpenAI API Client (Local endpoint configured)

## 2. Research Value
본 프로젝트가 지니는 핵심적인 연구 가치는 '완전한 통제권이 보장된 평가 환경의 구축'에 있다.

기존의 상용 클라우드 API 기반 벤치마크는 네트워크 지연, 서버 로드, 그리고 공급자 측의 잠수함 패치(Silent updates)로 인해 동일한 프롬프트에 대해서도 일관된 성능 및 품질을 보장하기 어렵다. AMEVA-Benchmark-Suite는 이러한 외부 변수를 완전히 차단한다.

평가 대상 모델을 컨테이너 내부로 격리(Isolation)함으로써 시스템 레벨의 간섭을 최소화하고, CPU 명령어 셋(AVX2 등) 최적화에 따른 순수 하드웨어 성능과 모델 가중치 간의 상관관계를 학술적으로 입증할 수 있는 재현 가능한(Reproducible) 테스트 베드를 제공한다.

## 3. Expected Outcomes
본 벤치마크 스위트의 도입을 통해 다음과 같은 기술적, 운영적 이점을 확보할 수 있다.

* **보안 및 프라이버시 확보:** 데이터가 외부로 전송되지 않는 폐쇄망(Air-gapped) 환경에서의 AI 모델 검증이 가능하여, 민감한 산업 데이터나 연구 데이터를 활용한 평가 시 정보 유출의 원천적인 차단이 가능하다.
* **정밀한 리소스 프로파일링:** SystemMonitor를 통한 OS 커널 수준의 리소스 트래킹을 제공함으로써, 특정 모델을 엣지 디바이스나 리소스 제한적 환경에 배포하기 전 정확한 비용(Cost) 및 오버헤드 예측이 가능하다.
* **표준화된 자동화 평가:** 도커 엔진과 연동된 MatrixEngine의 프로비저닝 로직을 통해, 사용자의 개입 없이 복수의 모델을 순차적으로 띄우고 평가한 뒤 결과를 수집하는 완전 자동화된 파이프라인을 구축할 수 있다.

## 4. Architectural Trade-offs and Rationale
AMEVA 시스템을 설계함에 있어 성능, 안정성, 범용성 사이에서 발생한 기술적 타협점과 그 선택의 엔지니어링적 근거는 다음과 같다.

### 4.1. Web 프론트엔드 대신 PySide6 (Qt) 선택
* **Trade-off:** 최근 유행하는 Web 기반 UI(React, Vue)나 Electron을 포기함으로써 접근성과 크로스 플랫폼 유연성을 일부 희생하고, 가파른 학습 곡선과 무거운 종속성을 감수하였다.
* **Rationale:** 실시간 리소스 모니터링 시 발생하는 대량의 데이터 포인트(pyqtgraph 사용)를 지연 없이 렌더링하기 위해서는 브라우저의 DOM 조작보다 OS 네이티브 그래픽 파이프라인과 직접 통신하는 C++ 바인딩 프레임워크(Qt6)가 필수적이었다. 또한, 도커 데몬(Named Pipe) 및 로컬 파일 시스템에 대한 강력하고 직접적인 제어권을 확보하기 위해 순수 Python 기반의 데스크톱 애플리케이션 아키텍처를 채택하였다.

### 4.2. Native 실행 대신 Docker (WSL2) 환경 격리 선택
* **Trade-off:** 모델을 호스트 OS에서 직접 실행(Native Execution)하는 것이 속도 면에서 가장 유리함에도 불구하고, 가상화 계층(Hypervisor/WSL2)을 거치게 하여 일정 수준의 I/O 및 연산 오버헤드(Overhead)를 발생시켰다.
* **Rationale:** 벤치마크의 가장 중요한 덕목은 '재현성'과 '무결성'이다. 호스트 OS 환경은 설치된 다른 소프트웨어나 백그라운드 프로세스에 의해 오염되기 쉬우며, 이는 평가 지표의 신뢰성을 훼손한다. 따라서 약간의 성능 손실을 감수하더라도, 평가 환경을 매번 동일한 상태로 초기화(Clean State)할 수 있는 컨테이너 기술을 도입하는 것이 연구 목적에 부합한다고 판단하였다.

### 4.3. 최신 Python 버전(3.14) 대신 보수적인 버전(3.12) 선택
* **Trade-off:** 최신 버전의 파이썬 엔진이 제공하는 향상된 실행 속도 및 신규 문법의 이점을 포기하였다.
* **Rationale:** C/C++ 기반의 서드파티 라이브러리(PySide6, pydantic_core)는 파이썬의 C-API 변경에 매우 민감하게 반응한다. 초기 구축 과정에서 실험적인 최신 버전(3.14) 적용 시 DLL 로딩 실패(ImportError) 및 프로시저 진입점 오류가 발생함이 확인되었다. 시스템의 핵심 구동 안정성을 보장하기 위해, 글로벌 커뮤니티에서 가장 폭넓게 검증되고 라이브러리 지원이 안정화된 Python 3.12를 표준 런타임으로 강제하는 보수적 스탠스를 취하였다.

## 5. Core Technical Achievements (핵심 기술 성과)
본 프로젝트 구축 과정에서 직면한 심층적인 시스템 레벨의 장애 요인들을 성공적으로 분석 및 해결한 주요 성과는 다음과 같다.

### 5.1. 하드웨어 수준의 가상화 제어 및 컨테이너 연동
호스트 OS(Windows)의 WSL2 백엔드와 메인보드 BIOS의 가상화 기술(VT-x/SVM) 간의 종속성 문제를 분석하였다. 기능이 비활성화된 환경에서도 DISM(Deployment Image Servicing and Management) 명령어 기반의 자동화 파이프라인을 구축하여, 운영체제 커널 계층에서 컨테이너 오케스트레이션 엔진(Docker Daemon)이 요구하는 Named Pipe 통신 채널을 안정적으로 기동시키는 아키텍처를 구현하였다.

### 5.2. 런타임 격리를 통한 동적 링크 라이브러리(DLL) 하이재킹 원천 차단
Windows 환경에서 전역으로 설치된 구버전 파이썬 환경이 가상환경(venv)의 모듈 로딩 우선순위를 간섭하여 발생하는 치명적인 DLL 충돌(ImportError)을 식별하였다. 이를 해결하기 위해 실행 컨텍스트 진입 직전, 스크립트 레벨에서 시스템 환경변수(PATH)를 오버라이딩(Overriding)하여 특정 버전의 PySide6 플랫폼 플러그인이 배타적으로 메모리에 적재되도록 강제하는 '경로 격리화 메커니즘'을 성공적으로 적용하였다.

## 6. Limitations and Future Works (기술적 한계 및 향후 개선 과제)
본 시스템의 성공적인 구현에도 불구하고, 초기 설계 역량의 한계와 인프라 종속성에 기인한 몇 가지 구조적 보완점이 식별되었으며, 이는 향후 연구 및 시스템 고도화의 방향성을 제시한다.

### 6.1. 인프라 종속성 파악 지연 및 초기 구조 설계의 한계점
프로젝트 초기 단계에서 호스트 시스템의 전역 환경변수 스코프(Scope)와 하드웨어 레벨의 가상화 상태가 애플리케이션 런타임에 미치는 심층적인 영향을 사전에 완벽히 인지하지 못했다. 이로 인해 트러블슈팅 과정에서 런타임 예외 처리에 상당한 리소스가 소모되었다. 이는 시스템 아키텍처 설계 시, 운영 환경에 대한 의존성 역전(Dependency Inversion) 관점의 고려가 다소 부족했음을 시사한다. 향후 프로젝트에서는 설계 초기 단계부터 인프라 프로비저닝 요구사항을 명확히 정의하는 인프라 에스 코드(Infrastructure as Code, IaC) 방법론의 도입이 요구된다.

### 6.2. 모듈 간 결합도 및 동기적(Synchronous) 리소스 모니터링의 병목
현재 구조는 PySide6 메인 스레드와 docker-py 데몬 통신이 일부 동기적으로 처리되어, 시스템 리소스 사용량이 극단적으로 높아지는 구간에서 UI 렌더링 프레임 저하를 유발할 수 있는 잠재적 취약성이 존재한다. 향후 비동기 I/O(Asyncio) 모델 또는 별도의 워커 스레드(Worker Thread) 풀 기반의 이벤트 주도(Event-driven) 아키텍처로 리팩토링하여, 백그라운드 텔레메트리 수집과 UI 렌더링 간의 결합도를 완전히 분리(Decoupling)하는 작업이 필수적으로 수반되어야 한다.