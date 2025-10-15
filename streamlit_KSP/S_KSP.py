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
import os, io, re, json, urllib.request, hashlib, pathlib, copy
from typing import List, Dict, Tuple
from collections import Counter, defaultdict, OrderedDict
import urllib.request
from pathlib import Path
import numpy as np
import pandas as pd
from PIL import Image
from PIL import ImageFont
import streamlit as st
import folium
from streamlit_folium import st_folium
from wordcloud import WordCloud
import plotly.express as px
import plotly.graph_objects as go
from matplotlib import font_manager, rcParams

#######################################################
# --------------------- Changyeon ---------------------
# import pdfplumber
# import zipfile
# import streamlit.components.v1 as components
# import json
# from sklearn.feature_extraction.text import TfidfVectorizer
# import tempfile
#######################################################

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
    "경제에서", "경제로", "전환하고자", "그러나" ,"부문은", "부족으로", "잠재력을", "충분히", "활용하지", "못하고", "호주는", "호주의", "분야에서", "인도네시아는", "문제점을", "효율성을"
}
STOP_LOW = {w.lower() for w in STOP}
#######################################################
# --------------------- Changyeon ---------------------
# st.sidebar.header("1. LLM 입력용 ZIP 폴더 생성")
# def extract_smooth_text_from_pdf(pdf_path: str) -> str:
#     """
#     PDF에서 텍스트 추출 후 문장 단위로 이어붙임
#     """
#     full_text = ""
#     with pdfplumber.open(pdf_path) as pdf:
#         for page in pdf.pages:
#             page_text = page.extract_text() or ""
#             page_text = page_text.strip()
#             if not page_text:
#                 continue

#             if re.search(r'[.?!\'"]$', page_text.strip()):
#                 full_text += page_text + "\n"
#             else:
#                 full_text += page_text + " "
#     return full_text.strip()

# # 사이드바에서 ZIP 파일 업로드
# uploaded_zip = st.sidebar.file_uploader("📂 PDF 폴더(ZIP) 업로드", type="zip")

# if uploaded_zip is not None:
#     results = []
#     txt_files = []

#     # 업로드한 ZIP을 임시 폴더에 풀기
#     with tempfile.TemporaryDirectory() as tmpdir:
#         with zipfile.ZipFile(uploaded_zip, "r") as zip_ref:
#             zip_ref.extractall(tmpdir)

#         # 변환된 TXT들을 담을 ZIP 버퍼
#         zip_buffer = io.BytesIO()
#         with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as out_zip:
#             for filename in os.listdir(tmpdir):
#                 if not filename.lower().endswith(".pdf"):
#                     continue

#                 pdf_path = os.path.join(tmpdir, filename)
#                 txt_filename = os.path.splitext(filename)[0] + ".txt"

#                 try:
#                     text = extract_smooth_text_from_pdf(pdf_path)
#                     if len(text) < 100:
#                         results.append(f"⚠️ 텍스트 부족 → 건너뜀: {filename}")
#                         continue

#                     # 변환된 텍스트를 ZIP에 직접 저장
#                     out_zip.writestr(txt_filename, text)
#                     txt_files.append(txt_filename)
#                     results.append(f"✓ 저장 완료: {filename}")
#                 except Exception as e:
#                     results.append(f"⚠️ 오류 발생: {filename} → {e}")

#         # ZIP 다운로드 버튼
#         zip_buffer.seek(0)
#         st.write("### 처리 결과")
#         st.text("\n".join(results))

#         if txt_files:
#             st.download_button(
#                 label="📥 변환된 TXT ZIP 다운로드",
#                 data=zip_buffer,
#                 file_name="PDF2TXT_Result.zip",
#                 mime="application/zip"
#             )
# else:
#     st.info("👈 사이드바에서 ZIP 파일을 업로드하세요.")

# st.sidebar.header("2. LLM 입력용 프롬프트 복사")
# text = """
# 네 역할은 Tabulation machine이야.
# zip 폴더의 압축을 해제한 뒤 정보를 추출해서 table을 만들 거야.
# table의 열은 ['파일명', '대상국', '대상기관', '주요 분야', '연도, '지원기관', '주요 내용', '기대 효과', '요약', 'WB_Class']로 구성해.
# 파일명은 zip 폴더 내 확장자 및 영문, 국문 표기를 제외한 파일명을 입력해.
# 대상국, 대상기관, 주요 분야, 지원기관은 파일 내용으로부터 추출해. 이들은 한국어 label 형태로 입력해.
# 연도은 연도와 대시를 사용해서 나타내.
# 주요 내용, 기대 효과, 요약은 각각 5문장 이상, 10문장 이하의 문장으로 입력해.
# 주요 내용은 현황과 이슈, 문제점, 제안 및 제언을 위주로 작성해.
# 기대효과는 정성적 및 정량적 성과, 전망, 기대효과 중심으로 작성해.
# 요약은 네 판단 하에 다룰 만한 부분을 종합적으로 작성해.
# ICT 유형는 https://data360.worldbank.org/en/digital의 Topic을 label로 사용할 거야.
# 'Connectivity', 'Data Infrastructure', 'Cybersecurity', 'Digital Industry and Jobs', 'Digital Services' 중에 선택해.
# 보고서 성격에 따라 아래 사전을 참고하여 label을 할당해.
# {Connectivity: [Telecom Networks, Telecom Subscriptions, Digital Adoption, Telecom Markets and Competition, Affordability, Telecom Regulation],
# Data Infrastructure: [Data Centers, Internet Exchange Points (IXPs)],
# Cybersecurity: [ITU Global Cybersecurity Index (GCI)],
# Digital Industry and Jobs: [ICT Industry , Digital Skills],
# Digital Services: [Digital Public Infrastructure - DPI, E-Government]}
# """
# st.sidebar.code(text, language="text")
# st.sidebar.link_button("🌐 LLM 접속", "https://chatgpt.com/c")

# st.sidebar.header("3. Hashtag 추출 및 문장 결합")
# def make_tags(row):  # 1
#     tags = []
#     text = f"{row['파일명']} {row['대상기관']} {row['지원기관']}"
    
#     if 'KDI' in text:
#         tags += ['경제', '사회정책']
#     if '한국수출입은행' in text:
#         tags += ['건설', '인프라']
#     if 'KOTRA' in text:
#         tags += ['산업', '무역', '투자']
        
#     return list(dict.fromkeys(tags))

# def del_word(row, column, word):  # 2
#     text = f"{row[column]}"
#     if pd.isna(text):
#         return None
    
#     parts = [p.strip() for p in str(text).split(',')]
#     result_parts = []

#     for p in parts:
#         if not p:
#             continue
#         if word not in p:
#             result_parts.append(p)
#         else:
#             match = re.search(r'\(([^)]*)\)', p)
#             if match:
#                 result_parts.append(match.group(1).strip())

#     return ', '.join(result_parts) if result_parts else None

# def top_tfidf_terms(row_tfidf, terms, k=3):
#     sorted_indices = row_tfidf.toarray().ravel().argsort()[::-1]
#     top_idxs = sorted_indices[:k]
#     return [terms[i] for i in top_idxs if row_tfidf[0, i] > 0]

# uploaded_file = st.sidebar.file_uploader("📂 엑셀 파일 업로드", type=["xlsx"])

# if uploaded_file:
#     df_c = pd.read_excel(uploaded_file)

#     # 기존 열은 그대로 두고 새로운 열 추가
#     df_c['Hashtag'] = df_c.apply(make_tags, axis=1)
#     df_c['지원기관'] = df_c.apply(lambda r: del_word(r, '지원기관', 'KSP'), axis=1)
#     df_c[['지원기관']] = df_c[['지원기관']].fillna('-')

#     target_cols = ['대상기관', '지원기관']
#     df_c[target_cols] = df_c[target_cols].fillna('')
#     for col in target_cols:
#         df_c[col] = df_c[col].str.replace(r'\s*등$', '', regex=True)

#     df_c['full_text'] = (
#         df_c[['주요 내용','기대 효과','요약']]
#         .fillna('')
#         .agg(' '.join, axis=1)
#     )

#     # TF–IDF
#     korean_stopwords = [
#         '의','가','이','은','들','는','을','를','에','와','과','도','으로','에서',
#         '하다','한다','있다','없다','좋다','같다','되다','수','을','기','등']
#     tfidf = TfidfVectorizer(max_df=0.8, min_df=2,
#                             stop_words=korean_stopwords,
#                             ngram_range=(1,1), max_features=2000)
#     X_tfidf = tfidf.fit_transform(df_c['full_text'])
#     terms = tfidf.get_feature_names_out()

#     # 기존 Hashtag + TF-IDF 키워드 합치기
#     new_tags = []
#     for i, vec in enumerate(X_tfidf):
#         kws = top_tfidf_terms(vec, terms, k=2)
#         existing = df_c.at[i, 'Hashtag']
#         if isinstance(existing, str):
#             exist_list = [t.strip() for t in existing.split(',') if t.strip()]
#         elif isinstance(existing, list):
#             exist_list = existing.copy()
#         else:
#             exist_list = []
#         for w in kws:
#             if w not in exist_list:
#                 exist_list.append(w)
#         new_tags.append(exist_list)

#     df_c['Hashtag'] = new_tags
#     df_c['Hashtag_str'] = df_c['Hashtag'].apply(lambda lst: ', '.join(lst) if lst else None)

#     # 결과 미리보기
#     st.subheader("🔎 Hashtag 추출 결과 (상위 10행)")
#     st.dataframe(df_c.head(10))

#     # 다운로드
#     output = io.BytesIO()
#     with pd.ExcelWriter(output, engine="openpyxl") as writer:
#         df_c.to_excel(writer, index=False, sheet_name="Result")
#     output.seek(0)

#     st.download_button(
#         "📥 결과 엑셀 다운로드",
#         data=output,
#         file_name="Hashtag_Result.xlsx",
#         mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
#     )

# else:
#     st.info("👈 사이드바에서 엑셀 파일을 업로드하세요.")
#######################################################

# --------------------- 데이터 입력 ---------------------
st.sidebar.header("데이터 입력")

# 기본값(있어도 되고 없어도 됨 — 자동 탐지 시 무시됨)
DEFAULT_DATA_PATH = r"df1_20250901_145328.xlsx"

# 스크립트 기준 디렉토리(노트북/REPL 대비 fallback)
DATA_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()
SEARCH_DIRS = [DATA_DIR, DATA_DIR / "data", DATA_DIR / "assets"]




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
    cands = sorted(cands, key=lambda p: (
        # 같은 로직을 양수로 재작성
        -(8 if "df1" in p.name.lower() else 0)
        -(6 if "ksp" in p.name.lower() else 0)
        -(5 if "state_of_the_table" in p.name.lower() else 0)
        -(2 if ("export" in p.name.lower() or "table" in p.name.lower()) else 0),
        -p.stat().st_mtime
    ))
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
    else:
        st.sidebar.info("같은 폴더(또는 ./data, ./assets)에서 적합한 데이터 파일을 찾지 못했습니다. 다른 소스 방식을 사용하세요.")

elif src_mode == "파일 업로드":
    up = st.sidebar.file_uploader("엑셀(.xlsx/.xls) 또는 CSV 업로드", type=["xlsx", "xls", "csv"])
    if up is not None:
        df = load_from_uploader(up)

elif src_mode == "CSV 붙여넣기":
    pasted = st.sidebar.text_area("CSV 원문 붙여넣기(헤더 포함)", height=160)
    if pasted.strip():
        df = load_from_csv_text(pasted)

else:  # 파일 경로
    # 자동 후보가 있으면 기본값을 그 중 첫 번째로 노출(없으면 DEFAULT 사용)
    default_path = str(auto_files[0]) if auto_files else DEFAULT_DATA_PATH
    data_path = st.sidebar.text_input("엑셀/CSV 경로", default_path)
    if os.path.exists(data_path):
        df = load_from_path(data_path)
        st.sidebar.caption(f"경로: `{Path(data_path).resolve()}`")

# 데이터 없으면 중단
if df is None or df.empty:
    st.stop()

# 필수 컬럼 진단
REQ = ["파일명","대상국","대상기관","주요 분야","지원기관","연도","주요 내용","기대 효과",
       "요약","ICT 유형","주제분류(대)","Hashtag","Hashtag_str","full_text"]
missing = [c for c in REQ if c not in df.columns]
if missing:
    st.warning(f"필수 컬럼 누락: {missing}")

with st.expander("데이터 미리보기 / 진단", expanded=False):
    st.write(f"행 수: {len(df):,}  |  고유 대상국: {df['대상국'].nunique()}  |  고유 ICT 유형: {df['ICT 유형'].nunique()}")
    st.dataframe(df.head(25), use_container_width=True)
# --------------------- 데이터 입력 (끝) ---------------------


def _font_path_safe():
    return GLOBAL_FONT_PATH or find_korean_font()  # 둘 다 없으면 None



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
@st.cache_data(show_spinner=False)
def expand_years(df_in: pd.DataFrame) -> pd.DataFrame:
    def years_from_text(txt: str):
        if pd.isna(txt): return []
        raw = str(txt)
        yrs = [int(y) for y in re.findall(r"(?:19|20)\d{2}", raw)]
        yrs = [y for y in yrs if 1990 <= y <= 2035]
        if not yrs: return []
        if len(yrs) == 1: return yrs
        a, b = min(yrs), max(yrs)
        if b - a > 30: b = a
        return list(range(a, b+1))
    dfy = df_in.copy()
    dfy["연도목록"] = dfy["연도"].apply(years_from_text)
    dfy = dfy.explode("연도목록")
    dfy = dfy.rename(columns={"연도목록":"연도"})
    dfy["연도"] = pd.to_numeric(dfy["연도"], errors="coerce").astype("Int64")
    return dfy

dfy = expand_years(df)     # 키워드/주제 상대 트렌드는 '국가 중복 없는' 원본 df 기준

# --------------------- 보기 모드 ---------------------
st.sidebar.header("보기 모드")
mode = st.sidebar.radio("지도 유형", ["국가별 총계", "ICT 유형 단일클래스"], index=0)

# 연도 시각화 옵션 (히트맵 제거)
st.sidebar.header("연도 시각화 방식")
YEAR_OPTIONS = ["100% 누적 막대", "순위 Bump"]
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
                cols_show = ["파일명","지원기관","연도","주제분류(대)", "ICT 유형","주요 내용","기대 효과","Hashtag_str"]
                st.dataframe(sub[cols_show].drop_duplicates().reset_index(drop=True), use_container_width=True)
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

    tab_overview, tab_brief, tab_cloud, tab_table = st.tabs(
        ["개요", f"{sel} 종합요약", "워드클라우드 / 키워드", "테이블"]
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

    # ---- (4) 테이블: 클래스 전체 보고서 목록 ----
    with tab_table:
        st.markdown("#### 프로젝트 목록 (클래스 전체)")
        cols_show = ["파일명","지원기관","연도","주제분류(대)","ICT 유형","대상국","대상기관","주요 내용","기대 효과","Hashtag_str"]
        st.dataframe(sub_wb[cols_show].drop_duplicates().reset_index(drop=True), use_container_width=True)




# --------------------- 전체 분포 대시보드 ---------------------
st.markdown("---")
st.subheader("전체 분포 대시보드")

# (1) 주제분류(대) 도넛
subj_counts = df["주제분류(대)"].fillna("미분류").value_counts().reset_index()
subj_counts.columns = ["주제분류(대)","count"]
fig1 = px.pie(subj_counts, names="주제분류(대)", values="count", hole=0.55)
# 도넛
fig1 = style_fig(fig1, "주제분류(대) 분포", legend="right", top_margin=120,
                 bg_color=VIZ_BG["donut_subj"], bg_alpha=0.5)
# (2) ICT 유형 도넛
wb_counts = (df["ICT 유형"].astype(str).str.strip().replace({"nan":"미분류"})
             .fillna("미분류").value_counts().reset_index())
wb_counts.columns = ["ICT 유형","count"]
fig2 = px.pie(wb_counts, names="ICT 유형", values="count", hole=0.55)
fig2 = style_fig(fig2, "ICT 유형 분포", legend="right", top_margin=120,
                 bg_color=VIZ_BG["donut_wb"], bg_alpha=0.5)

c0, c00 = st.columns([1,1], gap="large")
with c0: st.plotly_chart(fig1, use_container_width=True)
with c00: st.plotly_chart(fig2, use_container_width=True)

# (3) 주제×WB 100% 누적 막대
cross = (df.assign(WB=df["ICT 유형"].astype(str).str.strip().replace({"nan":"미분류"}).fillna("미분류"))
           .groupby(["주제분류(대)","WB"], as_index=False).size())
pivot = cross.pivot(index="주제분류(대)", columns="WB", values="size").fillna(0)
pivot_pct = pivot.div(pivot.sum(axis=1).replace(0, np.nan), axis=0).fillna(0).reset_index().melt(
    id_vars="주제분류(대)", var_name="WB", value_name="pct")
fig3 = px.bar(pivot_pct, x="주제분류(대)", y="pct", color="WB", barmode="stack")
fig3.update_yaxes(range=[0,1], tickformat=".0%")
fig3.update_layout(bargap=0.68, bargroupgap=0.08)   # 값↑ = 간격↑ = 막대 슬림


# 100% 누적 막대
st.plotly_chart(style_fig(fig3, "주제분류(대)별 ICT 유형 비중 (100%)",
                          legend="right", top_margin=120,
                          bg_color=VIZ_BG["stack_100"], bg_alpha=0.5),
                use_container_width=True)

# ---------- (4)(5) 연도별 비중 — 선택형 시각화 (히트맵 제거) ----------
dfy_valid = dfy.dropna(subset=["연도"]).copy()

def time_share(df_in, group_col):
    g = df_in.groupby(["연도", group_col], as_index=False).size()
    totals = g.groupby("연도")["size"].transform("sum")
    g["pct"] = g["size"] / totals
    return g

def draw_year_chart(g, group_col, title_prefix):
    if g.empty:
        fig = px.line(); return style_fig(fig, f"{title_prefix} (연도 추출 불가)")

    if year_mode == "순위 Bump":
        ranks = g.copy()
        ranks["rank"] = ranks.groupby("연도")["pct"].rank(ascending=False, method="dense")
        fig = px.line(ranks, x="연도", y="rank", color=group_col, markers=True)
        fig.update_traces(line=dict(width=3), marker=dict(size=8))
        fig.update_yaxes(autorange="reversed", dtick=1, title="순위(1=최상)")
        return style_fig(fig, f"{title_prefix} — 순위 Bump", legend="top", top_margin=120)
    else:  # 100% 누적 막대
        # fig = px.bar(g, x="연도", y="pct", color=group_col, barmode="stack", labels={"pct":"비중"})
        # fig.update_yaxes(range=[0,1], tickformat=".0%")
        # return style_fig(fig, f"{title_prefix} — 100% 누적 막대", legend="top", top_margin=120)
        
        fig = px.line(g, x="연도", y="pct", color=group_col, labels={"pct": "비중"}, markers=True)  # 각 점을 동그라미로 표시
        fig.update_yaxes(range=[0, 1], tickformat=".0%")
        fig.update_layout(title="비율 추세 (라인 플롯)", legend=dict(orientation="h", y=1.1))
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

YEAR_RE = re.compile(r"(?<!\d)(?:19|20)\d{2}(?!\d)")

def years_from_span(text: str):
    if not isinstance(text, str): return []
    t = text.replace("~","-").replace("–","-").replace("—","-")
    t = re.sub(r"[()]", " ", t)
    ys = [int(y) for y in YEAR_RE.findall(t)]
    return list(range(min(ys), max(ys)+1)) if ys else []

SYN = {"sme":"SME","pki":"PKI","ai":"AI","ict":"ICT","bigdata":"빅데이터","big data":"빅데이터",
       "e-gp":"전자조달","egp":"전자조달","e-procurement":"전자조달","data center":"데이터센터","cloud":"클라우드",
       "platform":"플랫폼","platfrom":"플랫폼","플렛폼":"플랫폼"}

def norm_token(x: str) -> str:
    x = re.sub(r"[\"'’“”()\[\]{}<>]", "", x.strip()); xl = x.lower()
    return SYN.get(xl, x)

def split_hashtags(s, stopset):
    if not isinstance(s,str) or not s.strip(): return []
    raw = re.split(r"[,\;/]| {2,}", s)
    out=[]
    for t in raw:
        t = norm_token(t)
        core = re.sub(r"\s+", "", t.lower())
        if not core or re.fullmatch(r"[\W_]+", core) or re.fullmatch(r"\d+(\.\d+)?", core):
            continue
        if len(core) < 2: continue
        if core in stopset: continue
        out.append(t)
    return sorted(set(out), key=str.lower)

def jeffreys_rolling_ratio(num, den, k=ROLL, alpha=ALPHA):
    numr = (num + alpha).rolling(k, center=True, min_periods=1).sum()
    denr = (den + 2*alpha).rolling(k, center=True, min_periods=1).sum()
    return (numr/denr*100.0).fillna(0.0)

@st.cache_data(show_spinner=False)
def build_keyword_time(df_in: pd.DataFrame, stop_extra: set):
    df_local = df_in.copy()
    if HASHTAG_COL:
        df_local[HASHTAG_COL] = clean(df_local[HASHTAG_COL])
    years_list = df_local["연도"].apply(years_from_span)
    all_years  = sorted({y for ys in years_list for y in (ys or [])})
    if not all_years: return [], {}, pd.Series([], dtype=int), pd.DataFrame()

    # 동적 불용어(대분류/클래스/국가 등)
    dyn = set()
    for col in ["주제분류(대)","ICT 유형","대상국","대상기관","지원기관"]:
        if col in df_local.columns: dyn |= set(map(str.lower, df_local[col].astype(str).unique()))
    stopset = {w.lower() for w in stop_extra} | dyn

    tokens_by_row = [split_hashtags(s, stopset) for s in (df_local[HASHTAG_COL] if HASHTAG_COL else pd.Series([""]*len(df_local)))]

    docs_per_year = pd.Series(0, index=all_years, dtype=int)
    for ys in years_list:
        for y in (ys or []): docs_per_year[y] += 1

    kw_doc = {y: Counter() for y in all_years}
    for i, ys in enumerate(years_list):
        toks = set(tokens_by_row[i])
        if not ys or not toks: continue
        for y in ys:
            kw_doc[y].update(toks)
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
    st.info("연도에서 연도를 추출할 수 없어 키워드 상대 트렌드를 건너뜁니다.")

# =====================================================================
# 추가 시각화 ②: 대표 '주제(키워드)' 상대 트렌드(상승/하락) — Plotly
# =====================================================================
st.markdown("---")
st.subheader("분석 기반 키워드 상대 트렌드 (상승/하락)")

THEMES = OrderedDict([
    (r"(전자\s*조달|e[\s\-]*procure(?:ment)?|e[\s\-]*gp\b|joneps|koneps|prozorro)", "전자조달·e-Procurement"),
    (r"(전자\s*무역|디지털\s*무역|e[\s\-]*trade|electronic\s*trade|전자\s*상거래|e[\s\-]*commerce|trade\s*facilitation)", "전자무역·e-Invoice"),
    (r"(전자\s*세금\s*계산서|전자세금계산서|e[\s\-]*invoice|e\s*invoice|전자\s*인보이스)", "전자무역·e-Invoice"),
    (r"(ifmis|통합\s*재정관리|재정관리\s*정보\s*시스템|government[-\s]*wide\s*fm|span\b)", "재정관리(IFMIS)"),
    (r"(전자\s*서명|디지털\s*인증|pki|공인인증|electronic\s*signature|digital\s*certificat(?:e|ion)|"
     r"certification\s*authority|(?:^|\W)ca(?:$|\W))", "전자서명/PKI"),
    (r"(지식\s*재산|지식재산권|ip\b|inapi|특허|출원\s*심사|출원심사|patent|trademark|상표)", "지식재산·출원심사"),
    (r"(데이터\s*센터|데이터센터|클라우드|cloud|gov\s*cloud|government\s*cloud|데이터\s*거버넌스|"
     r"data\s*governance|데이터\s*플랫폼)", "데이터거버넌스·정부 클라우드"),
    (r"(?:(?:neis|나이스|교육\s*행정\s*정보\s*시스템|학교\s*행정\s*정보\s*시스템|"
     r"(?:^|\W)emis(?:$|\W)|education\s*management\s*information\s*system)"
     r"|(?:e[\s\-]*health|telemedicine|ehr\b|his\b|hmis\b|"
     r"(?:보건|건강|health)\s*(?:ict|정보|시스템|플랫폼))"
     r"|(?:(?:livestock|축산|가축|도축|meat|nmis|traceab\w*|이력\s*추적)\s*"
     r"(?:ict|정보|시스템|플랫폼|추적|관리)))", "NEIS교육보건·축산 ICT"),
    (r"(관광\s*빅데이터|tourism\s*data|모바일\s*데이터\s*관광|tourism\s*analytics|관광\s*분석)", "관광 빅데이터"),
    (r"(교육\s*ict|포용적\s*교육|스마트\s*교실|edtech|디지털\s*교재|스마트\s*교육)", "교육 ICT"),
    (r"(내부\s*감사|내부\s*통제|it\s*통제|internal\s*audit|internal\s*control|bpkp|감사\s*체계|거버넌스\s*개선)", "행정개혁·내부통제"),
    (r"(스마트\s*시티|smart\s*city|hydro(?:met|meteorolog)|hydro[-\s]*met|"
     r"aws\b|automatic\s*weather\s*station|rain\s*gauge|우량(?:계)?|강우|"
     r"수문|수문\s*관측|수위(?:계|관측)?|관측\s*네트워크|iot\s*센서|telemetry|scada)", "스마트시티·수문관측"),
])

def normalize_text(row):
    parts = [str(row.get(c, "")) for c in ["파일명","주요 분야","요약","주요 내용","기대 효과"] if c in row.index]
    t = " ".join(parts).lower()
    t = re.sub(r"[“”\"'`]", "", t); t = re.sub(r"[·∙•‧･・]", " ", t); t = re.sub(r"\s+", " ", t).strip()
    return t

def detect_themes(text: str):
    hits = set()
    for pat, label in THEMES.items():
        if re.search(pat, text, flags=re.I): hits.add(label)
    return list(hits)

if all_years:
    # 테마×연도 count
    theme_year_cnt = defaultdict(int)
    for _, row in df.iterrows():
        themes = detect_themes(normalize_text(row))
        ys = years_from_span(row.get("연도", ""))
        if not themes or not ys: continue
        for y in ys:
            for th in themes:
                theme_year_cnt[(th, y)] += 1
    rows = [(th, y, c) for (th, y), c in theme_year_cnt.items()]
    if rows:
        cnt_df = pd.DataFrame(rows, columns=["theme","year","count"])
        pivot_cnt = cnt_df.pivot_table(index="theme", columns="year", values="count", aggfunc="sum").fillna(0.0)
        pivot_cnt = pivot_cnt.reindex(columns=all_years, fill_value=0.0)
        valid = [th for th in pivot_cnt.index if pivot_cnt.loc[th].sum() >= 4 and (pivot_cnt.loc[th] > 0).sum() >= 3]
        pivot_cnt = pivot_cnt.loc[valid]

        den_year  = pd.Series(docs_per_year, dtype=float) + 2*ALPHA
        share     = pivot_cnt.add(ALPHA, axis=0).div(den_year, axis=1) * 100.0
        share     = share.rolling(5, axis=1, center=True, min_periods=1).mean()

        w = (docs_per_year / docs_per_year.sum()).reindex(all_years)
        base = (share.mul(w.values, axis=1)).sum(axis=1)
        lift = share.div(base, axis=0).replace([np.inf, -np.inf], np.nan).fillna(0.0)

        N_plot = min(10, len(all_years))
        years_plot = all_years[-N_plot:]

        # 최근 기울기
        N_slope = min(5, len(all_years))
        yrs_slope = np.array(all_years[-N_slope:], dtype=float)
        recent_slope = {th: np.polyfit(yrs_slope, lift.loc[th, all_years[-N_slope:]].values.astype(float), 1)[0]
                        for th in lift.index}
        var_lift = lift.var(axis=1, ddof=1).fillna(0.0)
        up_sorted   = sorted([th for th in lift.index if recent_slope[th] > 0],
                             key=lambda k: abs(recent_slope[k])*(1+var_lift[k]), reverse=True)[:8]
        down_sorted = sorted([th for th in lift.index if recent_slope[th] < 0],
                             key=lambda k: abs(recent_slope[k])*(1+var_lift[k]), reverse=True)[:8]

        def plot_theme_plotly(keys, title):
            fig = go.Figure()
            for k in keys:
                fig.add_trace(go.Scatter(x=years_plot, y=lift.loc[k, years_plot].values,
                                         mode="lines+markers", name=k,
                                         line=dict(width=3), marker=dict(size=8)))
            fig.add_hline(y=1.0, line_width=1.5, line_dash="dash", opacity=0.6)
            fig.update_xaxes(title_text="연도")
            fig.update_yaxes(title_text="lift (배)")
            return style_fig(fig, title + f" — 최근 {N_slope}년 기준")

        uu, vv = st.columns([1,1], gap="large")
        fig_tu = plot_theme_plotly(up_sorted, "상승세")
        fig_tu = style_fig(fig_tu, bg_color=VIZ_BG["theme_up"], bg_alpha=0.5)
        fig_tu.update_layout(legend=dict(orientation="h", y=1.10, yanchor="bottom", x=0, xanchor="left"))
        fig_tu = add_line_end_labels(fig_tu, years_plot, lift, up_sorted)
        fig_tu = force_legend_top_padding(fig_tu, base_top=130)  # ★ 추가
        with uu:
            st.plotly_chart(fig_tu, use_container_width=True, config={"displayModeBar": False})

        fig_td = plot_theme_plotly(down_sorted, "하락세")
        fig_td = style_fig(fig_td, bg_color=VIZ_BG["theme_down"], bg_alpha=0.5)
        fig_td.update_layout(legend=dict(orientation="h", y=1.10, yanchor="bottom", x=0, xanchor="left"))
        fig_td = add_line_end_labels(fig_td, years_plot, lift, down_sorted)
        fig_td = force_legend_top_padding(fig_td, base_top=130)  # ★ 추가
        with vv:
            st.plotly_chart(fig_td, use_container_width=True, config={"displayModeBar": False})
    else:
        st.info("텍스트에서 주제를 감지하지 못해 '주제(키워드)' 트렌드를 생략합니다.")
else:
    st.info("연도에서 연도를 추출할 수 없어 '주제(키워드)' 트렌드를 건너뜁니다.")

# --------------------- 설치 / 실행 ---------------------
with st.expander("설치 / 실행"):
    st.code("pip install streamlit folium streamlit-folium pandas wordcloud plotly matplotlib", language="bash")
    st.code("streamlit run S_KSP_clickpro_v4_plotly_patch_FIXED.py", language="bash")














































































