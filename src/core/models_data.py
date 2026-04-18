# AMEVA Benchmark Model Registry

MODEL_CATALOGUE = [
    # ── Lite ──────────────────────────────────────────────────── 최소 RAM 2GB
    {
        "id":          "qwen2.5-1.5b",
        "display":     "Qwen2.5-1.5B-Instruct",
        "category":    "Lite",
        "tag":         "⚡ 밸런스 · 한국어 명령",
        "desc":        "범용 소형 모델. 한국어 지시문 이해 우수. 노트북CPU에서도 빠름.",
        "min_ram_gb":  2,
        "size_gb":     1.0,
        "filename":    "qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "hf_url":      "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf",
        "ollama_tag":  "qwen2.5:1.5b",
    },
    {
        "id":          "llama-3.2-1b",
        "display":     "Llama-3.2-1B-Instruct",
        "category":    "Lite",
        "tag":         "🪶 초경량 · JSON 포맷팅",
        "desc":        "가장 작은 모델. JSON 출력·구조화 태스크에 최적. RAM 2GB 이하 OK.",
        "min_ram_gb":  2,
        "size_gb":     0.7,
        "filename":    "Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/Llama-3.2-1B-Instruct-GGUF/resolve/main/Llama-3.2-1B-Instruct-Q4_K_M.gguf",
        "ollama_tag":  "llama3.2:1b",
    },
    {
        "id":          "deepseek-r1-1.5b",
        "display":     "DeepSeek-R1-Distill-Qwen-1.5B",
        "category":    "Lite",
        "tag":         "🧠 논리 추론 · 경로 판단",
        "desc":        "추론 특화 증류 모델. 수학·논리·단계적 사고 강점. 1.5B 대비 성능 이상.",
        "min_ram_gb":  2,
        "size_gb":     1.0,
        "filename":    "DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/DeepSeek-R1-Distill-Qwen-1.5B-GGUF/resolve/main/DeepSeek-R1-Distill-Qwen-1.5B-Q4_K_M.gguf",
        "ollama_tag":  "deepseek-r1:1.5b",
    },
    {
        "id":          "gemma-2-2b",
        "display":     "Gemma-2-2B-It",
        "category":    "Lite",
        "tag":         "🏷️ 분류 · 객관식 판단",
        "desc":        "Google DeepMind 2B 모델. 분류·선택형 판단 우수. 효율 대비 품질 높음.",
        "min_ram_gb":  3,
        "size_gb":     1.6,
        "filename":    "gemma-2-2b-it-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q4_K_M.gguf",
        "ollama_tag":  "gemma2:2b",
    },
    # ── Medium ────────────────────────────────────────────────── RAM 4~6GB
    {
        "id":          "qwen2.5-3b",
        "display":     "Qwen2.5-3B-Instruct",
        "category":    "Medium",
        "tag":         "💻 코딩 · 로직 분석",
        "desc":        "코딩·로직 분석 3B 최강. 파이썬/JS 함수 작성, 알고리즘 추론 탁월.",
        "min_ram_gb":  4,
        "size_gb":     2.0,
        "filename":    "qwen2.5-3b-instruct-q4_k_m.gguf",
        "hf_url":      "https://huggingface.co/Qwen/Qwen2.5-3B-Instruct-GGUF/resolve/main/qwen2.5-3b-instruct-q4_k_m.gguf",
        "ollama_tag":  "qwen2.5:3b",
    },
    {
        "id":          "llama-3.2-3b",
        "display":     "Llama-3.2-3B-Instruct",
        "category":    "Medium",
        "tag":         "🔗 논리 추론 · 맥락 유지",
        "desc":        "Meta 3B. 긴 문맥 유지·대화 흐름 일관성 우수. 범용 중형 추천.",
        "min_ram_gb":  4,
        "size_gb":     2.0,
        "filename":    "Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/Llama-3.2-3B-Instruct-GGUF/resolve/main/Llama-3.2-3B-Instruct-Q4_K_M.gguf",
        "ollama_tag":  "llama3.2:3b",
    },
    # ── Heavy ─────────────────────────────────────────────────── RAM 8GB+
    {
        "id":          "exaone-7.8b",
        "display":     "EXAONE-3.0-7.8B-Instruct",
        "category":    "Heavy",
        "tag":         "🇰🇷 한국어 뉘앙스 · 최고 성능",
        "desc":        "LG AI Research 7.8B 한국어 1위 모델. 문맥·뉘앙스·존댓말 완벽 이해.",
        "min_ram_gb":  8,
        "size_gb":     4.8,
        "filename":    "EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/EXAONE-3.0-7.8B-Instruct-GGUF/resolve/main/EXAONE-3.0-7.8B-Instruct-Q4_K_M.gguf",
        "ollama_tag":  "exaone3:7.8b",
    },
    {
        "id":          "kullm3-8b",
        "display":     "KULLM3-8B",
        "category":    "Heavy",
        "tag":         "🌐 Llama3 기반 한국어 패치",
        "desc":        "Korea Univ. Llama3 파인튜닝. 한국어 교육·상식·추론 특화. 8B급 안정성.",
        "min_ram_gb":  8,
        "size_gb":     4.9,
        "filename":    "KULLM3-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/KULLM3-GGUF/resolve/main/KULLM3-Q4_K_M.gguf",
        "ollama_tag":  "kullm3",
    },
    {
        "id":          "eeve-10.8b",
        "display":     "EEVE-Korean-10.8B",
        "category":    "Heavy",
        "tag":         "📚 어휘력 특화 · 대형 모델",
        "desc":        "Yanolja 10.8B 한국어 어휘력 특화. 문학·법률·의학 어휘 이해 최상위.",
        "min_ram_gb":  12,
        "size_gb":     6.6,
        "filename":    "EEVE-Korean-Instruct-10.8B-v1.0-Q4_K_M.gguf",
        "hf_url":      "https://huggingface.co/bartowski/EEVE-Korean-Instruct-10.8B-v1.0-GGUF/resolve/main/EEVE-Korean-Instruct-10.8B-v1.0-Q4_K_M.gguf",
        "ollama_tag":  "eeve-korean:10.8b",
    },
]

CATEGORY_META = {
    "Lite":   {"icon": "⚡", "color": "#10b981", "desc": "RAM 2~3GB  |  즉시 실행 가능  |  CPU 전용 환경 OK"},
    "Medium": {"icon": "⚙️", "color": "#3b82f6", "desc": "RAM 4~6GB  |  일상 노트북 권장  |  4코어 이상"},
    "Heavy":  {"icon": "🔥", "color": "#f59e0b", "desc": "RAM 8GB+   |  고성능 워크스테이션  |  GPU 권장"},
}

def get_filename_by_id(model_id: str) -> str:
    """ID 혹은 ollama_tag를 기반으로 GGUF 파일명을 찾습니다."""
    for m in MODEL_CATALOGUE:
        if m["id"] == model_id or m["ollama_tag"] == model_id:
            return m["filename"]
    return f"{model_id}.gguf" #Fallback
