# S_KSP_clickpro_v4_plotly_patch_FIXED.py
# ===============================================
# KSP Explorer — Leaflet + Plotly (Pro v4 • Plotly patch, FIXED)
# - 지도: ① 국가별 총계(클릭) ② ICT 유형 단일클래스(클릭)
# - 상세: 워드클라우드(항상: 해시태그+요약/내용) + 상위 키워드 가로막대(라벨 잘림 방지)
# - 전역 대시보드: 도넛 2개 + 주제×WB 100% 누적 막대
# - 연도 시각화: 순위 Bump / 100% 누적 막대 (토글)
# - 추가 시각화: 대표 키워드 상대 트렌드(상/하, Plotly) + 대표 '주제(키워드)' 상대 트렌드(상/하, Plotly)
# - 불필요한 슬라이더/옵션 제거: 워드클라우드 소스 고정, Top-K 조절/Jeffreys+롤링 윈도 조절 제거
# - FIX: with/else 들여쓰기 정리, 블록 사이에 코드 삽입으로 인한 SyntaxError 해결
# ===============================================
import os, io, re, json, urllib.request, hashlib, pathlib, copy, colorsys
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "True")
from typing import List, Dict, Tuple, Optional
from collections import Counter, defaultdict, OrderedDict
import urllib.request
from pathlib import Path
import traceback, platform, numpy as np
import pandas as pd
from PIL import Image
import itertools
from PIL import ImageFont
import streamlit as st
import folium
from streamlit_folium import st_folium
from wordcloud import WordCloud
import plotly.express as px
import plotly.graph_objects as go
from matplotlib import font_manager, rcParams
import math
from sklearn.feature_extraction.text import TfidfVectorizer
from functools import lru_cache     


# --------------------- 페이지/테마 ---------------------
st.set_page_config(page_title="KSP Explorer (Pro v4)", layout="wide", page_icon="🌍")

@st.cache_resource
def resolve_korean_font() -> str | None:
    # 1) 리포에 동봉된 폰트 우선
    candidates = [
        Path(__file__).parent / "assets/fonts/NanumGothic.ttf",
        Path(__file__).parent / "assets/fonts/NotoSansKR-Regular.otf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        r"C:\Windows\Fonts\malgun.ttf",
        "/System/Library/Fonts/AppleGothic.ttf",
    ]
    for p in candidates:
        p = str(p)
        if os.path.exists(p):
            try:
                ImageFont.truetype(p, 20)
                return p
            except Exception:
                pass

    # 2) 최후: 시스템 폰트 디렉토리 전체 스캔(캐시됨)
    roots = ["/usr/share/fonts", "/Library/Fonts", "/System/Library/Fonts", r"C:\Windows\Fonts"]
    keys  = ["nanum","noto","apple","malgun","gulim","batang","sourcehan","cjk"]
    for root in roots:
        if not os.path.isdir(root):
            continue
        for dirpath, _, filenames in os.walk(root):
            for fn in filenames:
                if fn.lower().endswith((".ttf",".otf",".ttc")) and any(k in fn.lower() for k in keys):
                    cand = os.path.join(dirpath, fn)
                    try:
                        ImageFont.truetype(cand, 20)
                        return cand
                    except Exception:
                        continue
    return None


WC_FONT_PATH = resolve_korean_font()
#GLOBAL_FONT_FAMILY = "Noto Sans KR, NanumGothic, Malgun Gothic, AppleGothic, Arial Unicode MS, sans-serif"

st.sidebar.header("환경 설정")
theme_name = st.sidebar.selectbox(
    "테마", ["Nord", "Emerald", "Sandstone", "Slate"], index=0
)

THEME_PRESETS = {
    "Obsidian":  {"bg":"#0f1115","text":"#e6e8eb","panel":"#151923","card":"#0f141c","border":"#202634","accent":"#4f9cf0","plotly_template":"plotly_dark"},
    "Midnight":  {"bg":"#0b1220","text":"#e8eefc","panel":"#101a2c","card":"#0d1526","border":"#1c2a45","accent":"#8ac6ff","plotly_template":"plotly_dark"},
    "Nord":      {"bg":"#ECEFF4","text":"#2E3440","panel":"#E5E9F0","card":"#FFFFFF","border":"#D8DEE9","accent":"#5E81AC","plotly_template":"plotly_white"},
    "Emerald":   {"bg":"#f3fbf7","text":"#123026","panel":"#e8f6ee","card":"#ffffff","border":"#cfe9dc","accent":"#2bb673","plotly_template":"plotly_white"},
    "Sandstone": {"bg":"#faf7f2","text":"#2c251b","panel":"#f1ece3","card":"#ffffff","border":"#e3d9c6","accent":"#d49a6a","plotly_template":"plotly_white"},
    "Slate":     {"bg":"#f6f7fb","text":"#111827","panel":"#eef1f6","card":"#ffffff","border":"#e5e7eb","accent":"#3b82f6","plotly_template":"plotly_white"},
}
ui = THEME_PRESETS[theme_name]



st.markdown(f"""
<style>
:root {{
  --bg:{ui['bg']}; --text:{ui['text']};
  --panel:{ui['panel']}; --card:{ui['card']}; --border:{ui['border']}; --accent:{ui['accent']};
}}
html, body, .block-container {{ background:var(--bg) !important; color:var(--text) !important; }}
section[data-testid="stSidebar"] {{ background:var(--panel) !important; }}
div[data-testid="stHeader"] {{ background:var(--bg) !important; }}
.stMarkdown, p, h1,h2,h3,h4,h5,h6 {{ color:var(--text) !important; }}
.ksp-card {{ background:var(--card); border:1px solid var(--border); border-radius:14px; padding:14px; }}
.ksp-chip {{ display:inline-block; background:var(--panel); border:1px solid var(--border);
            border-radius:14px; padding:4px 10px; margin:4px; }}
a {{ color: var(--accent); }}
</style>
""", unsafe_allow_html=True)

# ---- Force Korean-capable fonts in the browser (Plotly/HTML) ----
#st.markdown(f"""
#<style>
#* {{ font-family: {GLOBAL_FONT_FAMILY} !important; }}
#</style>
#""", unsafe_allow_html=True)

# ---- Plotly font stack (safe getter) ----
FONT_STACK_DEFAULT = "Noto Sans KR, NanumGothic, Malgun Gothic, AppleGothic, Arial Unicode MS, Arial, sans-serif"

def _plotly_font_family():
    # 세션/글로벌/디폴트 순으로 가져옴
    return (
        st.session_state.get("plotly_font_family")
        or globals().get("GLOBAL_FONT_FAMILY")
        or FONT_STACK_DEFAULT
    )



st.title("KSP Explorer 🌍 — Pro v4")



# --------------------- 불용어 ---------------------
STOP = {
    "및","등","관련","수립","방안","개선","전략","지원","정책","사업","프로젝트","제도", "한국과", "멕시코의", "향상을", "프로젝트는", "현대화를", "헬프데스크와", "기능", "상승", "탑재", "과제", "100위에서", "모니터링을", "공유", "지적", "높은", "28중", "미흡", "9대항목",
    "구축","도입","개요","현황","위한","활용","분석","제공","개발","기반","디지털","data", "근거", "경험", "67소", "9대", "3그룹", "제도적", "변화", "기관", "조사", "부문", "확대", "기업", "혁신을", "활용한", "등이다", "효과는", "경험을", "방안을",
    "데이터","system","정부","ksp","koica","kdi","idb","ebrd","wb","adb","국가","한국", "제도와", "시스템을", "검색", "전문가", "업체", "사업은", "제도개선을", "로드맵과", "설문을", "디지털정부의", "체계를", "순위", "순위가", "80위로", "필요성", "표준", "기관의", "28중항목",
    "연구","보고","최종","중간","성과","향상","제고","도움","차세대","로드맵","운영","서비스", "바탕으로", "말레이시아의", "진단하고", "정부와", "KSP는", "지원했다", "한국의", "시스템", "회의", "논의", "참여", "시스템과", "KSP에서", "참고하여", "구축을", "방문", "풀텍스트",
    "라오스","2030","ntca","to be","헝가리","be","사례","모델","산업", "비교", "강조", "최종보고", "위해", "연수", "비전", "개최", "협의", "제2", "구축", "권고", "문제", "온나라", "중앙", "도입과", "하부", "성장", "등을", '품질', "연구개발과", "거버넌스를", "설립",
    "격차","해소","역량","강화","실행계획","연금","vision","실용신안", "평가", "제시", "통해", "설치", "제시했다", "권고하며", "분석하고", "시스템의", "개선안을", "했다", "통해", "목표로", "향상과", "제안", "관리", "통합", "협력", "제안하였다", "체계", "비교하여", "설명가능",
    "가지", "장기", "투명성과", "기대했다", "진행되었으며", "전환과", "마련했다", "모델로", "협의와", "비교와", "개발을", "이후", "마련", "부족을", "수립을", "사례를", "정부와", "프레임워크", "통한", "기반으로", "카하", "발전", "제안했다", "제시하고", "정책을", "화상회의를",
    "적용", "포털", "수립하였다", "것이다", "도입을", "정부의", "성숙도", "과정", "계획을", "희수", "따른", "계획과", "TV", "새로운", "중소기업의", "자료", "추정", "안정", "선정", "경쟁력", "전략을", "현황을", "개선을", "활성화를", "To", "검토", "실행계획과", "단계별",
    "강화와", "현행", "생태계를", "현황과", "가치평가", "전환에", "활동", "국민", "포함", "기본계획", "접근성", "전환", "할당", "양국", "효과", "추진", "협력과", "이용계획", "담은", "로드맵을", "제시하였다", "WASH", "기술", "기대효과", "가나의", "솔루션을", "수행하였다", "분야",
    "67소항목으로", "분야", "진단", "중복조사와", "사용", "항목", "포용적", "규제", "기업들의", "혁신", "라오스의", "메콩강", "베트남의", "통계", "처리", "제도의", "제안합니다", "유역의", "이를", "강화를", "있습니다", "폐기물", "필리핀의", "tuneps", "표준화", "재정감사감독청", "이집트의",
    "개혁을", "체계적으로", "dur", "파라과이의", "과테말라의", "제안한다", "보고서는", "강화하고", "국가들의", "회원국", "도출했습니다", "분석하여", "팀은", "제안한다", "것을", "제시한다", "국가들의", "우즈베키스탄의", "검토하였습니다", "낮은", "그룹", "경쟁력을", "강조한다", "중요성을",
    "핵심", "수동", "지연", "그리고", "또한", "보고서입니다", "겪고", "인해", "현재", "다니는", "다룬다", "중심으로", "가능한", "한다", "위치", "부문의", "가장", "온두라스의", "운영을", "센터", "특히", "참여를", "등록", "초점을", "지원을", "제시했습니다", "행정의",
    "접근성을", "발생하는", "수립합니다", "제시합니다", "성공적인", "효율적인", "전환을", "대응", "자문을", "합니다", "기술을", "서비스에", "등의", "주요", "분절된", "시스템은", "기능이", "세르비아의", "방글라데시의", "강화하기", "체계적인", "문제를", "지원합니다", "높이는", "기본", "단지의", "산업의",
    "미흡한", "시스템이", "비롯한", "다각화와", "타지키스탄은", "타지키스탄의", "정보", "이에", "따라", "실정입니다", "데이터의", "데이터를", "공유하고", "것입니다", "궁극적으로", "기여할", "정확성을", "자동화하여", "수립의", "공유를", "융합하여", "부문을", "지속", "달성하도록", "성장을", "돕는", "산업과",
    "경제에서", "경제로", "전환하고자", "그러나" ,"부문은", "부족으로", "잠재력을", "충분히", "활용하지", "못하고", "호주는", "호주의", "분야에서", "인도네시아는", "문제점을", "효율성을", "것으로", "지역의", "벤치마킹하여", "기대됩니다"
}
STOP_LOW = {w.lower() for w in STOP}

# ---- Trend config (safe defaults; can be overridden later) ----
# 코드 어디서든 참조해도 NameError가 안 나도록 안전 기본값을 먼저 깔아둔다.
YEAR_SOURCE = globals().get("YEAR_SOURCE", None)   # 예: "연도"로 바꾸면 해당 컬럼만 사용
STOP_CUSTOM = globals().get("STOP_CUSTOM", set())  # 코드에서 직접 추가할 불용어
BASE_STOP   = globals().get("BASE_STOP", set())

STOP_LOW_ALL = (
    {w.lower() for w in STOP} |
    {w.lower() for w in STOP_CUSTOM} |
    {w.lower() for w in BASE_STOP}
)

# --------------------- 데이터 입력 ---------------------
st.sidebar.header("데이터 입력")

# 기본값(있어도 되고 없어도 됨 — 자동 탐지 시 무시됨)
DEFAULT_DATA_PATH = r"df1_20250901_145328.xlsx"

# 스크립트 기준 디렉토리(노트북/REPL 대비 fallback)
DATA_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
SEARCH_DIRS = [DATA_DIR, DATA_DIR / "data", DATA_DIR / "assets"]

# --- Safe column selector (교집합 + 동의어 + 폴백) ---
ALT_NAMES = {
    "사업 기간": ["사업기간", "기간", "Project Period", "Years", "Year", "year"],
    "요약": ["요약문", "내용 요약"],
    "주요 내용": ["본문", "내용"],
    "Hashtag_str": ["Hashtag", "해시태그", "해시태그_문자열"],
    "대상기관": ["기관", "기관명"],
    "지원기관": ["지원 기관"],
    "ICT 유형": ["ICT유형"],
    "주제분류(대)": ["주제(대)", "주제 대분류"],
    "파일명": ["Filename", "파일 이름"],
    "대상국": ["Country"],
}

def pick_existing_columns(df: pd.DataFrame, preferred: list[str], fallback_max: int = 8) -> list[str]:
    """preferred 우선 → ALT_NAMES로 대체 → 그래도 부족하면 앞 n개 임의 폴백"""
    existing = [c for c in preferred if c in df.columns]
    wanted = set(preferred)

    # 필요한데 빠진 것들에 대해 동의어 시도
    for col in preferred:
        if col in existing:
            continue
        for alt in ALT_NAMES.get(col, []):
            if alt in df.columns and alt not in existing and alt not in wanted:
                existing.append(alt)
                break

    # 그래도 하나도 없으면 앞에서 몇 개 폴백
    if not existing:
        existing = list(df.columns[:fallback_max])

    return existing


def ensure_unique_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = pd.Series(df.columns)
    if cols.duplicated().any():
        # 동일 이름 열이 여러 개면 첫 번째만 남기고 나머지는 버림
        df = df.loc[:, ~cols.duplicated()].copy()
    return df

# === NEW: 컬럼 정규화(유사명 → 표준명) ===
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    - 공백/개행 제거, 대소문자 틀어짐 보정
    - 자주 쓰이는 변형명을 표준 컬럼으로 통일
    """
    if df is None or df.empty:
        return df

    # 1) 트리밍
    new_cols = []
    for c in df.columns:
        c2 = str(c).replace("\n", " ").strip()
        c2 = re.sub(r"\s+", " ", c2)
        new_cols.append(c2)
    df = df.copy()
    df.columns = new_cols

    # 2) 유사명 매핑
    #   표준: "사업 기간", "연도", "요약", "주요 내용", "Hashtag", "Hashtag_str", "ICT 유형", "주제분류(대)", "대상국", "대상기관", "지원기관", "파일명"
    rename_map = {
        "사업기간": "사업 기간",
        "프로젝트 기간": "사업 기간",
        "기간": "사업 기간",
        "Project Period": "사업 기간",
        "Years": "연도",
        "Year": "연도",
        "year": "연도",
        "Hashtags": "Hashtag",
        "해시태그": "Hashtag",
        "해시태그_문자열": "Hashtag_str",
        "ICT유형": "ICT 유형",
        "주제(대)": "주제분류(대)",
        "주제 대분류": "주제분류(대)",
        "Country": "대상국",
        "기관": "대상기관",
        "기관명": "대상기관",
        "지원 기관": "지원기관",
        "Filename": "파일명",
        "파일 이름": "파일명",
        "요약문": "요약",
        "내용 요약": "요약",
        "본문": "주요 내용",
    }
    for k, v in list(rename_map.items()):
        if k in df.columns and v not in df.columns:
            df = df.rename(columns={k: v})

    # 3) 최소 필요한 핵심 컬럼이 없을 때도 후속 로직이 죽지 않도록 보정
    for must in ["파일명", "대상국", "ICT 유형", "주제분류(대)"]:
        if must not in df.columns:
            # 없는 경우라도 차트 전체가 죽지 않게 placeholder 생성
            df[must] = df.get(must, pd.Series(["-"] * len(df)))

    return df


@st.cache_data(show_spinner=False)
def load_from_path(path: str) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()
    if ext in [".xlsx", ".xls"]: return pd.read_excel(path)
    if ext == ".csv": return pd.read_csv(path, encoding_errors="ignore")
    return pd.read_excel(path)

def load_from_uploader(f) -> pd.DataFrame:
    name = f.name.lower()
    if name.endswith((".xlsx", ".xls")): return pd.read_excel(f)
    if name.endswith(".csv"): return pd.read_csv(f, encoding_errors="ignore")
    return pd.read_excel(f)

def load_from_csv_text(txt: str) -> pd.DataFrame:
    return pd.read_csv(io.StringIO(txt), encoding_errors="ignore")

@st.cache_data(show_spinner=False)
def discover_data_files(dirs: list[Path]) -> list[Path]:
    """같은 폴더(+ 관용 서브폴더)에서 엑셀/CSV 후보 탐색 & 스코어링"""
    cands: list[Path] = []
    for base in dirs:
        if not base.exists(): continue
        for pat in ("*.xlsx", "*.xls", "*.csv"):
            cands.extend(sorted(base.glob(pat)))
    # 스코어: 파일명 힌트(가중) + 최신 수정시간
    def score(p: Path) -> tuple:
        name = p.name.lower()
        s = 0
        # 프로젝트에서 자주 쓰는 패턴 가중치
        if "df1" in name: s += 8
        if "ksp" in name: s += 6
        if "state_of_the_table" in name: s += 5
        if "export" in name or "table" in name: s += 2
        if name.startswith("~$") or name.endswith(".tmp"): s -= 100
        # 최신 파일 우선
        return (-s, -p.stat().st_mtime)
    # 가장 높은 점수(음수 정렬 보정 위해 -s)부터 오름차순 → 우리가 원하는 건 점수 큰 순이므로 다시 정렬 기준 주의
    # 위 score에서 -s, -mtime을 줬으니 "오름차순"으로 정렬하면 실질적으로 점수↓ → 원하는 건 반대.
    # 간단히 별도 key로 다시 정렬:
    def _rank_value(path: Path) -> int:
        name = path.name.lower()
        score = 0
        score += 8 if "df1" in name else 0
        score += 6 if "ksp" in name else 0
        score += 5 if "state_of_the_table" in name else 0
        score += 2 if ("export" in name or "table" in name) else 0
        return score
    
    cands = sorted(
        cands,
        key=lambda p: (-_rank_value(p), -p.stat().st_mtime)  # 점수↓, 최근파일↑
    )

    # 중복 제거(동일 경로 대비 안전)
    seen = set(); out = []
    for p in cands:
        if p.resolve() not in seen:
            out.append(p); seen.add(p.resolve())
    return out

# ── UI: 소스 선택(자동이 기본) ──────────────────────────────────────────
src_mode = st.sidebar.radio(
    "소스 선택",
    ["자동(같은 폴더)", "파일 업로드", "CSV 붙여넣기", "파일 경로"],
    index=0
)

# 캐시 리로드
if st.sidebar.button("로드/새로고침", use_container_width=True):
    st.cache_data.clear()

df = None
auto_files = discover_data_files(SEARCH_DIRS)

if src_mode == "자동(같은 폴더)":
    if auto_files:
        # 후보가 여러 개면 선택 박스 제공(기본: 최우선 후보)
        labels = [f"{p.name}  —  {p.parent.name}/  (수정: {pd.to_datetime(p.stat().st_mtime, unit='s'):%Y-%m-%d %H:%M})"
                  for p in auto_files]
        sel_idx = 0
        if len(auto_files) > 1:
            sel_idx = st.sidebar.selectbox("자동 탐지된 파일", list(range(len(auto_files))),
                                           index=0, format_func=lambda i: labels[i])
        st.sidebar.caption(f"경로: `{auto_files[sel_idx]}`")
        df = load_from_path(str(auto_files[sel_idx]))
        df = normalize_columns(df)
        df = ensure_unique_columns(df)

    else:
        st.sidebar.info("같은 폴더(또는 ./data, ./assets)에서 적합한 데이터 파일을 찾지 못했습니다. 다른 소스 방식을 사용하세요.")

elif src_mode == "파일 업로드":
    up = st.sidebar.file_uploader("엑셀(.xlsx/.xls) 또는 CSV 업로드", type=["xlsx", "xls", "csv"])
    if up is not None:
        df = load_from_uploader(up)
        df = normalize_columns(df)
        df = ensure_unique_columns(df)


elif src_mode == "CSV 붙여넣기":
    pasted = st.sidebar.text_area("CSV 원문 붙여넣기(헤더 포함)", height=160)
    if pasted.strip():
        df = load_from_csv_text(pasted)
        df = normalize_columns(df)
        df = ensure_unique_columns(df)


else:  # 파일 경로
    # 자동 후보가 있으면 기본값을 그 중 첫 번째로 노출(없으면 DEFAULT 사용)
    default_path = str(auto_files[0]) if auto_files else DEFAULT_DATA_PATH
    data_path = st.sidebar.text_input("엑셀/CSV 경로", default_path)
    if os.path.exists(data_path):
        df = load_from_path(data_path)
        df = normalize_columns(df)
        df = ensure_unique_columns(df)

        st.sidebar.caption(f"경로: `{Path(data_path).resolve()}`")

# 데이터 없으면 중단
if df is None or df.empty:
    st.stop()

# 필수 컬럼 진단
REQ = ["파일명","대상국","대상기관","주요 분야","지원기관","주요 내용","기대 효과",
       "요약","ICT 유형","주제분류(대)","Hashtag","Hashtag_str","full_text"]
missing = [c for c in REQ if c not in df.columns]
if missing:
    st.warning(f"필수 컬럼 누락: {missing}")

with st.expander("데이터 미리보기 / 진단", expanded=False):
    st.write(f"행 수: {len(df):,}  |  고유 대상국: {df['대상국'].nunique()}  |  고유 ICT 유형: {df['ICT 유형'].nunique()}")
    st.dataframe(df.head(25), use_container_width=True)
# --------------------- 데이터 입력 (끝) ---------------------
# ========================= 전역 컬러 팔레트 =========================


# ---------- 1) df 로드 이후 ----------
# 반드시 df가 이미 로드된 뒤 실행!
WB_ORDER   = [str(v).strip() for v in df["ICT 유형"].fillna("미분류").astype(str).unique().tolist()]
SUBJ_ORDER = [str(v).strip() for v in df["주제분류(대)"].fillna("미분류").astype(str).unique().tolist()]

# ---------- 2) 기본 팔레트 ----------
_BASE_QUALS = (
    px.colors.qualitative.Set1
    + px.colors.qualitative.Set2
    + px.colors.qualitative.Set3
    + px.colors.qualitative.Dark24
    + px.colors.qualitative.Bold
    + px.colors.qualitative.Vivid
)

# ---------- 3) 색 파싱/보정 ----------
def _parse_color_to_rgb01(c: str) -> Optional[Tuple[float, float, float]]:
    if not isinstance(c, str):
        return None
    s = c.strip()
    if s.startswith("#"):
        h = s[1:]
        if len(h) == 3: h = "".join(ch*2 for ch in h)
        if len(h) == 6:
            try:
                r = int(h[0:2], 16)/255; g = int(h[2:4], 16)/255; b = int(h[4:6], 16)/255
                return (r,g,b)
            except Exception: return None
    if s.lower().startswith("rgb"):
        nums = re.findall(r"[\d\.]+", s)
        if len(nums)>=3:
            r,g,b = [float(x) for x in nums[:3]]
            if max(r,g,b)>1: r,g,b = r/255,g/255,b/255
            return (r,g,b)
    try:
        from matplotlib.colors import to_rgb
        return to_rgb(s)
    except Exception:
        return None

def _to_hex_from_rgb01(rgb):
    r,g,b=[int(max(0,min(1,v))*255+0.5) for v in rgb]
    return f"#{r:02x}{g:02x}{b:02x}"

def _brighten_color(c: str, s_scale=1.3, l_shift=-0.05) -> str:
    rgb = _parse_color_to_rgb01(c)
    if rgb is None: return c
    h,l,s = colorsys.rgb_to_hls(*rgb)
    s = min(1, s*s_scale); l = min(1, max(0, l+l_shift))
    r2,g2,b2 = colorsys.hls_to_rgb(h,l,s)
    return _to_hex_from_rgb01((r2,g2,b2))

# ---------- 4) 컬러 맵 ----------
def make_color_map(names, base_colors=None, s_scale=1.3, l_shift=-0.05):
    if base_colors is None:
        base_colors = _BASE_QUALS
    if not base_colors:
        import plotly.express as px
        base_colors = px.colors.qualitative.Plotly
    cmap = {}
    cycle = itertools.cycle(base_colors)
    for n in names:
        if n not in cmap:
            raw = next(cycle)
            cmap[n] = _brighten_color(raw, s_scale=s_scale, l_shift=l_shift)
    return cmap

# ---------- 5) 최종 생성 ----------
COLOR_WB   = make_color_map(WB_ORDER)
COLOR_SUBJ = make_color_map(SUBJ_ORDER)


def _font_path_safe():
    return GLOBAL_FONT_PATH or find_korean_font()  # 둘 다 없으면 None

SENT_SPLIT_RE = re.compile(r"(?<=[\.!\?]|[。！？]|[…]|[;]|[ㆍ]|[·]|[·\s]|[”’\"\'])\s+|(?<=[\.\?])(?=[가-힣A-Za-z0-9])")
KOR_END = "다다요요함음임니까니가라를에에서의으로로다되었으며했고하며"

def split_sentences(txt: str, max_len: int = 500) -> list[str]:
    """한국어/영문 혼합 문장 분할 + 과도하게 긴 문장 자르기"""
    if not isinstance(txt, str) or not txt.strip():
        return []
    # 1차 분할
    parts = re.split(r'(?<=[\.!\?])\s+|[。]|[！]|[？]|\n+', txt)
    out = []
    for p in parts:
        p = p.strip()
        if not p: 
            continue
        # 너무 길면 키워드 매칭 전에 2차 분할 시도
        if len(p) > max_len:
            chunks = re.split(r'[,;·]|(?<=\))\s+|(?<=\])\s+', p)
            for c in chunks:
                c = c.strip()
                if 30 <= len(c) <= max_len:
                    out.append(c)
        else:
            out.append(p)
    return [s for s in out if len(s) >= 20]

def shorten_around_keyword(sent: str, kw: str, half: int = 140) -> str:
    """키워드 기준 좌우로 문맥만 남겨 280자 내로 축약"""
    i = sent.lower().find(kw.lower())
    if i < 0:
        return sent[:280] + ("…" if len(sent) > 280 else "")
    left = max(0, i - half)
    right = min(len(sent), i + len(kw) + half)
    clip = (("…" if left > 0 else "") + sent[left:right] + ("…" if right < len(sent) else ""))
    return clip

def highlight(text: str, kw: str) -> str:
    pat = re.compile(re.escape(kw), re.IGNORECASE)
    return pat.sub(lambda m: f"<mark style='background:#fff3a1; padding:0 2px; border-radius:4px'>{m.group(0)}</mark>", text)

# === 교체: sample_sentences_for_keyword ===
def sample_sentences_for_keyword(df_in: pd.DataFrame, kw: str, text_cols: list[str], 
                                 per_kw: int = 3, seed: int = 42) -> list[tuple[str, str]]:
    """
    kw를 포함하는 문장을 최대 per_kw개 샘플링.
    반환: [(파일명, 문장_HTML), ...]
    """
    # ✔ 지역 임포트로 NameError 방지
    from random import Random

    # ✔ 시드 캐스팅(숫자/문자 상관없이 안전)
    try:
        base_seed = int(seed)
    except Exception:
        base_seed = 42

    rng = Random(base_seed + (hash(str(kw)) % 10000))

    texts = []
    cols = [c for c in text_cols if c in df_in.columns]
    if not cols:
        return []

    for _, row in df_in.iterrows():
        blob = " ".join(str(row.get(c, "") or "") for c in cols).strip()
        if not blob:
            continue
        sents = split_sentences(blob)
        hits = [s for s in sents if kw.lower() in s.lower()]
        if hits:
            fname = str(row.get("파일명") or row.get("Filename") or "").strip()
            rng.shuffle(hits)
            for s in hits[:per_kw * 2]:   # 약간 넉넉히 가져와 중복 제거/축약 후 선택
                texts.append((fname, s))

    # 중복 제거
    seen, uniq = set(), []
    for fn, s in texts:
        key = (fn, s.strip().lower())
        if key in seen:
            continue
        seen.add(key)
        uniq.append((fn, s))

    # 최종 샘플
    rng.shuffle(uniq)
    uniq = uniq[:per_kw]

    out = []
    for fn, s in uniq:
        clip = shorten_around_keyword(s, kw, half=140)
        out.append((fn, highlight(clip, kw)))
    return out




USE_NOUN_FILTER: bool = True   # ← 명사 필터 사용 여부(사이드바 토글로 바꿔도 됨)

# ==== 규칙 기반 명사 필터 (kiwi 불필요) ====

_HANGUL_RE = re.compile(r"[가-힣]+")
_TOKEN_RE  = re.compile(r"[A-Za-z]+(?:[-_][A-Za-z0-9]+)*|[0-9]+(?:\.[0-9]+)?|[가-힣]+")
_KO_POSTFIX_DROP = (
    "하다","적인","스러운","스러움","스럽다","되다","시키다","되며","하며","하다가",
    "으로","부터","처럼","까지","대로","라서","면서","면서도","하면서",
    "에서","에게","에게서","한테","이라서","이라도",
)
_KO_SINGLE_PARTICLE = set(list("은는이가을를의에와과도만"))
_EN_SHORT_MIN = 2

def _strip_ko_suffix(tok: str) -> str:
    for suf in _KO_POSTFIX_DROP:
        if tok.endswith(suf) and len(tok) > len(suf) + 1:
            tok = tok[:-len(suf)]
            break
    if len(tok) >= 3 and tok[-1] in _KO_SINGLE_PARTICLE:
        tok = tok[:-1]
    return tok

def _valid_token(tok: str) -> bool:
    if not tok: return False
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)?", tok): return False
    if len(tok) == 1: return False
    return True

def extract_nouns_korean(text: str) -> str:
    if not isinstance(text, str) or not text.strip(): return ""
    toks = _TOKEN_RE.findall(text)
    out = []
    for t in toks:
        if _HANGUL_RE.fullmatch(t):
            t = _strip_ko_suffix(t).strip()
            if not t: continue
            if t.lower() in STOP_ALL: continue
            if _valid_token(t): out.append(t)
        else:
            tl = t.lower()
            if len(tl) < _EN_SHORT_MIN: continue
            if tl in STOP_ALL: continue
            out.append(tl)
    return " ".join(out)

def _prep_docs(df_in: pd.DataFrame, text_cols: list[str]) -> list[str]:
    cols = [c for c in (text_cols or []) if c in df_in.columns]
    out = []
    for _, r in df_in.iterrows():
        t = " ".join(str(r.get(c, "") or "") for c in cols).strip()
        if not t: continue
        if USE_NOUN_FILTER:
            t = extract_nouns_korean(t)
        out.append(t)
    return out




# ===== 강한 stop/필터 =====
GENERIC_KO = {
    "경제","사회","정책","데이터","디지털","서비스","시장","운영","현황","전략","방안","도입","개선","구축","체계",
    "기반","중장기","보고","분석","지원","정부","공공","프로젝트","로드맵","비전","활용","강화","확대","평가","계획",
    "사례","현지","과제","인프라","플랫폼","시스템","포털","조달","법제","제도","가이드라인","기획","추진","성과",
    "과학기술","교육","보건","안전","보안","전자정부","스마트","혁신","연구","중소기업","산업","도시","센터","플렛폼",
    "현안","자료","분야","지원기관","대상기관","주제분류","ict","ICT","AI","인공지능","빅데이터","클라우드", "기대됩니다",
    "생산성", "IT", "대한", "자원", "투자", "디지털화", "무역", "법정", "재정", "정보화", "법적", "인력", "민간", "맞춤형", "행정", "비즈니스", "제조업", "건설", "광업", "BIM", "에너지", "불가리아", "지속가능한", "IP", "중남미", "공장", "양성", "우즈베키스탄", "높이고", "이러한", "유치", "전문",
    "정책적", "촉진할", "성공", "루마니아", "특허", "상황입니다", "검토하여", "환경", "생태계", "온두라스", "구축하여", "거버넌스", "필리핀", "시범", "심사", "업무", "데이터베이스", "온라인", "있으며", "산학연", "전자", "사이버", "다룹니다", "감사", "교통", "담고", "조세", "예산", "강조합니다", "세수",
    "투명성", "인센티브", "법률", "기술적", "함께", "인도네시아", "세무", "조직", "높여", "방글라데시", "수집", "확보하고", "멕시코", "효율성", "제공합니다", "적합한", "국제", "컨설팅", "분석한다", "공무원", "납세자", "납세", "가능하게", "크게", "선진", "향상", "공격", "이집트", "악성", "징수",
    "코드", "인적자원", "강조함", "제시함", "재활용", "요약됨", "시스템적", "슬로바키아", "재설계", "중복", "순환", "포함됨", "물류", "이루어지고", "진행", "진료", "도입하기", "통신", "원격", "빠르게", "도출합니다", "토지", "비현금", "농업", "방송", "축산물", "경매", "경영", "진료비", "원산지", "공기업",
    "관광", "교사", "주파수", "경보", "만성질환", "요르단", "재해복구", "Konza", "홍수", "가뭄", "식량", "JONEPS", "증명", "비기술적", "미디어", "전자회계감사", "수자원", "KLIS", "누락", "건설기술", "의료진", "공공의료", "설계하였습니다", "현금영수증", "공공재산", "처분", "이중화", "아날로그",
    "국세청", "자문", "시민들", "문서", "세르비아", "가입", "창출", "기업들", "crm", "육성", "장애", "인재", "협업", "기초", "업그레이드", "백업", "기관별", "유역", "의료", "환자", "안보", "지속가능성", "콘텐츠", "넘어", "증진", "공정한", "불평등", "피해", "칠레", "극복하기", "회계", "일부", "향후", "제공한다", "재정관리",
    "지원한다", "부가가치", "생산", "국가를", "분석합니다", "요인", "중점", "부족", "공공부문", "공공조달", "강화하", "오프라인", "탈세", "증대", "타지키스탄", "단지", "리투아니아", "말레이시아", "대응책", "탄자니아", "db", "이행계획", "벨라루스", "모로코", "브라질", "몰도바", "경영평", "우크라이나", "조지아", "카타르", "르완다",
    "케냐", "호주", "태국", "건설산업", "아크라", "대역", "학생", "DMA", "지질", "소득세", "운영자", "자메이카", "하드웨어", "수수료", "윤리", "아프리카", "도입률", "위험기반", "금융결제원", "문해력", "D-IP", "법인세", "오프", "ID", "상암"
}
GENERIC_EN = {
    "data","digital","service","services","system","systems","platform","portal","project","program","policy","policies",
    "plan","roadmap","model","models","evaluation","implementation","phase","final","interim","infrastructure","innovation"
}
STRONG_STOP = {s.lower() for s in (STOP | BASE_STOP | STOP_CUSTOM | GENERIC_KO | GENERIC_EN)}

# 이미 정의된 STOP/BASE_STOP/STOP_CUSTOM/GENERIC_KO/GENERIC_EN을 한데 모아 통합
def _collect_stop_all():
    STOP_ALL = set()
    for s in [globals().get("STOP"), globals().get("BASE_STOP"),
              globals().get("STOP_CUSTOM"), globals().get("GENERIC_KO"),
              globals().get("GENERIC_EN"), globals().get("STOP_LOW_ALL")]:
        if s:
            STOP_ALL |= {str(w).lower() for w in s}
    return STOP_ALL

STOP_ALL = _collect_stop_all()

def _normalize_token(t: str) -> str:
    t = re.sub(r"[\"'’“”()\[\]{}<>]", "", str(t)).strip()
    t = re.sub(r"\s{2,}", " ", t)
    return t

def _is_valid_kw(t: str) -> bool:
    if not t or len(t) < 2: return False
    if re.fullmatch(r"\d+(\.\d+)?", t): return False
    # 품사적 패턴 제거: '하다','적인','으로','하여' 등
    if re.search(r"(하다|적인|으로|하며|하고|에서|되어|하고자|된다|시키다|있다|된다)$", t):
        return False
    if re.search(r"[은는이가을를의에는로과와도만]$", t): return False
    return (t.lower() not in STRONG_STOP)


def contrastive_keywords_tfidf(
    docs_class: list[str],
    docs_neg: list[str],
    top_n: int = 60,
    ngram_bonus=(0.10, 0.20),
    eps: float = 1e-6,
) -> list[tuple[str, float]]:
    """
    score = log((tf_c/len_c + eps) / (tf_n/len_n + eps)) * log(1 + N / df)
            + n-그램 보너스
    - 불용어(STOP_ALL) 적용
    - KeyBERT/임베딩 없이 '클래스 vs 나머지' 대비로 구분력 확보
    - 영어 키워드는 최종 출력 시 대문자로 변환
    """
    def _tokenize_for_vocab(docs):
        out = []
        for d in docs:
            if not isinstance(d, str) or not d.strip():
                out.append([])
                continue
            toks = re.split(r"\s+", d.strip())
            toks = [t.lower() for t in toks if t and t.lower() not in STOP_ALL]
            out.append(toks)
        return out

    toks_c = _tokenize_for_vocab(docs_class)
    toks_n = _tokenize_for_vocab(docs_neg)

    N_docs = len(toks_c) + len(toks_n)
    df_term, cnt_c, cnt_n = Counter(), Counter(), Counter()
    len_c = len_n = 0

    for toks in toks_c + toks_n:
        if not toks: continue
        for t in set(toks): df_term[t] += 1

    for toks in toks_c:
        cnt_c.update(toks); len_c += len(toks)
    for toks in toks_n:
        cnt_n.update(toks); len_n += len(toks)

    len_c = max(len_c, 1); len_n = max(len_n, 1)

    picked = []
    for t in set(cnt_c.keys()) | set(cnt_n.keys()):
        if t in STOP_ALL: 
            continue
        tfc = cnt_c[t] / len_c
        tfn = cnt_n[t] / len_n
        lift = np.log((tfc + eps) / (tfn + eps))
        idf  = np.log(1.0 + N_docs / max(1, df_term[t]))
        score = lift * idf
        n = len(t.split())
        if n == 2: score += ngram_bonus[0]
        elif n >= 3: score += ngram_bonus[1]
        picked.append((t, float(score)))

    # === ▼ 영문 단어는 대문자화 ▼ ===
    def _upper_if_english(term: str) -> str:
        if re.fullmatch(r"[a-zA-Z0-9\-\_]+", term):  # 영문/숫자/하이픈 조합이면
            return term.upper()
        return term

    picked.sort(key=lambda x: x[1], reverse=True)
    uniq, seen = [], []
    for term, sc in picked:
        low = term
        if any(low in s or s in low for s in seen):
            continue
        seen.append(low)
        uniq.append((_upper_if_english(term), sc))   # ← 여기에 적용
        if len(uniq) >= top_n:
            break
    return uniq




def mmr_select_text(candidates: list[tuple[str, float]], k: int, lambda_div: float = 0.65) -> list[str]:
    if not candidates: return []
    candidates = sorted(candidates, key=lambda x: x[1], reverse=True)
    toks = {t: set(t.lower().split()) for t, _ in candidates}
    def sim(a: str, b: str) -> float:
        A, B = toks[a], toks[b]
        if not A or not B: return 0.0
        inter = len(A & B); union = len(A | B)
        return inter/union if union else 0.0
    selected = [candidates[0][0]]
    rest = [t for t, _ in candidates[1:]]
    while len(selected) < min(k, len(candidates)) and rest:
        best, best_score = None, -1e9
        for t in rest:
            rel = next(s for (tt, s) in candidates if tt == t)
            max_sim = max(sim(t, s) for s in selected) if selected else 0.0
            mmr = (1 - lambda_div) * rel - lambda_div * max_sim
            if mmr > best_score:
                best, best_score = t, mmr
        selected.append(best); rest.remove(best)
    return selected[:k]



def _docs_texts(df_in: pd.DataFrame, text_cols: List[str]) -> List[str]:
    cols = [c for c in (text_cols or []) if c in df_in.columns]
    if not cols:
        return []
    out = []
    for _, r in df_in.iterrows():
        blob = " ".join(str(r.get(c, "") or "") for c in cols).strip()
        if blob:
            out.append(blob)
    return out








def _contains_kw_doclevel(txt: str, kw: str) -> bool:
    # 영문은 단어경계, 한국어/혼합은 서브스트링도 허용
    pat = re.compile(rf"(?i)(\b{re.escape(kw)}\b)|({re.escape(kw)})")
    return bool(pat.search(txt))

def _doc_share(docs: list[str], kw: str) -> tuple[int, int, float]:
    n = len(docs) or 1
    c = sum(1 for t in docs if _contains_kw_doclevel(t, kw))
    return c, n, c / n

def _monroe_log_odds_z(c_a, n_a, c_b, n_b, alpha=0.5):
    pa = (c_a + alpha) / (n_a + 2*alpha)
    pb = (c_b + alpha) / (n_b + 2*alpha)
    logodds = math.log(pa/(1-pa+1e-12) + 1e-12) - math.log(pb/(1-pb+1e-12) + 1e-12)
    va = 1.0 / max(1e-9, (c_a + alpha)) + 1.0 / max(1e-9, (n_a - c_a + alpha))
    vb = 1.0 / max(1e-9, (c_b + alpha)) + 1.0 / max(1e-9, (n_b - c_b + alpha))
    return logodds / math.sqrt(va + vb)

@lru_cache(maxsize=2048)
def _embed_phrase(phrase: str):
    m = get_sbert()
    if m is None: return None
    return m.encode(phrase, normalize_embeddings=True)

def _centroid(docs: list[str]):
    m = get_sbert()
    if m is None or not docs: return None
    import numpy as _np
    embs = m.encode(docs, normalize_embeddings=True)
    return _np.mean(embs, axis=0)

def _cos(a, b):
    import numpy as _np
    if a is None or b is None: return 0.0
    return float(_np.clip(_np.dot(a, b), -1.0, 1.0))


def rerank_with_negative_contrast(
    candidates: list[tuple[str, float]],  # (kw, tfidf_score)
    df_all: pd.DataFrame,
    df_class: pd.DataFrame,
    df_negative: pd.DataFrame,
    text_cols: list[str],
    w_lift=0.65,
    w_logodds=0.35,
    # w_embed 제거
    unigram_penalty=0.25,
    bigram_bonus=0.10,
    trigram_bonus=0.15
) -> list[tuple[str, float, float, float, float, float]]:
    """
    반환: [(kw, final, lift, logodds_z, emb_delta(=0), kb_like_score)]
    여기서 kb_like_score는 TF-IDF score를 대입.
    """
    docs_cls = _prep_docs(df_class, text_cols)
    docs_neg = _prep_docs(df_negative, text_cols)

    out = []
    for kw, tfidf_sc in candidates:
        if not _is_valid_kw(kw):
            continue

        # 문서 내 포함 비율 (클래스/나머지)
        hit_c, n_c, share_c = _doc_share(docs_cls, kw)
        hit_n, n_n, share_n = _doc_share(docs_neg, kw)
        lift = (share_c + 1e-6) / (share_n + 1e-6)
        z = _monroe_log_odds_z(hit_c, n_c, hit_n, n_n, alpha=0.5)

        ngram = len(kw.split())
        gram_bonus = (trigram_bonus if ngram >= 3 else bigram_bonus if ngram == 2 else -unigram_penalty)

        # 임베딩 항은 0으로
        emb_delta = 0.0
        final = w_lift * float(np.log(max(lift, 1e-6))) + w_logodds * z + gram_bonus + 0.03 * tfidf_sc

        out.append((kw, final, lift, z, emb_delta, tfidf_sc))

    out.sort(key=lambda x: x[1], reverse=True)
    return out





# ========================= 국가 브리프(요약) 입력 =========================
st.sidebar.header("국가 브리프(요약)")

@st.cache_data(show_spinner=False)
def load_country_briefs_from_ipynb_bytes(b: bytes) -> dict:
    """ipynb 안의 code cell에서 'briefs = {...}' 딕셔너리를 찾아 반환"""
    import json
    nb = json.loads(b.decode("utf-8"))
    for cell in nb.get("cells", []):
        if cell.get("cell_type") == "code":
            code = "".join(cell.get("source", []))
            if "briefs" in code:
                ns = {}
                try:
                    exec(code, {}, ns)
                except Exception:
                    ns = {}
                briefs = ns.get("briefs", {})
                if isinstance(briefs, dict):
                    return briefs
    return {}

@st.cache_data(show_spinner=False)
def load_country_briefs_auto(app_dir: Path) -> tuple[dict, str | None]:
    """
    스크립트와 같은 폴더(또는 관용 서브폴더)에서 CountryBriefs.ipynb 자동 탐색
    반환: (briefs_map, 사용한 경로 또는 None)
    """
    candidates = [
        app_dir / "CountryBriefs.ipynb",
        app_dir / "assets" / "CountryBriefs.ipynb",
        app_dir / "data" / "CountryBriefs.ipynb",
    ]
    for p in candidates:
        if p.exists():
            try:
                return load_country_briefs_from_ipynb_bytes(p.read_bytes()), str(p)
            except Exception:
                pass
    return {}, None

# 현재 앱 디렉터리(스트림릿에서 __file__이 정상적으로 들어온다. 노트북/REPL 대비 fallback 동작)
APP_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()

brief_mode = st.sidebar.radio("소스", ["자동(같은 폴더)", "파일 업로드", "비활성화"], index=0, horizontal=True)
if st.sidebar.button("브리프 리로드", use_container_width=True):
    st.cache_data.clear()

briefs_map: dict = {}
brief_path_used: str | None = None

if brief_mode == "자동(같은 폴더)":
    briefs_map, brief_path_used = load_country_briefs_auto(APP_DIR)
    if brief_path_used:
        st.sidebar.caption(f"경로: `{brief_path_used}`")
    else:
        st.sidebar.info("같은 폴더에서 `CountryBriefs.ipynb`를 찾지 못했습니다.")
elif brief_mode == "파일 업로드":
    upb = st.sidebar.file_uploader("CountryBriefs.ipynb 업로드", type=["ipynb"])
    if upb is not None:
        briefs_map = load_country_briefs_from_ipynb_bytes(upb.read())
# 비활성화면 briefs_map == {}


# ========================= ICT 유형 브리프(요약) 입력 =========================
st.sidebar.header("ICT 유형 브리프(요약)")

@st.cache_data(show_spinner=False)
def load_wb_briefs_from_ipynb_bytes(b: bytes) -> dict:
    """ipynb 안의 code cell에서 'wb_briefs' (또는 'briefs', 'class_briefs') 딕셔너리 찾아 반환"""
    import json
    nb = json.loads(b.decode("utf-8"))
    for cell in nb.get("cells", []):
        if cell.get("cell_type") != "code":
            continue
        code = "".join(cell.get("source", []))
        ns = {}
        try:
            exec(code, {}, ns)
        except Exception:
            continue

        # 우선순위: wb_briefs > briefs > class_briefs > 그 외 'dict' 후보
        for key in ["wb_briefs", "briefs", "class_briefs"]:
            obj = ns.get(key)
            if isinstance(obj, dict):
                return obj

        # 혹시 모를 기타 딕셔너리도 스캔
        for k, v in ns.items():
            if isinstance(v, dict) and k.lower().endswith("briefs"):
                return v
    return {}


@st.cache_data(show_spinner=False)
def load_wb_briefs_auto(app_dir: Path) -> tuple[dict, str | None]:
    """
    스크립트와 같은 폴더/자주 쓰는 서브폴더에서 WB_ClassBriefs 노트북 자동 탐색
    반환: (wb_briefs_map, 사용한 경로 또는 None)
    """
    candidates = []
    for base in [app_dir, app_dir / "assets", app_dir / "data"]:
        for pat in [
            "WB_ClassBriefs.ipynb", "WBClassBriefs.ipynb",
            "wb_class_briefs.ipynb", "wbclass_briefs.ipynb",
            "*WB*Class*Brief*.ipynb",
        ]:
            candidates += list(base.glob(pat))

    for p in candidates:
        try:
            return load_wb_briefs_from_ipynb_bytes(p.read_bytes()), str(p)
        except Exception:
            continue
    return {}, None


wb_brief_mode = st.sidebar.radio("소스 (ICT 유형)", ["자동(같은 폴더)", "파일 업로드", "비활성화"],
                                 index=0, horizontal=True)

# '브리프 리로드' 버튼은 위에서 st.cache_data.clear()를 호출하므로 여기에도 적용됨
wb_briefs_map: dict = {}
wb_brief_path_used: str | None = None

if wb_brief_mode == "자동(같은 폴더)":
    wb_briefs_map, wb_brief_path_used = load_wb_briefs_auto(APP_DIR)
    if wb_brief_path_used:
        st.sidebar.caption(f"WB 브리프 경로: `{wb_brief_path_used}`")
    else:
        st.sidebar.info("같은 폴더에서 `WB_ClassBriefs.ipynb`를 찾지 못했습니다.")
elif wb_brief_mode == "파일 업로드":
    up_wb = st.sidebar.file_uploader("WB_ClassBriefs.ipynb 업로드", type=["ipynb"])
    if up_wb is not None:
        wb_briefs_map = load_wb_briefs_from_ipynb_bytes(up_wb.read())
# 비활성화면 wb_briefs_map == {}


# --------------------- 국가 매핑 ---------------------
COUNTRY_MAP = {
    # 🌏 아시아
    "대한민국": ("KOR","Korea, Republic of","대한민국"), "한국": ("KOR","Korea, Republic of","대한민국"),
    "북한": ("PRK","Korea, Democratic People's Republic of","북한"),
    "일본": ("JPN","Japan","일본"), "중국": ("CHN","China","중국"), "몽골": ("MNG","Mongolia","몽골"),
    "베트남": ("VNM","Vietnam","베트남"), "라오스": ("LAO","Laos","라오스"), "캄보디아": ("KHM","Cambodia","캄보디아"),
    "태국": ("THA","Thailand","태국"), "미얀마": ("MMR","Myanmar","미얀마"),
    "말레이시아": ("MYS","Malaysia","말레이시아"), "싱가포르": ("SGP","Singapore","싱가포르"),
    "인도네시아": ("IDN","Indonesia","인도네시아"), "필리핀": ("PHL","Philippines","필리핀"),
    "브루나이": ("BRN","Brunei Darussalam","브루나이"), "동티모르": ("TLS","Timor-Leste","동티모르"),
    "인도": ("IND","India","인도"), "파키스탄": ("PAK","Pakistan","파키스탄"), "네팔": ("NPL","Nepal","네팔"),
    "부탄": ("BTN","Bhutan","부탄"), "스리랑카": ("LKA","Sri Lanka","스리랑카"), "몰디브": ("MDV","Maldives","몰디브"),
    "카자흐스탄": ("KAZ","Kazakhstan","카자흐스탄"), "우즈베키스탄": ("UZB","Uzbekistan","우즈베키스탄"),
    "키르기스스탄": ("KGZ","Kyrgyzstan","키르기스스탄"), "타지키스탄": ("TJK","Tajikistan","타지키스탄"),
    "투르크메니스탄": ("TKM","Turkmenistan","투르크메니스탄"), "아프가니스탄": ("AFG","Afghanistan","아프가니스탄"),
    "이란": ("IRN","Iran","이란"), "이라크": ("IRQ","Iraq","이라크"), "시리아": ("SYR","Syrian Arab Republic","시리아"),
    "레바논": ("LBN","Lebanon","레바논"), "이스라엘": ("ISR","Israel","이스라엘"), "팔레스타인": ("PSE","Palestine","팔레스타인"),
    "요르단": ("JOR","Jordan","요르단"), "사우디아라비아": ("SAU","Saudi Arabia","사우디아라비아"),
    "예멘": ("YEM","Yemen","예멘"), "오만": ("OMN","Oman","오만"), "아랍에미리트": ("ARE","United Arab Emirates","아랍에미리트"),
    "카타르": ("QAT","Qatar","카타르"), "바레인": ("BHR","Bahrain","바레인"), "쿠웨이트": ("KWT","Kuwait","쿠웨이트"),

    # 🌍 유럽
    "영국": ("GBR","United Kingdom","영국"), "아일랜드": ("IRL","Ireland","아일랜드"), "프랑스": ("FRA","France","프랑스"),
    "독일": ("DEU","Germany","독일"), "이탈리아": ("ITA","Italy","이탈리아"), "스페인": ("ESP","Spain","스페인"),
    "포르투갈": ("PRT","Portugal","포르투갈"), "네덜란드": ("NLD","Netherlands","네덜란드"),
    "벨기에": ("BEL","Belgium","벨기에"), "룩셈부르크": ("LUX","Luxembourg","룩셈부르크"),
    "스위스": ("CHE","Switzerland","스위스"), "오스트리아": ("AUT","Austria","오스트리아"),
    "덴마크": ("DNK","Denmark","덴마크"), "노르웨이": ("NOR","Norway","노르웨이"), "스웨덴": ("SWE","Sweden","스웨덴"),
    "핀란드": ("FIN","Finland","핀란드"), "아이슬란드": ("ISL","Iceland","아이슬란드"),
    "체코": ("CZE","Czechia","체코"), "폴란드": ("POL","Poland","폴란드"), "헝가리": ("HUN","Hungary","헝가리"),
    "슬로바키아": ("SVK","Slovakia","슬로바키아"), "슬로베니아": ("SVN","Slovenia","슬로베니아"),
    "크로아티아": ("HRV","Croatia","크로아티아"), "세르비아": ("SRB","Serbia","세르비아"),
    "몬테네그로": ("MNE","Montenegro","몬테네그로"), "보스니아헤르체고비나": ("BIH","Bosnia and Herzegovina","보스니아헤르체고비나"),
    "북마케도니아": ("MKD","North Macedonia","북마케도니아"), "알바니아": ("ALB","Albania","알바니아"),
    "그리스": ("GRC","Greece","그리스"), "터키": ("TUR","Türkiye","터키"),
    "루마니아": ("ROU","Romania","루마니아"), "불가리아": ("BGR","Bulgaria","불가리아"),
    "몰도바": ("MDA","Moldova","몰도바"), "우크라이나": ("UKR","Ukraine","우크라이나"), "벨라루스": ("BLR","Belarus","벨라루스"),
    "리투아니아": ("LTU","Lithuania","리투아니아"), "라트비아": ("LVA","Latvia","라트비아"), "에스토니아": ("EST","Estonia","에스토니아"),
    "조지아": ("GEO","Georgia","조지아"), "아르메니아": ("ARM","Armenia","아르메니아"), "아제르바이잔": ("AZE","Azerbaijan","아제르바이잔"),
    "러시아": ("RUS","Russian Federation","러시아"),

    # 🌍 아프리카
    "이집트": ("EGY","Egypt","이집트"), "리비아": ("LBY","Libya","리비아"), "알제리": ("DZA","Algeria","알제리"),
    "모로코": ("MAR","Morocco","모로코"), "튀니지": ("TUN","Tunisia","튀니지"), "수단": ("SDN","Sudan","수단"),
    "남수단": ("SSD","South Sudan","남수단"), "에티오피아": ("ETH","Ethiopia","에티오피아"),
    "에리트레아": ("ERI","Eritrea","에리트레아"), "지부티": ("DJI","Djibouti","지부티"),
    "소말리아": ("SOM","Somalia","소말리아"), "케냐": ("KEN","Kenya","케냐"), "탄자니아": ("TZA","Tanzania","탄자니아"),
    "우간다": ("UGA","Uganda","우간다"), "르완다": ("RWA","Rwanda","르완다"), "부룬디": ("BDI","Burundi","부룬디"),
    "콩고민주공화국": ("COD","Democratic Republic of the Congo","콩고민주공화국"),
    "콩고공화국": ("COG","Republic of the Congo","콩고공화국"),
    "앙골라": ("AGO","Angola","앙골라"), "잠비아": ("ZMB","Zambia","잠비아"), "짐바브웨": ("ZWE","Zimbabwe","짐바브웨"),
    "말라위": ("MWI","Malawi","말라위"), "모잠비크": ("MOZ","Mozambique","모잠비크"), "마다가스카르": ("MDG","Madagascar","마다가스카르"),
    "남아프리카공화국": ("ZAF","South Africa","남아프리카공화국"), "보츠와나": ("BWA","Botswana","보츠와나"),
    "나미비아": ("NAM","Namibia","나미비아"), "레소토": ("LSO","Lesotho","레소토"), "에스와티니": ("SWZ","Eswatini","에스와티니"),
    "가나": ("GHA","Ghana","가나"), "코트디부아르": ("CIV","Côte d'Ivoire","코트디부아르"), "나이지리아": ("NGA","Nigeria","나이지리아"),
    "세네갈": ("SEN","Senegal","세네갈"), "말리": ("MLI","Mali","말리"), "니제르": ("NER","Niger","니제르"),
    "차드": ("TCD","Chad","차드"), "카메룬": ("CMR","Cameroon","카메룬"), "가봉": ("GAB","Gabon","가봉"),
    "적도기니": ("GNQ","Equatorial Guinea","적도기니"),

    # 🌎 아메리카
    "미국": ("USA","United States of America","미국"), "캐나다": ("CAN","Canada","캐나다"),
    "멕시코": ("MEX","Mexico","멕시코"), "브라질": ("BRA","Brazil","브라질"), "아르헨티나": ("ARG","Argentina","아르헨티나"),
    "칠레": ("CHL","Chile","칠레"), "페루": ("PER","Peru","페루"), "콜롬비아": ("COL","Colombia","콜롬비아"),
    "에콰도르": ("ECU","Ecuador","에콰도르"), "우루과이": ("URY","Uruguay","우루과이"), "파라과이": ("PRY","Paraguay","파라과이"),
    "볼리비아": ("BOL","Bolivia","볼리비아"), "베네수엘라": ("VEN","Venezuela","베네수엘라"),
    "쿠바": ("CUB","Cuba","쿠바"), "도미니카공화국": ("DOM","Dominican Republic","도미니카공화국"),
    "자메이카": ("JAM","Jamaica","자메이카"), "아이티": ("HTI","Haiti","아이티"),
    "코스타리카": ("CRI","Costa Rica","코스타리카"), "파나마": ("PAN","Panama","파나마"),
    "온두라스": ("HND","Honduras","온두라스"), "엘살바도르": ("SLV","El Salvador","엘살바도르"),
    "니카라과": ("NIC","Nicaragua","니카라과"), "과테말라": ("GTM","Guatemala","과테말라"),

    # 🌊 오세아니아
    "호주": ("AUS","Australia","호주"), "뉴질랜드": ("NZL","New Zealand","뉴질랜드"),
    "파푸아뉴기니": ("PNG","Papua New Guinea","파푸아뉴기니"), "피지": ("FJI","Fiji","피지"),
    "사모아": ("WSM","Samoa","사모아"), "통가": ("TON","Tonga","통가"), "바누아투": ("VUT","Vanuatu","바누아투"),
}

REGION_RULES = {
    "메콩강위원회": [
        ("KHM","Cambodia","캄보디아"),
        ("LAO","Laos","라오스"),
        ("THA","Thailand","태국"),
        ("VNM","Vietnam","베트남"),
    ],
    "호주·한국": [
        ("AUS","Australia","호주"),
        ("KOR","Korea, Republic of","대한민국"),
    ],
    "중남미 지역": [
        ("ARG","Argentina","아르헨티나"),("BRA","Brazil","브라질"),("CHL","Chile","칠레"),
        ("URY","Uruguay","우루과이"),("PRY","Paraguay","파라과이"),("BOL","Bolivia","볼리비아"),
        ("PER","Peru","페루"),("ECU","Ecuador","에콰도르"),("COL","Colombia","콜롬비아"),
        ("VEN","Venezuela","베네수엘라"),("GUY","Guyana","가이아나"),("SUR","Suriname","수리남"),
        ("MEX","Mexico","멕시코"),("GTM","Guatemala","과테말라"),("BLZ","Belize","벨리즈"),
        ("HND","Honduras","온두라스"),("SLV","El Salvador","엘살바도르"),("NIC","Nicaragua","니카라과"),
        ("CRI","Costa Rica","코스타리카"),("PAN","Panama","파나마"),
        ("CUB","Cuba","쿠바"),("DOM","Dominican Republic","도미니카공화국"),("HTI","Haiti","아이티"),
        ("JAM","Jamaica","자메이카"),("BRB","Barbados","바베이도스"),("BHS","Bahamas","바하마"),
        ("TTO","Trinidad and Tobago","트리니다드토바고"),("LCA","Saint Lucia","세인트루시아"),
        ("VCT","Saint Vincent and the Grenadines","세인트빈센트그레나딘"),
        ("KNA","Saint Kitts and Nevis","세인트키츠네비스"),
        ("GRD","Grenada","그레나다"),("DMA","Dominica","도미니카연방"),
        ("ATG","Antigua and Barbuda","앤티가바부다"),("PRI","Puerto Rico","푸에르토리코"),
        ("VIR","Virgin Islands (U.S.)","미국령 버진 아일랜드"),
        ("CYM","Cayman Islands","케이맨 제도"),("TCA","Turks and Caicos Islands","터크스 케이커스 제도"),
        ("ABW","Aruba","아루바"),("CUW","Curaçao","퀴라소"),("SXM","Sint Maarten","신트마르턴"),
        ("MAF","Saint Martin (French part)","생마르탱"),
    ],
}

def split_countries(x: str):
    if pd.isna(x): return []
    return [tok for tok in re.split(r"[·/,;|&]+|\s*,\s*|\s*&\s*", str(x).strip()) if tok]

def map_country_token(token: str):
    tkn = token.strip()
    if tkn in COUNTRY_MAP: return [COUNTRY_MAP[tkn]]
    if tkn in REGION_RULES: return REGION_RULES[tkn]
    out = []
    for s in re.split(r"[·/,;|&]+", tkn):
        s = s.strip()
        if s in COUNTRY_MAP: out.append(COUNTRY_MAP[s])
    return out

def expand_by_country(df_in: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, row in df_in.iterrows():
        tokens = split_countries(row.get("대상국",""))
        mapped = []
        for tk in tokens: mapped.extend(map_country_token(tk))
        if not mapped: continue
        for iso3, en, ko in mapped:
            d = row.to_dict()
            d.update({"iso3": iso3, "country_en": en, "country_ko": ko})
            rows.append(d)
    return pd.DataFrame(rows)

dfx = expand_by_country(df)

# --------------------- 세계 경계 + key_on 자동 ---------------------
@st.cache_data(show_spinner=False)
def get_world_geojson_auto() -> Dict:
    url = "https://raw.githubusercontent.com/python-visualization/folium/master/examples/data/world-countries.json"
    cache_dir = pathlib.Path(".ksp_cache"); cache_dir.mkdir(exist_ok=True)
    local = cache_dir / ("world-countries." + hashlib.md5(url.encode()).hexdigest() + ".json")
    if not local.exists():
        with urllib.request.urlopen(url, timeout=20) as resp: local.write_bytes(resp.read())
    return json.loads(local.read_text(encoding="utf-8"))

world_geojson = get_world_geojson_auto()

def resolve_geojson_key_on(gj: dict):
    feat0 = gj["features"][0]; props = feat0.get("properties", {})
    for c in ["iso_a3","ISO_A3","adm0_a3","ADM0_A3","wb_a3","WB_A3","ISO3","id"]:
        if c in props: return f"feature.properties.{c}", c, True
    if "id" in feat0: return "feature.id", "id", False
    raise ValueError("GeoJSON에서 ISO3 키를 찾지 못했습니다.")

key_on_info = resolve_geojson_key_on(world_geojson)

def augment_geojson_values(gj: dict, key_on_info, value_map: dict, value_prop: str):
    key_on_str, iso_key, in_props = key_on_info
    new_gj = copy.deepcopy(gj)
    for feat in new_gj["features"]:
        props = feat.setdefault("properties", {})
        iso = props.get(iso_key) if in_props else feat.get("id")
        props["ISO3"] = iso
        props[value_prop] = value_map.get(str(iso), 0)
    return new_gj

# --------------------- 지도/클릭 유틸 ---------------------
def make_base_map(center=[15,10], zoom=3):
    m = folium.Map(
        location=center, zoom_start=zoom, tiles=None,
        control_scale=True, prefer_canvas=True,
        world_copy_jump=False, max_bounds=True, max_bounds_viscosity=1.0,
        min_zoom=2
    )
    folium.TileLayer(tiles="CartoDB Positron", name="Base", control=False, no_wrap=True).add_to(m)
    return m

def extract_iso_from_stfolium(ret: dict):
    if not ret: return None
    iso_keys = ["ISO3","id","iso_a3","ISO_A3","adm0_a3","ADM0_A3","wb_a3","WB_A3"]
    obj = ret.get("last_object_clicked")
    if isinstance(obj, dict):
        props = obj.get("properties") or {}
        for k in iso_keys:
            if props.get(k): return props.get(k)
    lad = ret.get("last_active_drawing") or ret.get("last_active_drawing_geojson")
    if isinstance(lad, dict):
        props = lad.get("properties") or lad.get("feature", {}).get("properties") or {}
        for k in iso_keys:
            if props.get(k): return props.get(k)
    s = ret.get("last_object_clicked_popup")
    if isinstance(s, str):
        m = re.search(r"([A-Z]{3})", s)
        if m: return m.group(1)
    return None

# --------------------- 연도 파서 ---------------------
# === KEEP ONLY THIS ===
YEAR_RE = re.compile(r"(?:19|20)\d{2}")

def years_from_span(text):
    """
    '2025-2026' → [2025,2026], '2025' → [2025]
    숫자(정수/실수)도 허용. 범위가 뒤집혀도 정상화.
    """
    if pd.isna(text):
        return []

    if isinstance(text, (int, np.integer, float, np.floating)):
        y = int(text)
        return [y] if 1990 <= y <= 2035 else []

    t = str(text)
    t = t.replace("~", "-").replace("–", "-").replace("—", "-")
    t = re.sub(r"[()]", " ", t)

    years = [int(y) for y in YEAR_RE.findall(t)]
    years = [y for y in years if 1990 <= y <= 2035]

    # 범위 확장
    for a, b in re.findall(r"((?:19|20)\d{2})\s*-\s*((?:19|20)\d{2})", t):
        a, b = int(a), int(b)
        lo, hi = min(a, b), max(a, b)
        years.extend(range(lo, hi + 1))

    years = sorted(set(years))
    return years


# === 연도 텍스트 시리즈 선택 ===
def _year_text_series(df_in: pd.DataFrame) -> pd.Series:
    """연도 원천: 지정 컬럼 > 관용 컬럼들 > 요약/본문 등 텍스트 결합 → 문자열 시리즈 반환"""
    ys_col = globals().get("YEAR_SOURCE", None)
    if ys_col and ys_col in df_in.columns:
        return df_in[ys_col].astype(str)

    for c in ["사업 기간","연도","기간","Project Period","Years","Year","year"]:
        if c in df_in.columns:
            return df_in[c].astype(str)

    pool = [c for c in ["요약","주요 내용","파일명"] if c in df_in.columns]
    if pool:
        return df_in[pool].fillna("").astype(str).agg(" ".join, axis=1)

    # 최후: 빈 문자열 시리즈 (길이 맞춰서 반환)
    return pd.Series([""] * len(df_in), index=df_in.index, dtype=str)


@st.cache_data(show_spinner=False)
def expand_years(df_in: pd.DataFrame) -> pd.DataFrame:
    """
    - YEAR_SOURCE 지정/자동 탐색(_year_text_series)로 연도 텍스트를 확보
    - years_from_span으로 연도 리스트 추출 후 explode
    - '연도'가 DataFrame(중복명)으로 생겨도 안전하게 1-D로 강제
    """
    if df_in is None or df_in.empty:
        return pd.DataFrame({"연도": pd.Series([], dtype="Int64")})

    # ① 중복 컬럼 제거
    df1 = df_in.loc[:, ~df_in.columns.duplicated()].copy()

    # ② 연도 원천 시리즈 확보 (지정 컬럼 > 관용 컬럼들 > 텍스트 결합)
    ser = _year_text_series(df1)  # ← 앞서 추가한 헬퍼

    # ③ 연도 파싱
    years_list = ser.apply(years_from_span)
    if not years_list.apply(lambda x: bool(x)).any():
        return pd.DataFrame({"연도": pd.Series([], dtype="Int64")})

    # ④ explode
    dfy = df1.assign(__years=years_list).explode("__years").rename(columns={"__years": "연도"})

    # ⑤ '연도'를 반드시 1-D Series로 강제
    y = dfy["연도"]
    if isinstance(y, pd.DataFrame):  # 혹시라도 또 중복되면 첫 열 사용
        y = y.iloc[:, 0]
    y = pd.to_numeric(y, errors="coerce").astype("Int64")

    # 동일 이름 컬럼들 정리 후 삽입
    dup_cols = [c for c in dfy.columns if c == "연도"]
    dfy = dfy.drop(columns=dup_cols)
    dfy.insert(0, "연도", y.values)

    return dfy





dfy = expand_years(df)     # 키워드/주제 상대 트렌드는 '국가 중복 없는' 원본 df 기준

# --------------------- 보기 모드 ---------------------
st.sidebar.header("보기 모드")
mode = st.sidebar.radio("지도 유형", ["국가별 총계", "ICT 유형 단일클래스"], index=0)

# 연도 시각화 옵션 (히트맵 제거)
st.sidebar.header("연도 시각화 방식")
YEAR_OPTIONS = ["Line Bump", "순위 Bump"]
year_mode = st.sidebar.selectbox("표현 방식", YEAR_OPTIONS, index=0, key="year_mode")


clicked_iso = None

# ===================== ① 국가별 총계 (클릭) =====================
if mode == "국가별 총계":
    st.subheader("국가별 총 프로젝트 수")
    agg_country = dfx.groupby(["iso3","country_ko"], as_index=False).agg(n_docs=("파일명","nunique"))
    base = make_base_map()
    value_map = {r.iso3: int(r.n_docs) for _, r in agg_country.iterrows()}
    gj = augment_geojson_values(world_geojson, key_on_info, value_map, "ksp_docs")

    ch = folium.Choropleth(
        geo_data=gj, data=agg_country, columns=["iso3","n_docs"],
        key_on=key_on_info[0],
        fill_color="YlGnBu", fill_opacity=0.88,
        line_opacity=0.55, line_color="#7f7f7f",
        legend_name="보고서 수", nan_fill_color="#f0f0f0",
        highlight=True
    ); ch.add_to(base)
    ch.geojson.add_child(folium.features.GeoJsonTooltip(
        fields=["ISO3", "name" if "name" in gj["features"][0]["properties"] else "ISO3", "ksp_docs"],
        aliases=["ISO3", "국가", "보고서 수"], sticky=False
    ))
    ch.geojson.add_child(folium.features.GeoJsonPopup(fields=["ISO3"], aliases=["ISO3"]))
    ret = st_folium(base, height=560, use_container_width=True)
    clicked_iso = extract_iso_from_stfolium(ret)



# --------------------- 상세 패널 ---------------------
def find_korean_font() -> str | None:
    candidates = [
        r"C:\\Windows\\Fonts\\malgun.ttf", r"C:\\Windows\\Fonts\\Malgun.ttf",
        r"C:\\Windows\\Fonts\\NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/System/Library/Fonts/AppleGothic.ttf",
    ]
    for p in candidates:
        if os.path.exists(p): return p
    return None

# ======== Color utils ========
def _hex_to_rgb(hexstr: str) -> tuple[int,int,int]:
    s = hexstr.strip().lstrip("#")
    if len(s) == 3: s = "".join(c*2 for c in s)
    return int(s[0:2],16), int(s[2:4],16), int(s[4:6],16)

def rgba_str(color: str, alpha: float=0.5) -> str:
    if not color: return "rgba(0,0,0,0)"
    if color.startswith("rgb"):  # already rgba/rgb string
        return color if "rgba" in color else color.replace("rgb(", "rgba(").replace(")", f", {alpha})")
    r,g,b = _hex_to_rgb(color); return f"rgba({r},{g},{b},{alpha})"


# 공통 Plotly 스타일 (폰트 크게)
# 공통 Plotly 스타일 (폰트 크게) — 배경 투명 + 범례 줄바꿈 시 상단여백 자동 보정
# ---- PATCH B: Upgrade style_fig (consistent, professional charts) ----
# 안전한 style_fig: title이 None이면 기존 제목을 보존
def style_fig(fig, title=None, height=None, legend="top", top_margin=96,
              auto_legend_space=True, bg_color=None, bg_alpha=0.5):
    # legend presets
    if legend == "top":
        legend_cfg = dict(orientation="h", y=1.12, yanchor="bottom", x=0, xanchor="left", bgcolor="rgba(0,0,0,0)")
        m = dict(l=16, r=24, b=72, t=top_margin)
    elif legend == "bottom":
        legend_cfg = dict(orientation="h", y=-0.22, yanchor="top", x=0, xanchor="left", bgcolor="rgba(0,0,0,0)")
        m = dict(l=16, r=24, b=120, t=72)
    elif legend == "right":
        legend_cfg = dict(orientation="v", y=0.5, yanchor="middle", x=1.02, xanchor="left", bgcolor="rgba(0,0,0,0)")
        m = dict(l=16, r=160, b=72, t=top_margin)
    else:
        legend_cfg, m = dict(), dict(l=16, r=24, b=72, t=top_margin)

    # 배경 rgba
    def _hex_to_rgb(s):
        s = s.strip().lstrip("#")
        if len(s) == 3: s = "".join(c*2 for c in s)
        return int(s[0:2],16), int(s[2:4],16), int(s[4:6],16)
    def rgba_str(color, a=0.5):
        if not color: return "rgba(0,0,0,0)"
        if color.startswith("rgb"):  # rgb/rgba 문자열
            return color if "rgba" in color else color.replace("rgb(", "rgba(").replace(")", f", {a})")
        r,g,b = _hex_to_rgb(color); return f"rgba({r},{g},{b},{a})"
    bg_rgba = rgba_str(bg_color, bg_alpha) if bg_color else "rgba(0,0,0,0)"

    # layout kwargs를 동적으로 구성 (title은 None이면 건드리지 않음)
    layout_kwargs = dict(
        template=ui["plotly_template"],
        paper_bgcolor=bg_rgba,
        plot_bgcolor=bg_rgba,
        font=dict(family=_plotly_font_family(), color=ui["text"], size=16),
        height=height,
        margin=m,
        legend=legend_cfg if legend != "none" else None,
        hovermode="x unified",
        hoverlabel=dict(font=dict(size=13, family=_plotly_font_family()),    # ★ 여기
                        bgcolor="rgba(255,255,255,0.92)", bordercolor="rgba(0,0,0,0.1)"),
        modebar=dict(bgcolor="rgba(0,0,0,0)", color="#808B98", activecolor=ui["accent"]),
    )

    if title is not None:  # ← 제목을 새로 줄 때만 세팅
        layout_kwargs["title"] = dict(
            text=title, font=dict(size=22, family="Inter, Noto Sans KR"),
            x=0.0, xanchor="left", y=0.98, yanchor="top"
        )

    fig.update_layout(**layout_kwargs)

    # 축 스타일
    fig.update_xaxes(title_font=dict(size=16), tickfont=dict(size=13),
                     showline=True, linewidth=1, linecolor="rgba(0,0,0,0.25)",
                     gridcolor="rgba(127,127,127,0.16)", zeroline=False)
    fig.update_yaxes(title_font=dict(size=16), tickfont=dict(size=13),
                     showline=True, linewidth=1, linecolor="rgba(0,0,0,0.25)",
                     gridcolor="rgba(127,127,127,0.16)", zeroline=True, zerolinewidth=1,
                     zerolinecolor="rgba(127,127,127,0.20)")

    # 범례 줄바꿈 여유
    if auto_legend_space and getattr(fig.layout, "legend", None) and getattr(fig.layout.legend, "orientation", "") == "h":
        import numpy as _np
        n_items = sum(1 for tr in fig.data if getattr(tr, "showlegend", True) and getattr(tr, "name", None))
        rows_est = int(_np.ceil((n_items or 1)/8))
        if rows_est > 1:
            extra = 28 * (rows_est - 1)
            fig.update_layout(margin=dict(l=fig.layout.margin.l, r=fig.layout.margin.r,
                                          b=fig.layout.margin.b, t=max(fig.layout.margin.t or 0, top_margin + extra)))
    return fig



VIZ_BG = {
    "map_total":     "#E8F0FE",   # 국가별 총계 지도 카드
    "map_wb":        "#F1ECE3",   # ICT 유형 단일 지도 카드
    "donut_subj":    "#F6F7FB",   # 주제 도넛
    "donut_wb":      "#E8F6EE",   # WB 도넛
    "stack_100":     "#FFF7ED",   # 100% 누적 막대(주제×WB)
    "year_subj":     "#FDF2F8",   # 연도별 주제 시각화
    "year_wb":       "#EEF2FF",   # 연도별 WB 시각화
    "trend_up":      "#E2F2FF",   # 키워드 상승세
    "trend_down":    "#FFE4E6",   # 키워드 하락세
    "theme_up":      "#E5F9F0",   # 테마 상승세
    "theme_down":    "#FFF1F2",   # 테마 하락세
    "wc":            "#EEF1F6",   # 워드클라우드
    "bar_topk":      "#FAF7F2",   # Top-20 가로막대
}



def render_wordcloud_png(freqs: dict, bg_color: str, alpha: float=0.5,
                         width: int=820, height: int=460, scale: int=2) -> bytes | None:
    """워드클라우드 이미지를 PNG 바이트로 반환 (st.image 안전 표시용)."""
    if not freqs or not WC_FONT_PATH:
        return None

    wc = WordCloud(
        width=width, height=height, scale=scale,
        mode="RGBA", background_color=None,
        max_words=220, prefer_horizontal=0.95,
        max_font_size=108, min_font_size=10,
        font_path=WC_FONT_PATH, random_state=42
    ).generate_from_frequencies(freqs)

    wc_img = wc.to_image().convert("RGBA")  # PIL.Image
    r, g, b = _hex_to_rgb(bg_color)
    base    = Image.new("RGBA", wc_img.size, (r, g, b, int(255*alpha)))
    mixed   = Image.alpha_composite(base, wc_img)

    buf = io.BytesIO()
    mixed.save(buf, format="PNG")  # ★ 포맷 확정
    return buf.getvalue()


def auto_expand_top_margin_for_wrapped_legend(fig, base_top=100, items_per_row=8, extra_per_row=28):
    """legend를 이후에 top/horizontal로 변경한 경우 상단여백을 자동 증분."""
    import math
    leg = getattr(fig.layout, "legend", None)
    if not leg or getattr(leg, "orientation", "") != "h":
        return fig
    n_items = sum(1 for tr in fig.data if getattr(tr, "showlegend", True) and getattr(tr, "name", None))
    rows_est = math.ceil(n_items / max(1, items_per_row)) if n_items else 1
    if rows_est > 1:
        extra = extra_per_row * (rows_est - 1)
        cur = getattr(fig.layout.margin, "t", base_top) or base_top
        fig.update_layout(margin=dict(l=fig.layout.margin.l, r=fig.layout.margin.r,
                                      b=fig.layout.margin.b, t=max(cur, base_top + extra)))
    return fig

def force_legend_top_padding(fig, base_top=120,
                             items_per_row_hard=6,   # 한 줄에 6개만 수용한다고 가정(보수적)
                             char_unit=10.0,         # 라벨 길이 보정(10자 ≈ 1 유닛)
                             extra_per_row=40,       # 줄 늘 때마다 추가할 여백(px)
                             y_step=0.05):           # 줄 늘 때마다 legend y를 얼마나 더 올릴지
    """
    - 실제 화면폭을 알 수 없으므로 '항목 수 + 라벨 길이'로 줄 수를 과대추정해서 안전 여백을 확보.
    - items_per_row_hard=6 으로 낮춰 두 줄 판단을 쉽게 만듦(⇒ 항상 넉넉한 top margin).
    """
    import math

    # 범례 항목 수집
    names = [getattr(tr, "name", None) for tr in fig.data if getattr(tr, "showlegend", True)]
    names = [n for n in names if n]
    if not names:
        # 그래도 최소 base_top은 보장
        cur_t = getattr(fig.layout.margin, "t", 0) or 0
        if cur_t < base_top:
            fig.update_layout(margin=dict(l=fig.layout.margin.l, r=fig.layout.margin.r,
                                          b=fig.layout.margin.b, t=base_top))
        return fig

    # 유닛 계산(항목 1 + 라벨 길이에 비례한 보정)
    total_units = sum(1.0 + (len(str(n)) / char_unit) for n in names)

    # 보수적 줄수 추정
    rows_est = int(math.ceil(total_units / max(1e-6, items_per_row_hard)))
    rows_est = max(rows_est, 1)

    # 원하는 top margin & legend y
    want_top = base_top + (rows_est - 1) * extra_per_row
    y_target = 1.10 + (rows_est - 1) * y_step

    cur_t = getattr(fig.layout.margin, "t", 0) or 0
    fig.update_layout(
        legend=dict(orientation="h", y=y_target, yanchor="bottom", x=0, xanchor="left"),
        margin=dict(l=fig.layout.margin.l, r=fig.layout.margin.r,
                    b=fig.layout.margin.b, t=max(cur_t, want_top))
    )
    return fig

# ---- PATCH D: Tabbed detail panel ----
if mode == "국가별 총계":
    st.subheader("상세 패널")
    if clicked_iso:
        sub = dfx[dfx["iso3"]==clicked_iso].copy()
        if not sub.empty:
            country_name = sub["country_ko"].iloc[0]
            st.markdown(f"### {country_name} — 프로젝트 {sub['파일명'].nunique()}건")

            tab_overview, tab_cloud, tab_table = st.tabs(["개요", "워드클라우드 / 키워드", "테이블"])

            with tab_overview:
                st.markdown("#### 국가 브리프")
                if isinstance(briefs_map, dict) and briefs_map:
                    iso = clicked_iso
                    brief_txt = briefs_map.get(iso) or briefs_map.get(sub["country_en"].iloc[0], None) or briefs_map.get(country_name, None)
                    st.write(brief_txt if brief_txt else "브리프가 없습니다.")
                else:
                    st.info("좌측에서 CountryBriefs.ipynb를 지정하세요.")
                st.divider()

                st.markdown("#### 핵심 지표")
                _suby = expand_years(sub)  # 기존에 정의된 함수
                sub_years = sorted(set(_suby["연도"].dropna().astype(int).tolist()))
                cA, cB, cC = st.columns(3)
                with cA: st.metric("연도 범위", f"{min(sub_years) if sub_years else '-'}–{max(sub_years) if sub_years else '-'}")
                with cB: st.metric("ICT 유형 고유", f"{sub['ICT 유형'].astype(str).str.strip().nunique():,}")
                with cC: st.metric("대상기관 수", f"{sub['대상기관'].nunique():,}")

            with tab_cloud:
                st.markdown("#### 워드클라우드 (해시태그 + 요약/내용)")
                # 0) 토큰 수집 (해시태그 + 요약/내용)
                tokens: list[str] = []
                if "Hashtag_str" in sub.columns and sub["Hashtag_str"].notna().any():
                    for txt in sub["Hashtag_str"].dropna().astype(str):
                        tokens += [z.strip() for z in re.split(r"[;,]", txt) if z.strip()]
                elif "Hashtag" in sub.columns and sub["Hashtag"].notna().any():
                    for txt in sub["Hashtag"].dropna().astype(str):
                        tokens += [z.strip() for z in re.split(r"[;,]", txt) if z.strip()]

                pool_cols = [c for c in ["요약", "주요 내용"] if c in sub.columns]
                if pool_cols:
                    for txt in sub[pool_cols].fillna("").astype(str).agg(" ".join, axis=1).tolist():
                        for w in re.split(r"[^0-9A-Za-z가-힣]+", txt):
                            w = w.strip()
                            if len(w) >= 2:
                                tokens.append(w)

                # 1) 정제
                tokens = [
                    w for w in tokens
                    if w and w.lower() not in STOP_LOW and not re.fullmatch(r"\d+(\.\d+)?", w)
                ]
                freq = Counter(tokens)
                top_freqs = dict(freq.most_common(220))
                top20 = freq.most_common(10)

                # 2) 2열 배치 (워드클라우드 : 막대 = 6 : 7)
                lc, rc = st.columns([6, 7], gap="large")

                # Left) 워드클라우드 — “적당히 큼 + 선명”, 컬럼 폭에 맞춰 자동 맞춤
                with lc:
                    st.markdown("**워드클라우드**")
                    if top_freqs:
                        font_path = find_korean_font()
                        # 밝은/어두운 테마 자동 배경
                        bg = "white" if ui.get("plotly_template", "plotly_white") == "plotly_white" else ui.get("card", "#0f1115")
                        # (왼쪽) 워드클라우드 생성

                        

                        png_bytes = render_wordcloud_png(top_freqs, bg_color=VIZ_BG["wc"], alpha=0.5)
                        if png_bytes:
                            st.image(png_bytes, use_container_width=True, output_format="PNG")  # ★ 안전
                        else:
                            if not WC_FONT_PATH:
                                st.error("워드클라우드용 한글 폰트를 찾지 못했습니다. (리포에 assets/fonts/NanumGothic.ttf 추가 또는 packages.txt에 fonts-nanum)")
                            else:
                                st.info("표시할 단어가 부족합니다.")

                        

                        # 상위 키워드 칩(빠른 스캔용, 12개)
                        chips = " ".join([f'<span class="ksp-chip">{k}</span>' for k, _ in freq.most_common(12)])
                        st.markdown(chips, unsafe_allow_html=True)
                    else:
                        st.info("표시할 단어가 부족합니다.")

                # Right) Top-20 가로막대 — 라벨 잘림 방지 + 값 외부표시
                with rc:
                    st.markdown("**상위 키워드 Top-10**")
                    if top20:
                        bar_df = pd.DataFrame(top20, columns=["키워드", "빈도"])
                        fig_bar = px.bar(
                            bar_df.sort_values("빈도"),
                            x="빈도", y="키워드", orientation="h", text="빈도"
                        )
                        fig_bar = style_fig(fig_bar, "Top-10 키워드", legend="none", top_margin=64,
                        bg_color=VIZ_BG["bar_topk"], bg_alpha=0.5)
                        fig_bar.update_traces(textposition="outside", cliponaxis=False)
                        fig_bar.update_xaxes(title_text="빈도")
                        fig_bar.update_yaxes(title_text=None)
                        st.plotly_chart(style_fig(fig_bar, "Top-10 키워드", legend="none", top_margin=64),
                                        use_container_width=True, config={"displayModeBar": False})
                    else:
                        st.info("표시할 키워드가 부족합니다.")

            with tab_table:
                st.markdown("#### 프로젝트 목록")
                cols_pref = ["파일명","지원기관","사업 기간","주제분류(대)","ICT 유형","주요 내용","기대 효과","Hashtag_str","대상기관","대상국"]
                cols_use  = pick_existing_columns(sub, cols_pref, fallback_max=10)
                st.caption(f"표시 컬럼: {', '.join(cols_use)}")
                st.dataframe(sub[cols_use].drop_duplicates().reset_index(drop=True), use_container_width=True)

    else:
        st.info("상단 지도에서 국가를 클릭하면 상세가 열립니다.")

# ===================== ② ICT 유형 단일클래스 (지도를 국가 하이라이트로만 사용, 상세는 '클래스 전체' 기준) =====================
elif mode == "ICT 유형 단일클래스":
    st.subheader("ICT 유형 단일클래스 프로젝트 수")

    # 1) 클래스 선택
    wb_classes = [c for c in sorted(df["ICT 유형"].astype(str).str.strip().dropna().unique()) if c and c != "nan"]
    if not wb_classes:
        st.info("ICT 유형 값이 없습니다.")
        st.stop()

    sel = st.selectbox("ICT 유형 선택", wb_classes, index=0, key="wb_class_select_main")

    # 2) 지도(개요): 이 Class가 수행된 '국가 하이라이트'만, 클릭은 집계에 영향 X
    sub_wb_geo = dfx[dfx["ICT 유형"].astype(str).str.strip() == sel]  # 지도용(국가 확장본 사용)
    agg_geo = sub_wb_geo.groupby(["iso3", "country_ko"], as_index=False).agg(n=("파일명", "nunique"))
    value_map = {r.iso3: int(r.n) for _, r in agg_geo.iterrows()}
    gj = augment_geojson_values(world_geojson, key_on_info, value_map, "ksp_wb_cnt")

    base = make_base_map()
    ch = folium.Choropleth(
        geo_data=gj, data=agg_geo, columns=["iso3","n"],
        key_on=key_on_info[0],
        fill_color="PuBuGn", fill_opacity=0.90,
        line_opacity=0.5, line_color="#888",
        nan_fill_color="#fbfbfb", legend_name=f"{sel} 건수", highlight=True
    ); ch.add_to(base)
    ch.geojson.add_child(folium.features.GeoJsonTooltip(
        fields=["ISO3", "name" if "name" in gj["features"][0]["properties"] else "ISO3", "ksp_wb_cnt"],
        aliases=["ISO3","국가","건수"], sticky=False
    ))
    ch.geojson.add_child(folium.features.GeoJsonPopup(fields=["ISO3"], aliases=["ISO3"]))
    # 클릭은 보조 정보로만 사용(선택국가 표시에만 쓰고, 본문 집계에는 영향 X)
    ret = st_folium(base, height=520, use_container_width=True)
    clicked_iso = extract_iso_from_stfolium(ret)

    # 3) 상세 패널 — ★ 핵심: '클래스 전체' 기준으로 집계/시각화 ★
    st.subheader("상세 패널 — ICT 유형")

    # 본문 집계용은 '국가 확장 없는 원본 df'에서 필터 (동일 보고서가 다국가에 중복 집계되는 문제 방지)
    sub_wb = df[df["ICT 유형"].astype(str).str.strip() == sel].copy()

    # 상단 타이틀 + 메트릭
    n_docs = sub_wb["파일명"].nunique()
    part_countries = sub_wb_geo["iso3"].nunique()  # 참여국가 수(지도용 확장 df로 계산)
    st.markdown(f"### {sel} — 전체 프로젝트 {n_docs:,}건 · 참여국가 {part_countries:,}개국")

    tab_overview, tab_brief, tab_cloud, tab_extract, tab_table = st.tabs(
    ["개요", f"{sel} 종합요약", "워드클라우드 / 키워드", "키워드 문장 발췌", "테이블"]
    )


    # ---- (1) 개요: 연도 범위, 대상기관 수, 참여국가 상위 보기(선택 국가 보조 표기) ----
    with tab_overview:
        _suby = expand_years(sub_wb)
        sub_years = sorted(set(_suby["연도"].dropna().astype(int).tolist()))
        cA, cB, cC = st.columns(3)
        with cA:
            st.metric("연도 범위", f"{min(sub_years) if sub_years else '-'}–{max(sub_years) if sub_years else '-'}")
        with cB:
            st.metric("프토젝트 수", f"{n_docs:,}")
        with cC:
            st.metric("대상기관 수", f"{sub_wb['대상기관'].nunique():,}")

        # 참여국가 Top-10 (프로젝트 수 기준)
        st.markdown("#### 참여국가 (프로젝트 수 Top 10)")
        top_c = (sub_wb_geo.groupby(["country_ko"], as_index=False)
                          .agg(건수=("파일명","nunique"))
                          .sort_values("건수", ascending=False).head(10))
        if clicked_iso:
            # 클릭한 국가가 있으면 칩으로 보조 표기
            iso_name = sub_wb_geo.loc[sub_wb_geo["iso3"]==clicked_iso, "country_ko"]
            if len(iso_name):
                st.caption(f"지도로 선택된 국가: **{iso_name.iloc[0]}** (집계에는 영향 없음)")

        st.dataframe(top_c.reset_index(drop=True), use_container_width=True)

    # ---- (2) 종합요약: WB_ClassBriefs.ipynb에서 sel 키로 로드 ----
    with tab_brief:
        if isinstance(wb_briefs_map, dict) and wb_briefs_map:
            # 키 매칭(대소문자/공백 무시)
            key_fold = next((k for k in wb_briefs_map.keys()
                             if str(k).strip().lower() == str(sel).strip().lower()), None)
            brief_txt = wb_briefs_map.get(sel) or (wb_briefs_map.get(key_fold) if key_fold else None)
            st.write(brief_txt if brief_txt else f"'{sel}' 요약이 없습니다. WB_ClassBriefs.ipynb에 추가하세요.")
        else:
            st.info("좌측에서 WB_ClassBriefs.ipynb를 지정하세요.")

    # ---- (3) 워드클라우드/키워드: 클래스 전체 텍스트에서 생성 (국가 무관) ----
    with tab_cloud:
        tokens: list[str] = []
        if "Hashtag_str" in sub_wb.columns and sub_wb["Hashtag_str"].notna().any():
            for txt in sub_wb["Hashtag_str"].dropna().astype(str):
                tokens += [z.strip() for z in re.split(r"[;,]", txt) if z.strip()]
        elif "Hashtag" in sub_wb.columns and sub_wb["Hashtag"].notna().any():
            for txt in sub_wb["Hashtag"].dropna().astype(str):
                tokens += [z.strip() for z in re.split(r"[;,]", txt) if z.strip()]

        pool_cols = [c for c in ["요약", "주요 내용"] if c in sub_wb.columns]
        if pool_cols:
            for txt in sub_wb[pool_cols].fillna("").astype(str).agg(" ".join, axis=1).tolist():
                for w in re.split(r"[^0-9A-Za-z가-힣]+", txt):
                    w = w.strip()
                    if len(w) >= 2:
                        tokens.append(w)

        tokens = [w for w in tokens if w and w.lower() not in STOP_LOW and not re.fullmatch(r"\d+(\.\d+)?", w)]
        freq   = Counter(tokens)
        top20  = freq.most_common(10)
        top_freqs = dict(freq.most_common(220))

        lc, rc = st.columns([6, 7], gap="large")
        with lc:
            st.markdown("**워드클라우드**")
            if top_freqs:
                png_bytes = render_wordcloud_png(top_freqs, bg_color=VIZ_BG["wc"], alpha=0.5)
                if png_bytes:
                    st.image(png_bytes, use_container_width=True, output_format="PNG")  # ★ 안전
                else:
                    if not WC_FONT_PATH:
                        st.error("워드클라우드용 한글 폰트를 찾지 못했습니다. (리포에 assets/fonts/NanumGothic.ttf 추가 또는 packages.txt에 fonts-nanum)")
                    else:
                        st.info("표시할 단어가 부족합니다.")
                chips = " ".join([f'<span class="ksp-chip">{k}</span>' for k, _ in freq.most_common(12)])
                st.markdown(chips, unsafe_allow_html=True)
            else:
                st.info("표시할 단어가 부족합니다.")
        with rc:
            st.markdown("**상위 키워드 Top-10**")
            if top20:
                bar_df = pd.DataFrame(top20, columns=["키워드","빈도"])
                fig_bar = px.bar(bar_df.sort_values("빈도"), x="빈도", y="키워드",
                                 orientation="h", text="빈도")
                fig_bar = style_fig(fig_bar, f"Top-10 키워드 ({sel})",
                                    legend="none", top_margin=64,
                                    bg_color=VIZ_BG["bar_topk"], bg_alpha=0.5)
                fig_bar.update_traces(textposition="outside", cliponaxis=False)
                fig_bar.update_xaxes(title_text="빈도"); fig_bar.update_yaxes(title_text=None)
                st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("표시할 키워드가 부족합니다.")
        with tab_extract:
            st.markdown("#### 대표 키워드 문장 발췌 (임베딩 기반 · TF-IDF)")

            
            
                    
            # (1) 텍스트 컬럼 자동 선택 (full_text > 주요 내용 > 요약)
            # (1) 텍스트 컬럼 자동 선택
            pref_cols = ["full_text", "주요 내용", "요약"]
            text_cols = [c for c in pref_cols if c in sub_wb.columns]
            if not text_cols:
                st.info("문장 발췌에 사용할 텍스트 컬럼이 없습니다. (full_text/주요 내용/요약 중 하나 필요)")
                st.stop()
            
            # ▼ 이 줄을 "키워드 선택/렌더" 블록의 맨 위에 추가
            RUN_TAG = f"extract_once::{sel}::{','.join(text_cols)}"
            
            
            # --- 여기부터 당신의 기존 코드 ---
            # (2) 문서 준비
            docs_class = _prep_docs(sub_wb, text_cols)
            docs_neg   = _prep_docs(df[df["ICT 유형"].astype(str).str.strip() != sel], text_cols)
        
            # (3) 대비형 TF-IDF 키워드
            candidates = contrastive_keywords_tfidf(
                docs_class=docs_class,
                docs_neg=docs_neg,
                top_n=80,
                ngram_bonus=(0.10, 0.20)
            )
        
            # (4) 선택 수 k는 하드 클램프
            k_req = int(st.session_state.get("topk_auto", 8))
            k     = max(1, min(k_req, 8))
            diversity = float(st.session_state.get("diversity", 0.65))
            per_kw    = int(st.session_state.get("per_kw", 2))
            seed      = int(st.session_state.get("seed", 42))
        
            kw_selected = mmr_select_text(candidates, k=k, lambda_div=diversity)
            kw_selected = kw_selected[:k]  # 혹시라도 이후에 누가 더 붙이면 잘라서 보장
            st.caption(f"[debug] k={k} / candidates={len(candidates)} / selected={len(kw_selected)}")
        
       
        
            # (5) 문장 샘플링/표시 (기존 로직 재사용)
            if not kw_selected:
                st.info("선택된 키워드가 없습니다.")
            else:
                st.markdown("<style>.ksp-quote{background:var(--card);border:1px solid var(--border);padding:10px;border-radius:10px;margin:6px 0}</style>", unsafe_allow_html=True)
                cols = st.columns(2, gap="large") if len(kw_selected) >= 6 else [st.container()]
                for i, kw in enumerate(kw_selected):
                    target_col = cols[i % len(cols)]
                    with target_col:
                        st.markdown(f"**🔎 {kw}**")
                        sents = sample_sentences_for_keyword(sub_wb, kw, text_cols, per_kw=int(per_kw), seed=int(seed))
                        if not sents:
                            st.caption("· 일치 문장을 찾지 못했습니다.")
                        else:
                            for fn, html_sent in sents:
                                meta = f"<div style='font-size:12px;color:#6b7280'>{fn}</div>" if fn else ""
                                st.markdown(f"<div class='ksp-quote'>{html_sent}{meta}</div>", unsafe_allow_html=True)
            




    # ---- (4) 테이블: 클래스 전체 보고서 목록 ----
    with tab_table:
        st.markdown("#### 프로젝트 목록 (클래스 전체)")
        cols_pref = ["파일명","지원기관","사업 기간","주제분류(대)","ICT 유형","대상국","대상기관","주요 내용","기대 효과","Hashtag_str"]
        cols_use  = pick_existing_columns(sub_wb, cols_pref, fallback_max=12)
        st.caption(f"표시 컬럼: {', '.join(cols_use)}")
        st.dataframe(sub_wb[cols_use].drop_duplicates().reset_index(drop=True), use_container_width=True)





# --------------------- 전체 분포 대시보드 ---------------------
st.markdown("---")
st.subheader("전체 분포 대시보드")

# 주제 도넛
subj_counts = df["주제분류(대)"].fillna("미분류").astype(str).str.strip().replace({"nan":"미분류"}).value_counts().reindex(SUBJ_ORDER, fill_value=0).reset_index()
subj_counts.columns = ["주제분류(대)","count"]
fig1 = px.pie(subj_counts, names="주제분류(대)", values="count", hole=0.55,
              category_orders={"주제분류(대)": SUBJ_ORDER},
              color="주제분류(대)", color_discrete_map=COLOR_SUBJ)
fig1 = style_fig(fig1, "주제분류(대) 분포", legend="right", top_margin=120,
                 bg_color=VIZ_BG["donut_subj"], bg_alpha=0.5)

# ICT 도넛
wb_counts = (df["ICT 유형"].astype(str).str.strip().replace({"nan":"미분류"}).fillna("미분류").value_counts()
             .reindex(WB_ORDER, fill_value=0).reset_index())
wb_counts.columns = ["ICT 유형","count"]
fig2 = px.pie(wb_counts, names="ICT 유형", values="count", hole=0.55,
              category_orders={"ICT 유형": WB_ORDER},
              color="ICT 유형", color_discrete_map=COLOR_WB)
fig2 = style_fig(fig2, "ICT 유형 분포", legend="right", top_margin=120,
                 bg_color=VIZ_BG["donut_wb"], bg_alpha=0.5)


c0, c00 = st.columns([1,1], gap="large")
with c0: st.plotly_chart(fig1, use_container_width=True)
with c00: st.plotly_chart(fig2, use_container_width=True)

# (3) 주제×WB 100% 누적 막대
cross = (df.assign(WB=df["ICT 유형"].astype(str).str.strip().replace({"nan":"미분류"}).fillna("미분류"))
           .groupby(["주제분류(대)","WB"], as_index=False).size())

pivot = cross.pivot(index="주제분류(대)", columns="WB", values="size").fillna(0)
pivot_pct = (pivot
    .div(pivot.sum(axis=1).replace(0, np.nan), axis=0)
    .fillna(0)
    .reset_index()
    .melt(id_vars="주제분류(대)", var_name="WB", value_name="pct"))

fig3 = px.bar(
    pivot_pct,
    x="주제분류(대)", y="pct",
    color="WB", barmode="stack",
    category_orders={"WB": WB_ORDER, "주제분류(대)": SUBJ_ORDER},
    color_discrete_map=COLOR_WB,
)
fig3.update_yaxes(range=[0,1], tickformat=".0%")
fig3.update_layout(bargap=0.68, bargroupgap=0.08)
fig3 = style_fig(fig3, "주제분류(대)별 ICT 유형 비중 (100%)",
                 legend="right", top_margin=120,
                 bg_color=VIZ_BG["stack_100"], bg_alpha=0.5)
st.plotly_chart(fig3, use_container_width=True)


# ---------- (4)(5) 연도별 비중 — 선택형 시각화 (히트맵 제거) ----------
dfy_valid = dfy.dropna(subset=["연도"]).copy()

def time_share(df_in: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """
    - 중복 컬럼 제거
    - '연도'와 group_col이 DataFrame로 들어오면 첫 열만 사용
    """
    df1 = df_in.loc[:, ~df_in.columns.duplicated()].copy()

    y = df1["연도"]
    if isinstance(y, pd.DataFrame):
        y = y.iloc[:, 0]

    gcol = df1[group_col]
    if isinstance(gcol, pd.DataFrame):
        gcol = gcol.iloc[:, 0]

    tmp = pd.DataFrame({"연도": y, group_col: gcol})
    g = tmp.groupby(["연도", group_col], as_index=False).size()
    totals = g.groupby("연도")["size"].transform("sum")
    g["pct"] = g["size"] / totals
    return g


def draw_year_chart(g, group_col, title_prefix):
    if g.empty:
        fig = px.line()
        return style_fig(fig, f"{title_prefix} (연도 추출 불가)")

    is_subj = (group_col == "주제분류(대)")
    c_orders = {"연도": sorted(g["연도"].unique())}
    if is_subj:
        c_orders[group_col] = SUBJ_ORDER
        color_map = COLOR_SUBJ
    else:
        # group_col == "WB" (ICT 유형)
        c_orders[group_col] = WB_ORDER
        color_map = COLOR_WB

    if year_mode == "순위 Bump":
        ranks = g.copy()
        ranks["rank"] = ranks.groupby("연도")["pct"].rank(ascending=False, method="dense")
        fig = px.line(
            ranks, x="연도", y="rank", color=group_col, markers=True,
            category_orders=c_orders, color_discrete_map=color_map
        )
        fig.update_traces(line=dict(width=3), marker=dict(size=8))
        fig.update_yaxes(autorange="reversed", dtick=1, title="순위(1=최상)")
        return style_fig(fig, f"{title_prefix} — 순위 Bump", legend="top", top_margin=120)
    else:
        # 100% 누적 막대 대신 라인 비중 그래프를 쓰기로 한 현재 코드에 맞춤
        fig = px.line(
            g, x="연도", y="pct", color=group_col, markers=True,
            labels={"pct":"비중"},
            category_orders=c_orders, color_discrete_map=color_map
        )
        fig.update_yaxes(range=[0,1], tickformat=".0%")
        return style_fig(fig, f"{title_prefix} — 비중 Bump", legend="top", top_margin=120)


if not dfy_valid.empty:
    g_subj = time_share(dfy_valid, "주제분류(대)")
    g_wb   = time_share(dfy_valid.assign(WB=dfy_valid["ICT 유형"].astype(str).str.strip().replace({"nan":"미분류"}).fillna("미분류")), "WB")
else:
    g_subj = pd.DataFrame(columns=["연도","주제분류(대)","size","pct"])
    g_wb   = pd.DataFrame(columns=["연도","WB","size","pct"])

fig4 = draw_year_chart(g_subj, "주제분류(대)", "연도별 주제분류(대) 비중")
fig5 = draw_year_chart(g_wb, "WB", "연도별 ICT 유형 비중")
c1, c2 = st.columns([1,1], gap="large")
with c1: st.plotly_chart(fig4, use_container_width=True)
with c2: st.plotly_chart(fig5, use_container_width=True)

# =====================================================================
# 추가 시각화 ①: 대표 키워드 상대 트렌드(상승세/하락세)  — Plotly
# =====================================================================
st.markdown("---")
st.subheader("AI 추출 키워드 상대 트렌드 (상승/하락)")

# '대표 키워드 상대 트렌드'에 추가 적용할 불용어
BASE_STOP = { 
    "경제","사회","사회정책","정책","데이터","디지털","서비스","시장","운영","현황","전략","방안","도입",
    "개선","구축","체계","기반","중장기","최종보고","중간보고","분석","지원","정부","공공","국가","차세대",
    "평가","프로젝트","로드맵","비전","활용","강화","확대","예정","연구","사례","현지","정합성","수립",
    "마스터플랜","개편","고도화","개정","개발","업그레이드","적용","시범","컨설팅","협력","정비","도시",
    "인프라","플랫폼","플렛폼","시스템","포털","조달","법제","제도","가이드라인","기획","추진","성과",
    "현안","과제","기술","계획","자료","보고","요약","장단점","한계","경보","안전","보안","성장",
    "전자세금계산서","법적","의무화","예산","가뭄","교육","개인정보보호","vat","건설","vision","세정","다층","민간","근거",
    "산업","세수","세무조직","재정","인사","재무부","투자","통합","훈련","홍보","조정","무역","홍수","클라우드","데이터센터",
    "전자정부","추정","소스","콘텐츠", "조세", "의료", "교통", "ip", "Ip", "인증", "페기물", "납세자", "의약품", "생산성",
    "전자", "감사", "공무원의", "등록", "집행", "사이버", "조세행정", "높여", "원격", "사용자", "콜센터", "기관별", "에너지", "전자조달", "금융", "납세", "정보화",
    "있음", "지속가능한",
    # 축/라벨 관련 불용어 추가
    "연도","년도","year","years",
    # 영문 상투어
    "and","or","of","in","to","for","the","with","on","by","from","eu",
    "data","digital","service","services","policy","strategy","plan","roadmap","project","program",
    "system","platform","portal","model","evaluation","improvement","implementation","phase","final","interim",
    "procurement"
}

BASE_STOP_LOW = {s.lower() for s in BASE_STOP}
 

# ---- 고정 파라미터 (슬라이더 제거)
TOP_K_PER_FIG = 25   # 상승/하락 각각 표기 키워드 수
ROLL = 5             # Jeffreys + 롤링 윈도(년)
ALPHA = 0.7
WINDOW_YEARS = 10
RECENT_YEARS = 5
MIN_DOCS_BASE, MIN_YEARS_BASE = 4, 3
RECENT_DOCS_MIN, RECENT_YEARS_MIN = 2, 2

HASHTAG_COL = "Hashtag" if "Hashtag" in df.columns else ("Hashtag_str" if "Hashtag_str" in df.columns else None)

def clean(s): return s.astype(str).str.replace(r"\s+"," ",regex=True).str.strip()




SYN = {"sme":"SME","pki":"PKI","ai":"AI","ict":"ICT","bigdata":"빅데이터","big data":"빅데이터",
       "e-gp":"전자조달","egp":"전자조달","e-procurement":"전자조달","data center":"데이터센터","cloud":"클라우드",
       "platform":"플랫폼","platfrom":"플랫폼","플렛폼":"플랫폼", "ifmis":"IFMIS", "bim":"BIM"}

def norm_token(x: str) -> str:
    x = re.sub(r"[\"'’“”()\[\]{}<>]", "", x.strip()); xl = x.lower()
    return SYN.get(xl, x)

import ast

def _clean_token(x: str) -> str:
    # 따옴표/대괄호/괄호류 제거 + 공백 정리 + 동의어 매핑
    x = re.sub(r"[\"'’“”()\[\]{}<>]", "", str(x).strip())
    x = re.sub(r"\s{2,}", " ", x)
    xl = x.lower()
    return SYN.get(xl, x)

def split_hashtags(s, stopset):
    """
    해시태그 셀 하나를 -> 토큰 리스트로.
    - "['조달','전자조달']" 같은 리스트 문자열은 literal_eval로 파싱
    - 실패하면 일반 구분기호(,;/ 공백2+)로 분할
    - 국가/숫자/불용어/잡문자 제거
    """
    if not isinstance(s, str) or not s.strip():
        return []

    items = []
    txt = s.strip()

    # 1) 리스트 문자열이면 안전 파싱
    if txt.startswith("[") and txt.endswith("]"):
        try:
            arr = ast.literal_eval(txt)
            if isinstance(arr, (list, tuple)):
                items = [str(z) for z in arr]
        except Exception:
            items = []  # 파싱 실패하면 아래 fallback로 이어감

    # 2) fallback: 일반 분할
    if not items:
        items = re.split(r"[,\;/]| {2,}", txt)

    out = []
    for t in items:
        t = _clean_token(t)
        core = re.sub(r"\s+", "", t.lower())
        if not core or len(core) < 2:
            continue
        if re.fullmatch(r"[\W_]+", core) or re.fullmatch(r"\d+(\.\d+)?", core):
            continue
        if core in stopset:
            continue
        out.append(t)

    # 중복 제거(대소문자 무시)
    seen = set()
    dedup = []
    for w in out:
        k = w.lower()
        if k not in seen:
            seen.add(k)
            dedup.append(w)
    return dedup


def jeffreys_rolling_ratio(num, den, k=ROLL, alpha=ALPHA):
    numr = (num + alpha).rolling(k, center=True, min_periods=1).sum()
    denr = (den + 2*alpha).rolling(k, center=True, min_periods=1).sum()
    return (numr/denr*100.0).fillna(0.0)

@st.cache_data(show_spinner=False)
def build_keyword_time(df_in: pd.DataFrame, stop_extra: set):
    df_local = df_in.loc[:, ~df_in.columns.duplicated()].copy()

    # 연도 소스: 지정/자동(요약·내용 포함) → 리스트로 확장
    ser_year = _year_text_series(df_local)
    years_list = ser_year.apply(years_from_span)
    all_years = sorted({y for ys in years_list for y in (ys or [])})
    if not all_years:
        return [], {}, pd.Series([], dtype=int), pd.DataFrame()

    # 동적 불용어(대분류/클래스/국가 등)
    dyn = set()
    for col in ["주제분류(대)", "ICT 유형", "대상국", "대상기관", "지원기관"]:
        if col in df_local.columns:
            dyn |= {str(v).strip().lower() for v in df_local[col].dropna().unique()}
    stopset = {w.lower() for w in stop_extra} | dyn

    # 해시태그 토큰 (리스트 문자열 포함 안전 파싱)
    HASHTAG_COL = "Hashtag" if "Hashtag" in df_local.columns else ("Hashtag_str" if "Hashtag_str" in df_local.columns else None)
    if HASHTAG_COL:
        tokens_by_row = [split_hashtags(s, stopset) for s in df_local[HASHTAG_COL].fillna("").astype(str)]
    else:
        tokens_by_row = [[] for _ in range(len(df_local))]

    # 연도별 총 문서 수
    docs_per_year = pd.Series(0, index=all_years, dtype=int)
    for ys in years_list:
        for y in (ys or []):
            docs_per_year[y] += 1

    # 연도별 키워드 등장 수(문서 단위 중복 제거)
    kw_doc = {y: Counter() for y in all_years}
    for toks, ys in zip(tokens_by_row, years_list):
        if not ys or not toks:
            continue
        for y in ys:
            kw_doc[y].update(set(toks))

    return all_years, kw_doc, docs_per_year, df_local



all_years, kw_doc, docs_per_year, _ = build_keyword_time(df, STOP | BASE_STOP)


def ensure_topk(pool_tokens, need_k, docs_per_year, kw_doc, years):
    """
    토큰 선별: (1) 기본 컷오프 충족 → (2) 최근 RECENT_YEARS 컷오프 대체 → (3) 최근성/변동성 랭크 보충
    항상 need_k 개수를 반환하려고 시도.
    """
    def cnt_years_for(k, yrs):
        cnt = sum(kw_doc[y][k] for y in yrs)
        yrs_hit = sum(kw_doc[y][k] > 0 for y in yrs)
        return cnt, yrs_hit

    # (1) 기본 컷오프
    base_ok = []
    for k in pool_tokens:
        c, yh = cnt_years_for(k, years)
        if c >= MIN_DOCS_BASE and yh >= MIN_YEARS_BASE:
            base_ok.append(k)

    # (2) 최근 컷오프 (부족하면 대체 허용)
    last = years[-min(RECENT_YEARS, len(years)):]
    recent_ok = []
    for k in pool_tokens:
        c, yh = cnt_years_for(k, last)
        if c >= RECENT_DOCS_MIN and yh >= RECENT_YEARS_MIN:
            recent_ok.append(k)

    # (3) 랭크 — 최근 적중수, 최근 등장연수, 변동성
    recent_hits  = Counter(); recent_years = Counter()
    for y in last:
        recent_hits.update(kw_doc[y])
        for k,c in kw_doc[y].items():
            if c>0: recent_years[k]+=1
    var_proxy = {k: np.var([kw_doc[y][k]>0 for y in years]) for k in set().union(*[kw_doc[y].keys() for y in years])}
    ranked = sorted(set().union(*[kw_doc[y].keys() for y in years]),
                    key=lambda k: (recent_hits[k], recent_years[k], var_proxy.get(k,0.0)),
                    reverse=True)

    # 합치기 + need_k 채울 때까지 보충
    out = list(dict.fromkeys(base_ok))
    if len(out) < need_k:
        out = list(dict.fromkeys(out + recent_ok))
    if len(out) < need_k:
        out = list(dict.fromkeys(out + ranked))
    return out[:need_k]


def build_share_lift(tokens, years, kw_doc, docs_per_year):
    share = pd.DataFrame({
        k: jeffreys_rolling_ratio(
            pd.Series({y: kw_doc[y][k] for y in years}, dtype=float),
            docs_per_year.astype(float))
        for k in tokens
    }, index=years)
    w = docs_per_year / docs_per_year.sum()
    base = (share.mul(w, axis=0)).sum(axis=0).replace(0, np.nan)
    lift = share.div(base, axis=1).replace([np.inf,-np.inf], np.nan).fillna(0.0)
    return share, lift


def cagr(series):
    s = np.asarray(series, float)
    s = np.where(s<=0, np.nan, s)
    s = pd.Series(s).dropna()
    if len(s)<2: return 0.0
    n = len(s)-1
    return ((s.iloc[-1]/s.iloc[0])**(1/n) - 1) * 100.0


# ---- Plotly 라인 차트 생성

def plot_trend_plotly(keys, years_plot, lift_df, title):
    fig = go.Figure()
    for k in keys:
        ys = [lift_df.loc[y, k] for y in years_plot]
        fig.add_trace(go.Scatter(x=years_plot, y=ys, mode="lines+markers", name=k,
                                 line=dict(width=3), marker=dict(size=8), connectgaps=True))
    fig.add_hline(y=1.0, line_width=1.5, line_dash="dash", opacity=0.6)
    fig.update_xaxes(title_text="연도")
    fig.update_yaxes(title_text="lift (배)")
    return style_fig(fig, title, legend="right", top_margin=100)

# ---- Plotly: 라인 끝 라벨(겹침 방지) 유틸
# --- REPLACE THIS FUNCTION ENTIRELY ---
def add_line_end_labels(fig, years_plot, df, keys,
                        min_gap=0.03, xpad_frac=0.16, right_margin=200):
    """
    years_plot: 정렬된 연도 리스트
    df: [index=years, columns=keys] 또는 [index=keys, columns=years] 모두 처리
    keys: 라벨링할 시리즈 이름들
    """
    import numpy as _np

    if not keys:
        return fig

    # 1) 데이터 방향 자동 보정: keys가 열에 없으면 전치
    df2 = df if (keys[0] in df.columns) else df.T

    # 2) 실제로 존재하는 키만 사용
    keys = [k for k in keys if k in df2.columns]
    if not keys:
        return fig

    # 3) y 범위 계산
    ymins = [_np.nanmin(df2.loc[years_plot, k].astype(float).values) for k in keys]
    ymaxs = [_np.nanmax(df2.loc[years_plot, k].astype(float).values) for k in keys]
    y_min, y_max = float(min(ymins)), float(max(ymaxs))
    yrng = (y_max - y_min) if y_max > y_min else 1.0

    # 4) 마지막 y 값 정렬 → 간격 벌려서 겹침 방지
    y_last = _np.array([df2.loc[years_plot, k].iloc[-1] for k in keys], dtype=float)
    order = _np.argsort(-y_last)
    y_des = y_last[order].copy()
    top_cap, bottom_cap = y_max - 0.02*yrng, y_min + 0.02*yrng
    gap = max(min_gap, 0.6/max(1, len(keys))) * yrng

    y_pos = _np.empty_like(y_des)
    y_pos[0] = float(_np.clip(y_des[0], bottom_cap, top_cap))
    for i in range(1, len(y_des)):
        yi = float(_np.clip(y_des[i], bottom_cap, top_cap))
        if y_pos[i-1] - yi < gap:
            yi = y_pos[i-1] - gap
        if yi < bottom_cap:
            shift = bottom_cap - yi
            y_pos[:i] += shift
            yi = bottom_cap
            if _np.any(y_pos[:i] > top_cap):
                start = top_cap - gap * (i)
                y_pos[:i+1] = _np.linspace(start, top_cap, i+1)
                break
        y_pos[i] = yi

    inv = _np.empty_like(order); inv[order] = _np.arange(len(order))
    y_final = y_pos[inv]

    # 5) x축 패딩 + 오른쪽 마진 확장(잘림 방지)
    x0, x1 = years_plot[0], years_plot[-1]
    xpad = (x1 - x0) * xpad_frac
    fig.update_xaxes(range=[x0, x1 + xpad])
    # margin.r만 증설(기존 l/t/b는 유지)
    fig.update_layout(margin=dict(r=max(getattr(fig.layout.margin, "r", 0), right_margin)))
    x_label = x1 + xpad*0.55

    # 6) 연결선 + 주석
    for i, k in enumerate(keys):
        yk_end = float(y_last[i]); yf = float(y_final[i])
        fig.add_shape(type="line",
                      x0=x1, y0=yk_end, x1=x1 + xpad*0.45, y1=yf,
                      line=dict(color="rgba(128,128,128,0.85)", width=1))
        fig.add_annotation(x=x_label, y=yf, text=k, showarrow=False,
                           xanchor="left", yanchor="middle",
                           bgcolor="rgba(255,255,255,0.82)",
                           bordercolor="rgba(0,0,0,0)", borderpad=2,
                           font=dict(size=12, color=ui['text']))
    return fig



if all_years:
    # 풀 후보
    all_tokens = sorted({k for y in all_years for k in kw_doc[y].keys()})
    need_k = max(TOP_K_PER_FIG*2, 16)
    pool_tokens = ensure_topk(all_tokens, need_k, docs_per_year, kw_doc, all_years)
    share_all, lift_all = build_share_lift(pool_tokens, all_years, kw_doc, docs_per_year)

    win_years = all_years[-min(WINDOW_YEARS, len(all_years)):]
    share_win  = share_all.loc[win_years]
    lift_win   = lift_all.loc[win_years]

    latest_share = share_win.iloc[-1]
    delta_share  = (share_win.iloc[-1] - share_win.iloc[0])  # p.p. 변화
    last_lift    = lift_win.iloc[-1]
    cagr_lift    = pd.Series({k: cagr(lift_win[k].values) for k in lift_win.columns})

    # 점수(정렬용) — 2-of-3 규칙과 조화되도록 구성
    rise_score = (last_lift - 1.0) + 0.7*(cagr_lift/100.0) + 0.5*(delta_share/100.0)
    fall_score = (1.0 - last_lift) + 0.7*((-cagr_lift)/100.0) + 0.5*((-delta_share)/100.0)

    # 2-of-3 규칙으로 상/하락 후보 분리
    sig_up   = ((last_lift >= 1.0).astype(int) + (cagr_lift > 0).astype(int) + (delta_share > 0).astype(int))
    sig_down = ((last_lift < 1.0).astype(int)  + (cagr_lift < 0).astype(int) + (delta_share < 0).astype(int))

    rise_order = [k for k in rise_score.sort_values(ascending=False).index if sig_up[k]   >= 2]
    fall_order = [k for k in fall_score.sort_values(ascending=False).index if sig_down[k] >= 2]

    used=set(); rise_sel=[]; fall_sel=[]
    for k in rise_order:
        if k not in used: rise_sel.append(k); used.add(k)
    for k in fall_order:
        if k not in used: fall_sel.append(k); used.add(k)

    # 부족 시 최근성 기준 보충 (중복 금지)
    def backfill(sel, need, base_rank, predicate):
        if len(sel) >= need: return sel
        recent = win_years[-min(RECENT_YEARS, len(win_years)):]
        hits_recent  = Counter(); years_recent = Counter()
        for y in recent:
            hits_recent.update(kw_doc[y])
            for k,c in kw_doc[y].items():
                if c>0: years_recent[k]+=1
        var_proxy = {k: np.var([kw_doc[y][k]>0 for y in win_years]) for k in base_rank}
        rank = sorted(base_rank, key=lambda k: (hits_recent[k], years_recent[k], var_proxy.get(k,0.0)), reverse=True)
        for k in rank:
            if len(sel) >= need: break
            if k in used: continue
            if predicate(k): sel.append(k); used.add(k)
        if len(sel) < need:
            for k in base_rank:
                if len(sel) >= need: break
                if k in used: continue
                sel.append(k); used.add(k)
        return sel

    rise_sel = backfill(rise_sel, TOP_K_PER_FIG, list(rise_score.sort_values(ascending=False).index),
                        lambda k: (last_lift[k] >= 1.0) or (cagr_lift[k] > 0) or (delta_share[k] > 0))
    fall_sel = backfill(fall_sel, TOP_K_PER_FIG, list(fall_score.sort_values(ascending=False).index),
                        lambda k: (last_lift[k] < 1.0) or (cagr_lift[k] < 0) or (delta_share[k] < 0))

    rise_sel = rise_sel[:TOP_K_PER_FIG]
    fall_sel = fall_sel[:TOP_K_PER_FIG]

    # === 여기까지 rise_sel, fall_sel 목록이 만들어진 상태 ===

    # ① 원하는 목표 개수(양쪽 동일) — TOP_K_PER_FIG 사용
    TARGET = min(TOP_K_PER_FIG, len(rise_sel), len(fall_sel))
    
    # ② 부족하면 랭킹으로 보충
    #    (상승/하락 각각의 정렬 기준 이미 계산되어 있다고 가정: rise_score, fall_score)
    rise_rank = list(rise_score.sort_values(ascending=False).index)
    fall_rank = list(fall_score.sort_values(ascending=False).index)
    used = set(rise_sel) | set(fall_sel)
    
    def fill_to(target, base_list, rank_pool):
        out = list(base_list)
        for k in rank_pool:
            if len(out) >= target: break
            if k in used: continue
            out.append(k); used.add(k)
        return out[:target]
    
    rise_sel = fill_to(TARGET, rise_sel, rise_rank)
    fall_sel = fill_to(TARGET, fall_sel, fall_rank)
    
    # ③ 혹시 둘 다 너무 적을 때(데이터 희박), 두쪽의 실제 가능한 최소치로 재조정
    TARGET = min(len(rise_sel), len(fall_sel))
    rise_sel = rise_sel[:TARGET]
    fall_sel = fall_sel[:TARGET]


    years_plot = win_years[-min(RECENT_YEARS*2, len(win_years)):]  # 최근 10년 내에서 10~?년 슬라이스

    fig_up   = plot_trend_plotly(rise_sel, years_plot, lift_all, f"상승세 — 최근 {len(years_plot)}년")
    fig_up   = style_fig(fig_up, bg_color=VIZ_BG["trend_up"], bg_alpha=0.5)
    fig_up   = add_line_end_labels(fig_up, years_plot, lift_all, rise_sel)
    fig_down = plot_trend_plotly(fall_sel, years_plot, lift_all, f"하락세 — 최근 {len(years_plot)}년")
    fig_down = style_fig(fig_down, bg_color=VIZ_BG["trend_down"], bg_alpha=0.5)
    fig_down = add_line_end_labels(fig_down, years_plot, lift_all, fall_sel)

    u, v = st.columns([1,1], gap="large")
    # 트렌드 차트는 범례를 상단으로 이동 (블록 내부에 유지)
    with u:
        fig_up.update_layout(legend=dict(orientation="h", y=1.10, yanchor="bottom", x=0, xanchor="left"))
        fig_up = add_line_end_labels(fig_up, years_plot, lift_all, rise_sel)
        fig_up = force_legend_top_padding(fig_up, base_top=130)  # ★ 추가(보수적)
        st.plotly_chart(fig_up, use_container_width=True, config={"displayModeBar": False})
    with v:
        fig_down.update_layout(legend=dict(orientation="h", y=1.10, yanchor="bottom", x=0, xanchor="left"))
        fig_down = add_line_end_labels(fig_down, years_plot, lift_all, fall_sel)
        fig_down = force_legend_top_padding(fig_down, base_top=130)  # ★ 추가
        st.plotly_chart(fig_down, use_container_width=True, config={"displayModeBar": False})
else:
    st.info("사업 기간에서 연도를 추출할 수 없어 키워드 상대 트렌드를 건너뜁니다.")

# ===================== 키워드 트렌드 — 완전 수동(검색 없음) =====================
st.markdown("---")
st.subheader("키워드 트렌드 — 직접 선택 (검색 없음 · 국가/AI 키워드 제외)")
# 사이드바 어딘가에:
if st.sidebar.button("캐시 초기화", use_container_width=True):
    # 캐시 비우기
    st.cache_data.clear()
    st.cache_resource.clear()
    # 리런 (버전 호환)
    try:
        st.rerun()                 # Streamlit >= 1.27+
    except Exception:
        try:
            st.experimental_rerun()  # 구버전 백업
        except Exception:
            pass  # 최후의 보루: 리런 실패해도 앱은 계속 동작
            
with st.sidebar.expander("환경 점검", expanded=False):
    import sys, importlib.util
    st.write("Python:", sys.version)
    for m in ["streamlit_folium", "folium", "wordcloud", "plotly", "kiwipiepy", "sentence_transformers", "keybert"]:
        st.write(f"{m}: ", importlib.util.find_spec(m) is not None)



# ====================== 사용자 불용어 (코드에서 직접 편집) ======================
# ====================== 사용자 불용어 ======================
# ==== 0) 사용자 불용어 (여기만 수정) ====
STOP_CUSTOM = {"높여", "기관별", "지속가능한", "공무원의", "있음", "사용자", "경제", "중소기업의", "조달", "공공", "개혁을", "기업들의", "라오스의", "분석",
               "전략을", "제도의", "체계적으로", "통계", "표준화", "것이다", "베트남의", "과테말라의", "메콩강", "시스템을", "이집트의", "통합", "필리핀의", 
               "산업", "혁신", "가나의", "전환", "집행", "파라과이의", "검색", "규제", "기술", "생태계를", "처리", "협력", "등록", "납세자"}
STOP_SET = {w.strip().upper() for w in STOP_CUSTOM if w.strip()}

# ==== 1) 헬퍼 ====
import re
from collections import Counter

def _norm_token(x: str) -> str:
    x = re.sub(r'[\"\'’“”()\[\]{}<>]', "", str(x).strip())
    return x.upper()  # 대문자 기준으로 통일

def _is_numericish(s: str) -> bool:
    return bool(re.fullmatch(r"\d+(\.\d+)?", s))

# ==== 2) 해시태그 빈도 수집 ====
HASHTAG_COL = "Hashtag" if "Hashtag" in df.columns else ("Hashtag_str" if "Hashtag_str" in df.columns else None)

def collect_hashtag_freq(df_in) -> Counter:
    freq = Counter()
    if not HASHTAG_COL or HASHTAG_COL not in df_in.columns or df_in[HASHTAG_COL].isna().all():
        return freq
    for raw in df_in[HASHTAG_COL].dropna().astype(str):
        for t in re.split(r"[,\;/]| {2,}", raw):
            t = _norm_token(t)
            if not t or len(t) < 2:
                continue
            if t in STOP_SET or _is_numericish(t):
                continue
            freq[t] += 1
    return freq

# ==== 3) 제외세트 (국가/AI 키워드) ====
COUNTRY_WORDS = set()
if "COUNTRY_MAP" in globals():
    for k, (iso, en, ko) in COUNTRY_MAP.items():
        COUNTRY_WORDS |= {str(k).upper(), str(iso).upper(), str(en).upper(), str(ko).upper()}

AI_SET = set()
if "rise_sel" in globals() and rise_sel is not None:
    AI_SET |= {str(t).upper() for t in rise_sel}
if "fall_sel" in globals() and fall_sel is not None:
    AI_SET |= {str(t).upper() for t in fall_sel}

def is_excluded(tok: str) -> bool:
    t = tok.upper().strip()
    return (t in COUNTRY_WORDS) or (t in AI_SET) or (t in STOP_SET) or _is_numericish(t)

# ==== 4) 여기서 freq_all을 '먼저' 만든 다음 후보 생성 ====
freq_all = collect_hashtag_freq(df)          # ← 반드시 먼저!
candidates_all = [(k, c) for k, c in freq_all.items() if not is_excluded(k)]

# 후보가 너무 적으면(예: 불용어가 많을 때) 완화
if len(candidates_all) < 25 and HASHTAG_COL:
    tmp = Counter()
    for raw in df[HASHTAG_COL].dropna().astype(str):
        for t in re.split(r"[,\;/]| {2,}", raw):
            t = _norm_token(t)
            if t and (t not in COUNTRY_WORDS) and (t not in AI_SET) and (t not in STOP_SET) and (not _is_numericish(t)):
                tmp[t] += 1
    for k, v in tmp.items():
        freq_all[k] = max(freq_all.get(k, 0), v)
    candidates_all = [(k, c) for k, c in freq_all.items()
                      if (k not in COUNTRY_WORDS) and (k not in AI_SET) and (k not in STOP_SET) and (not _is_numericish(k))]

# 정렬/라벨
candidates_all = sorted(candidates_all, key=lambda x: (-x[1], x[0]))[:300]
cand_labels = [k for k, _ in candidates_all]


# --- 3) 체크박스 그리드 UI(검색 없음) ---
def checkbox_multi(label: str, options: list[str], max_select: int = 30, cols: int = 4) -> list[str]:
    st.caption("원하는 키워드를 체크하세요. (2–30개)")
    picks = []
    grids = [options[i::cols] for i in range(cols)]
    cols_obj = st.columns(cols, gap="large")
    for col, opts in zip(cols_obj, grids):
        with col:
            for o in opts:
                key = f"kw_pick_{label}_{o}"
                if st.checkbox(o, key=key, value=False):
                    picks.append(o)
    if len(picks) > max_select:
        st.warning(f"{max_select}개까지만 사용할 수 있어요. 현재 {len(picks)}개 선택됨 → 앞에서 {max_select}개만 사용합니다.")
        picks = picks[:max_select]
    return picks

chosen = checkbox_multi("kw", cand_labels, max_select=30, cols=4)

if len(chosen) < 2:
    st.info("키워드를 최소 2개 이상 선택하면 아래에 추세 그래프가 표시됩니다.")
    st.stop()

# --- 4) 연도 집계(!!! 여기 핵심: '사업 기간' 직접 참조 금지) ---
years_series = _year_text_series(df)                 # <-- 이걸로 연도 소스 자동/지정
years_list   = years_series.apply(years_from_span)
all_years    = sorted({y for ys in years_list for y in (ys or [])})
if not all_years:
    st.warning("연도를 추출할 수 없어서 추세를 그릴 수 없어요.")
    st.stop()

docs_per_year = pd.Series(0, index=all_years, dtype=int)
for ys in years_list:
    for y in (ys or []): docs_per_year[y] += 1

# 키워드 등장수(연도별, '선택된 것'만 계산)
kw_doc = {y: Counter() for y in all_years}
if HASHTAG_COL:
    for (_, row), ys in zip(df.iterrows(), years_list):
        if not ys: 
            continue
        toks = []
        for t in re.split(r"[,\;/]| {2,}", str(row.get(HASHTAG_COL, ""))):
            t = _norm_token(t.strip())
            if t and t in chosen:
                toks.append(t)
        if not toks:
            continue
        for y in ys:
            kw_doc[y].update(set(toks))

# share & lift
share = pd.DataFrame({
    k: jeffreys_rolling_ratio(
        pd.Series({y: kw_doc[y][k] for y in all_years}, dtype=float),
        docs_per_year.astype(float))
    for k in chosen
}, index=all_years).fillna(0.0)

w = docs_per_year / docs_per_year.sum()
base = (share.mul(w, axis=0)).sum(axis=0).replace(0, np.nan)
lift = share.div(base, axis=1).replace([np.inf, -np.inf], np.nan).fillna(0.0)

# 최근 10년만
years_plot = all_years[-min(10, len(all_years)):]
fig = go.Figure()
for k in chosen:
    ys = [float(lift.loc[y, k]) if (y in lift.index and k in lift.columns) else np.nan for y in years_plot]
    if np.all(np.isnan(ys)):   # 완전 미등장 방지
        continue
    fig.add_trace(go.Scatter(x=years_plot, y=ys, mode="lines+markers", name=k,
                             line=dict(width=3), marker=dict(size=8), connectgaps=True))
fig.add_hline(y=1.0, line_width=1.5, line_dash="dash", opacity=0.6)
fig.update_xaxes(title_text="연도")
fig.update_yaxes(title_text="lift (배)")
fig = style_fig(fig, "선택 키워드 추세 — 최근 10년", legend="top", top_margin=130,
                bg_color=VIZ_BG["trend_up"], bg_alpha=0.35)
fig = add_line_end_labels(fig, years_plot, lift, [k for k in chosen if k in lift.columns])
fig = force_legend_top_padding(fig, base_top=130)
st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})




# --------------------- 설치 / 실행 ---------------------
with st.expander("설치 / 실행"):
    st.code("pip install streamlit folium streamlit-folium pandas wordcloud plotly matplotlib", language="bash")
    st.code("streamlit run S_KSP_clickpro_v4_plotly_patch_FIXED.py", language="bash")






















































































































































































































































































