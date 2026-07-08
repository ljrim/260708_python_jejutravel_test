# -*- coding: utf-8 -*-
"""
🏝️ 제주도 여행 일정 추천 & 상권 분석 Streamlit 앱
--------------------------------------------------------------
이 앱은 '제주상권.csv' 데이터를 활용해서
  1) 개인 페르소나 → 여행 컨셉에 맞춘 제주 여행 일정을 추천하고,
  2) 추천된 일정의 이동 루트를 지도로 보여주며,
  3) 업종 소분류별 / 동네별 매장 수를 막대그래프와 위치 지도로 분석합니다.

초보자도 이해할 수 있도록 각 단계마다 한글 주석을 자세히 달았습니다.

▶ 실행 방법 (터미널에서):
    streamlit run app.py
"""

# ──────────────────────────────────────────────────────────────
# 0. 라이브러리 불러오기
# ──────────────────────────────────────────────────────────────
import math                              # 두 지점 사이 거리 계산(수학 함수)에 사용
import streamlit as st                   # 웹앱 화면을 만드는 핵심 라이브러리
import pandas as pd                      # 표(CSV) 데이터를 다루는 라이브러리
import plotly.express as px              # 막대그래프 등 인터랙티브 그래프
import folium                            # 지도를 그리는 라이브러리
from folium.plugins import MarkerCluster, AntPath  # 마커 묶기 / 움직이는 경로선
from streamlit_folium import st_folium   # folium 지도를 streamlit 화면에 표시


# ──────────────────────────────────────────────────────────────
# 1. 기본 페이지 설정
# ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="제주도 여행 추천 & 상권 분석",  # 브라우저 탭 제목
    page_icon="🏝️",                            # 브라우저 탭 아이콘
    layout="wide",                              # 화면을 넓게 사용
)


# ──────────────────────────────────────────────────────────────
# 2. 데이터 불러오기 (한 번만 읽고 캐시에 저장 → 빠름)
# ──────────────────────────────────────────────────────────────
# @st.cache_data : 함수 결과를 저장해 두었다가, 다음에 같은 함수를 부르면
#                  파일을 다시 읽지 않고 저장된 결과를 즉시 돌려줍니다.
@st.cache_data
def load_data():
    """배포용 경량 데이터(jeju_data.csv.gz)를 읽어 돌려주는 함수.

    원본 '제주상권.csv'(약 21MB, cp949)에서 앱이 실제로 쓰는 8개 컬럼만 골라
    좌표 정리·제주 범위 필터·결측 제거까지 끝낸 뒤 UTF-8 gzip CSV(약 1.7MB)로
    미리 저장해 두었습니다. 덕분에 배포 저장소 용량이 작고 로딩도 빠릅니다.
    (경량 파일을 다시 만들려면 prepare_data.py 를 실행하세요.)
    """
    # compression="gzip" : .gz 압축 파일을 자동으로 풀어서 읽습니다.
    # encoding="utf-8"   : 경량 파일은 UTF-8로 저장했습니다.
    df = pd.read_csv("jeju_data.csv.gz", compression="gzip", encoding="utf-8")
    return df


# 실제로 데이터를 불러옵니다.
df = load_data()


# ──────────────────────────────────────────────────────────────
# 3. 페르소나 & 여행 컨셉 정의
# ──────────────────────────────────────────────────────────────
# 여행 컨셉 5가지: 각 컨셉은 "어떤 업종 소분류를 방문할지" 목록(cats)을 가집니다.
CONCEPTS = {
    "🍜 맛집 미식 투어": {
        "desc": "제주 대표 먹거리(흑돼지·회·한정식)를 즐기는 미식 중심 일정",
        "cats": ["백반/한정식", "횟집", "돼지고기 구이/찜", "경양식",
                 "국수/칼국수", "중국집", "국/탕/찌개류", "치킨", "김밥/만두/분식"],
        "color": "red",        # 지도 경로선 색
    },
    "☕ 감성 카페 투어": {
        "desc": "바다 뷰 카페와 디저트를 즐기는 여유로운 감성 여행",
        "cats": ["카페", "빵/도넛"],
        "color": "purple",
    },
    "🏖️ 힐링 & 웰니스": {
        "desc": "펜션·요가·스파로 몸과 마음을 쉬어가는 힐링 일정",
        "cats": ["펜션", "호텔/리조트", "요가/필라테스 학원", "피부 관리실", "카페"],
        "color": "green",
    },
    "🎨 문화 & 액티비티": {
        "desc": "해양 레저·오락·사진 스팟으로 즐기는 활동적인 여행",
        "cats": ["수상/해양 레저업", "골프 연습장", "헬스장", "사진촬영업",
                 "노래방", "볼링장", "기타 오락관련 서비스업"],
        "color": "blue",
    },
    "🛍️ 쇼핑 & 기념품": {
        "desc": "제주 기념품·화장품·의류 쇼핑을 즐기는 알뜰 여행",
        "cats": ["기념품점", "화장품 소매업", "여성 의류 소매업",
                 "기타 의류 소매업", "채소/과일 소매업"],
        "color": "orange",
    },
}

# 페르소나 5가지: 각 페르소나는 어울리는 여행 컨셉을 추천 목록으로 가집니다.
PERSONAS = {
    "🧑‍🍳 미식가": ["🍜 맛집 미식 투어", "☕ 감성 카페 투어"],
    "💑 커플/연인": ["☕ 감성 카페 투어", "🏖️ 힐링 & 웰니스", "🎨 문화 & 액티비티"],
    "👨‍👩‍👧‍👦 가족 여행객": ["🍜 맛집 미식 투어", "🎨 문화 & 액티비티", "🏖️ 힐링 & 웰니스"],
    "🎒 나홀로 배낭여행": ["☕ 감성 카페 투어", "🎨 문화 & 액티비티", "🛍️ 쇼핑 & 기념품"],
    "🏄 액티비티 마니아": ["🎨 문화 & 액티비티", "🍜 맛집 미식 투어", "🛍️ 쇼핑 & 기념품"],
}


# ──────────────────────────────────────────────────────────────
# 4. 여행 경로(루트)를 만드는 도우미 함수들
# ──────────────────────────────────────────────────────────────
def haversine(lat1, lon1, lat2, lon2):
    """두 위경도 좌표 사이의 실제 거리(km)를 구하는 함수 (지구는 둥그니까요!)."""
    R = 6371  # 지구 반지름(km)
    # 도(degree) 단위를 라디안으로 바꿔서 삼각함수에 넣습니다.
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def build_route(points):
    """
    여러 장소(points)를 '가까운 곳부터 차례로' 잇는 경로 순서를 만드는 함수.
    (최근접 이웃 알고리즘: 현재 위치에서 가장 가까운 다음 장소를 계속 선택)
    points : [{"위도":.., "경도":..}, ...] 형태의 리스트
    반환값 : 방문 순서대로 정렬된 같은 형태의 리스트
    """
    if not points:
        return []
    remaining = points.copy()      # 아직 방문 안 한 장소들
    route = [remaining.pop(0)]     # 첫 장소에서 출발
    while remaining:
        last = route[-1]           # 현재 마지막으로 방문한 장소
        # 남은 장소들 중 현재 위치에서 가장 가까운 장소를 찾습니다.
        nearest = min(
            remaining,
            key=lambda p: haversine(last["위도"], last["경도"], p["위도"], p["경도"]),
        )
        route.append(nearest)      # 경로에 추가하고
        remaining.remove(nearest)  # 남은 목록에서 제거
    return route


def make_itinerary(data, categories, region, days, spots_per_day, seed):
    """
    선택한 컨셉/지역/일수에 맞춰 여행 일정을 만드는 함수.
    - data          : 전체 상권 데이터프레임
    - categories    : 이 컨셉에서 방문할 업종 소분류 목록
    - region        : "전체" / "제주시" / "서귀포시"
    - days          : 여행 일수
    - spots_per_day : 하루에 방문할 장소 수
    - seed          : 무작위 추출 기준값(바꾸면 다른 장소가 추천됨)
    반환값 : 하루 단위로 묶인 일정 리스트  [[1일차 장소들], [2일차...], ...]
    """
    # (1) 컨셉에 해당하는 업종만 남깁니다.
    sub = data[data["상권업종소분류명"].isin(categories)].copy()
    # (2) 지역 필터 (전체가 아니면 해당 시군구만)
    if region != "전체":
        sub = sub[sub["시군구명"] == region]

    if len(sub) == 0:
        return []  # 조건에 맞는 장소가 없으면 빈 일정 반환

    total_needed = days * spots_per_day       # 필요한 총 장소 수

    # (3) 후보를 넉넉히 무작위로 뽑은 뒤(seed로 결과 고정), 경로용으로 사용합니다.
    pool_size = min(len(sub), max(total_needed * 3, total_needed))
    pool = sub.sample(n=pool_size, random_state=seed)

    # (4) 딕셔너리 리스트로 변환 후 가까운 순서대로 경로를 만듭니다.
    points = pool.to_dict("records")
    ordered = build_route(points)[:total_needed]  # 필요한 개수만큼 잘라 사용

    # (5) 하루 단위(spots_per_day개씩)로 잘라서 일정으로 묶습니다.
    itinerary = [
        ordered[i:i + spots_per_day]
        for i in range(0, len(ordered), spots_per_day)
    ]
    return itinerary


# ──────────────────────────────────────────────────────────────
# 5. 화면 구성 : 제목 + 탭 2개
# ──────────────────────────────────────────────────────────────
st.title("🏝️ 제주도 여행 일정 추천 & 상권 분석")
st.caption("제주상권 데이터로 나만의 여행 일정을 만들고, 업종·동네별 상권을 분석해 보세요.")

tab_plan, tab_analysis = st.tabs(["🗺️ 여행 일정 추천", "📊 상권 분석"])


# ==============================================================
# 탭 1 : 여행 일정 추천
# ==============================================================
with tab_plan:
    st.subheader("1️⃣ 나에게 맞는 여행 컨셉 찾기")

    # ----- 입력 영역을 3개 컬럼으로 나눕니다 -----
    col1, col2, col3 = st.columns(3)

    with col1:
        # 페르소나 선택
        persona = st.selectbox("👤 여행자 페르소나를 골라주세요", list(PERSONAS.keys()))

    # 선택한 페르소나에게 추천되는 컨셉 목록
    recommended = PERSONAS[persona]

    with col2:
        # 추천 컨셉을 기본값으로 보여주되, 원하면 다른 컨셉도 고를 수 있게 전체 목록 제공
        concept = st.selectbox(
            "🎯 여행 컨셉 선택",
            list(CONCEPTS.keys()),
            index=list(CONCEPTS.keys()).index(recommended[0]),  # 추천 1순위를 기본 선택
        )

    with col3:
        # 여행 지역 선택
        region = st.selectbox("📍 여행 지역", ["전체", "제주시", "서귀포시"])

    # 페르소나 추천 컨셉을 안내 문구로 보여줍니다.
    st.info(f"**{persona}** 님께 추천하는 컨셉: " + " · ".join(recommended))
    # 선택한 컨셉 설명 표시
    st.markdown(f"> **{concept}** — {CONCEPTS[concept]['desc']}")

    # ----- 여행 일수 / 하루 방문 장소 수 설정 -----
    c1, c2 = st.columns(2)
    with c1:
        days = st.slider("🗓️ 여행 일수", min_value=1, max_value=5, value=3)
    with c2:
        spots_per_day = st.slider("📌 하루 방문 장소 수", min_value=2, max_value=6, value=4)

    st.divider()

    # ----- 일정 생성 버튼 -----
    # 버튼을 누르면 일정을 만들어 session_state(앱이 기억하는 저장 공간)에 담아둡니다.
    # 이렇게 해두면 지도를 조작해 화면이 새로고침돼도 일정이 사라지지 않습니다.
    btn_col1, btn_col2 = st.columns([1, 1])
    with btn_col1:
        make = st.button("🚀 여행 일정 만들기", type="primary", width="stretch")
    with btn_col2:
        # '다른 코스 추천'을 누르면 seed 값을 바꿔 새로운 장소들을 추천합니다.
        reshuffle = st.button("🔄 다른 코스로 다시 추천", width="stretch")

    # seed(추천 기준값) 관리 : 처음에는 42로 시작, '다시 추천'마다 1씩 증가
    if "seed" not in st.session_state:
        st.session_state.seed = 42
    if reshuffle:
        st.session_state.seed += 1
        make = True  # 다시 추천도 곧 일정 생성으로 이어지도록 처리

    # 버튼이 눌렸다면 일정을 새로 만들어 저장합니다.
    if make:
        itinerary = make_itinerary(
            df,
            CONCEPTS[concept]["cats"],
            region,
            days,
            spots_per_day,
            st.session_state.seed,
        )
        # 나중에 지도/일정표에서 다시 쓰기 위해 저장해 둡니다.
        st.session_state.itinerary = itinerary
        st.session_state.concept = concept

    # ----- 저장된 일정이 있으면 화면에 표시 -----
    if st.session_state.get("itinerary"):
        itinerary = st.session_state.itinerary
        concept_saved = st.session_state.concept
        route_color = CONCEPTS[concept_saved]["color"]  # 경로선 색상

        if not itinerary:
            st.warning("조건에 맞는 장소가 없어요. 지역이나 컨셉을 바꿔보세요.")
        else:
            st.subheader("2️⃣ 추천 여행 일정")

            # 왼쪽엔 일정표(텍스트), 오른쪽엔 지도를 나란히 배치합니다.
            plan_col, map_col = st.columns([1, 1.3])

            # ----- (왼쪽) 일자별 일정표 -----
            with plan_col:
                for day_idx, day_spots in enumerate(itinerary, start=1):
                    st.markdown(f"#### 🗓️ {day_idx}일차")
                    for spot_idx, spot in enumerate(day_spots, start=1):
                        # 각 장소를 '순번. 가게명 (업종) — 주소' 형태로 보여줍니다.
                        addr = spot.get("도로명주소") or "주소 정보 없음"
                        st.markdown(
                            f"**{spot_idx}. {spot['상호명']}** "
                            f"`{spot['상권업종소분류명']}`  \n"
                            f"　📍 {addr}"
                        )
                    st.markdown("")  # 일차 사이 여백

            # ----- (오른쪽) 이동 루트 지도 -----
            with map_col:
                st.markdown("#### 🗺️ 이동 루트 지도")
                st.caption("숫자 마커 = 방문 순서(일차-순번), 색선 = 이동 경로")

                # 모든 장소를 하나로 펼쳐서 지도의 중심 좌표(평균 위치)를 계산합니다.
                all_spots = [s for day in itinerary for s in day]
                center_lat = sum(s["위도"] for s in all_spots) / len(all_spots)
                center_lon = sum(s["경도"] for s in all_spots) / len(all_spots)

                # folium 지도 객체를 만듭니다. (제주 전체가 보이도록 확대 레벨 설정)
                m = folium.Map(location=[center_lat, center_lon], zoom_start=11)

                # 일차별로 경로선과 마커를 그립니다.
                for day_idx, day_spots in enumerate(itinerary, start=1):
                    # 이 날의 이동 경로 좌표들 (위도, 경도) 순서 리스트
                    path = [(s["위도"], s["경도"]) for s in day_spots]

                    # 움직이는 경로선(AntPath)으로 이동 흐름을 표현합니다.
                    if len(path) >= 2:
                        AntPath(
                            path,
                            color=route_color,
                            weight=4,
                            delay=800,
                            tooltip=f"{day_idx}일차 이동 경로",
                        ).add_to(m)

                    # 각 장소에 '숫자 마커'를 찍습니다.
                    for spot_idx, s in enumerate(day_spots, start=1):
                        # 마커 안에 '일차-순번' 숫자를 넣어 방문 순서를 표시합니다.
                        label = f"{day_idx}-{spot_idx}"
                        folium.Marker(
                            location=[s["위도"], s["경도"]],
                            tooltip=f"[{day_idx}일차 {spot_idx}번] {s['상호명']}",
                            popup=folium.Popup(
                                f"<b>{s['상호명']}</b><br>{s['상권업종소분류명']}<br>"
                                f"{s.get('도로명주소','')}",
                                max_width=250,
                            ),
                            # DivIcon으로 숫자가 보이는 동그란 마커를 직접 그립니다.
                            icon=folium.DivIcon(
                                html=(
                                    f'<div style="background:{route_color};color:white;'
                                    f'width:26px;height:26px;border-radius:50%;'
                                    f'display:flex;align-items:center;justify-content:center;'
                                    f'font-size:12px;font-weight:bold;border:2px solid white;'
                                    f'box-shadow:0 0 3px #555;">{label}</div>'
                                )
                            ),
                        ).add_to(m)

                # folium 지도를 streamlit 화면에 그립니다.
                # returned_objects=[] : 지도 클릭 정보를 돌려받지 않아 불필요한 새로고침을 줄입니다.
                st_folium(m, width=700, height=520, returned_objects=[], key="route_map")

    else:
        # 아직 일정을 만들지 않았을 때 안내 문구
        st.info("위 조건을 고른 뒤 **🚀 여행 일정 만들기** 버튼을 눌러보세요!")


# ==============================================================
# 탭 2 : 상권 분석 (업종 소분류별 / 동네별 막대그래프 + 위치 지도)
# ==============================================================
with tab_analysis:
    st.subheader("📊 제주 상권 데이터 분석")

    # ----- 지역 필터 (분석 대상 좁히기) -----
    region2 = st.radio(
        "분석할 지역을 선택하세요",
        ["전체", "제주시", "서귀포시"],
        horizontal=True,   # 가로로 나란히 배치
    )
    # 선택한 지역에 맞게 데이터를 거릅니다.
    if region2 == "전체":
        data2 = df
    else:
        data2 = df[df["시군구명"] == region2]

    # 상단에 요약 숫자(총 매장 수, 업종 수, 동네 수)를 보여줍니다.
    m1, m2, m3 = st.columns(3)
    m1.metric("총 매장 수", f"{len(data2):,} 개")
    m2.metric("업종 소분류 수", f"{data2['상권업종소분류명'].nunique():,} 종")
    m3.metric("동네(행정동) 수", f"{data2['행정동명'].nunique():,} 개")

    st.divider()

    # ---------- (A) 업종 소분류별 매장 수 막대그래프 ----------
    st.markdown("### 🏪 업종 소분류별 매장 수 (상위 Top)")

    # 대분류로 한 번 더 걸러서 보고 싶을 수 있으니 선택 상자를 제공합니다.
    big_cats = ["전체"] + sorted(data2["상권업종대분류명"].dropna().unique().tolist())
    sel_big = st.selectbox("업종 대분류로 좁혀보기", big_cats)

    data_cat = data2 if sel_big == "전체" else data2[data2["상권업종대분류명"] == sel_big]

    top_n = st.slider("표시할 업종 개수(Top N)", 5, 30, 15)

    # value_counts()로 업종별 개수를 세고 상위 N개만 추립니다.
    cat_counts = (
        data_cat["상권업종소분류명"]
        .value_counts()
        .head(top_n)
        .reset_index()
    )
    cat_counts.columns = ["업종소분류", "매장수"]

    # plotly 가로 막대그래프 (개수 많은 순으로 위에서 아래로 정렬)
    fig_cat = px.bar(
        cat_counts.sort_values("매장수"),  # 아래→위로 커지도록 정렬
        x="매장수",
        y="업종소분류",
        orientation="h",                   # 가로 막대
        text="매장수",                     # 막대 끝에 숫자 표시
        color="매장수",
        color_continuous_scale="Teal",
        title=f"{region2} · {sel_big} 업종 소분류별 매장 수 Top {top_n}",
    )
    fig_cat.update_layout(height=500, yaxis_title="", coloraxis_showscale=False)
    st.plotly_chart(fig_cat, width="stretch")

    st.divider()

    # ---------- (B) 동네(행정동)별 매장 수 막대그래프 ----------
    st.markdown("### 🏘️ 동네(행정동)별 매장 수 (상위 Top)")

    top_n2 = st.slider("표시할 동네 개수(Top N)", 5, 30, 15, key="dong_topn")

    dong_counts = (
        data_cat["행정동명"]
        .value_counts()
        .head(top_n2)
        .reset_index()
    )
    dong_counts.columns = ["행정동", "매장수"]

    fig_dong = px.bar(
        dong_counts.sort_values("매장수"),
        x="매장수",
        y="행정동",
        orientation="h",
        text="매장수",
        color="매장수",
        color_continuous_scale="Sunset",
        title=f"{region2} · {sel_big} 동네별 매장 수 Top {top_n2}",
    )
    fig_dong.update_layout(height=500, yaxis_title="", coloraxis_showscale=False)
    st.plotly_chart(fig_dong, width="stretch")

    st.divider()

    # ---------- (C) 매장 위치 지도 ----------
    st.markdown("### 🗺️ 매장 위치 지도")
    st.caption("보고 싶은 업종을 고르면 해당 매장들의 위치를 지도에 표시합니다. "
               "(가까운 마커들은 자동으로 묶여서 보여집니다)")

    # 지도에 표시할 업종 소분류를 하나 선택합니다. (매장 많은 순으로 정렬해서 제공)
    cat_list = data_cat["상권업종소분류명"].value_counts().index.tolist()
    if len(cat_list) == 0:
        st.warning("표시할 데이터가 없습니다.")
    else:
        sel_cat = st.selectbox("지도에 표시할 업종 소분류", cat_list)

        # 선택 업종의 매장만 골라냅니다.
        map_data = data_cat[data_cat["상권업종소분류명"] == sel_cat]

        # 매장이 너무 많으면 지도가 느려지므로 최대 1500개까지만 표시합니다.
        MAX_POINTS = 1500
        shown = map_data
        if len(map_data) > MAX_POINTS:
            shown = map_data.sample(MAX_POINTS, random_state=0)
            st.info(f"매장이 많아 {MAX_POINTS:,}개만 지도에 표시합니다. "
                    f"(전체 {len(map_data):,}개)")

        # 지도 중심을 선택 업종 매장들의 평균 위치로 잡습니다.
        center = [shown["위도"].mean(), shown["경도"].mean()]
        m2map = folium.Map(location=center, zoom_start=11)

        # MarkerCluster : 가까운 마커들을 묶어서 보여줘 지도를 깔끔하게 유지합니다.
        cluster = MarkerCluster().add_to(m2map)
        for _, row in shown.iterrows():
            folium.Marker(
                location=[row["위도"], row["경도"]],
                tooltip=row["상호명"],
                popup=folium.Popup(
                    f"<b>{row['상호명']}</b><br>{row['상권업종소분류명']}<br>"
                    f"{row.get('도로명주소','')}",
                    max_width=250,
                ),
                icon=folium.Icon(color="blue", icon="info-sign"),
            ).add_to(cluster)

        st_folium(m2map, width=1100, height=550, returned_objects=[], key="analysis_map")
