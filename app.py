import os
from dotenv import load_dotenv
import streamlit as st
import regex as re
from openai import OpenAI

# 환경변수에서 API 키 불러오기
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

# 예시 트윗 파일 읽기
with open("reference_tweets.txt", "r", encoding="utf-8") as f:
    reference_tweets = f.read()

st.title("일본 트위터 트렌드 기반 자동 트윗 생성")

# 1. 트렌드 원문 입력
trend_raw = st.text_area("트위터 트렌드 원문을 붙여넣으세요.")

def extract_keywords(text):
    keywords = []
    for line in text.splitlines():
        line = line.strip()
        if re.match(r"^#\S+$", line):
            keywords.append(line)
        elif re.match(r"^[\p{Hiragana}\p{Katakana}\p{Han}ー]+$", line):
            keywords.append(line)
        elif re.match(r"^[A-Za-z\s]+$", line) and not re.match(r"^(Trending|Only on X|posts?|K posts?)", line, re.I):
            keywords.append(line)
    return keywords

# 2. 키워드 추출 버튼
if st.button("트렌드 키워드 추출"):
    keywords = extract_keywords(trend_raw)
    if not keywords:
        st.warning("추출된 키워드가 없습니다. 입력을 확인하세요.")
    else:
        st.session_state['keywords'] = keywords
        # summaries도 초기화(새 키워드 추출 시)
        if 'summaries' in st.session_state:
            del st.session_state['summaries']

# 3. 키워드가 세션에 있으면 다음 단계 진행
if 'keywords' in st.session_state:
    keywords = st.session_state['keywords']
    st.subheader("추출된 트렌드 키워드")
    st.write(keywords)

    # 4. 한글 요약 생성 (최초 1회만)
    if 'summaries' not in st.session_state:
        summaries = []
        for kw in keywords:
            prompt = f"'{kw}'에 대해 한국어로 10~15자 이내로 간결하게 설명해줘."
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}]
            )
            summaries.append(resp.choices[0].message.content.strip())
        st.session_state['summaries'] = summaries

    # 5. 관심 트렌드 선택
    option_labels = [f"{k} - {s}" for k, s in zip(keywords, st.session_state['summaries'])]
    selected_idx = st.selectbox(
        "관심 트렌드를 선택하세요.",
        range(len(option_labels)),
        format_func=lambda x: option_labels[x],
        key="selected_trend_idx"
    )
    selected_trend = keywords[selected_idx]

    # 6. 게시물 형태 선택
    post_type = st.radio("게시물 형태를 선택하세요.", ["이미지", "텍스트"], key="post_type")

    # 7. 트윗 생성 버튼
    if st.button("트윗 생성"):
        # 트윗 생성 프롬프트
        tweet_prompt = f"""
아래는 일본 트위터의 실제 예시 트윗입니다. 분위기, 문장 구성, 말투, 해시태그 스타일을 참고해서,
'{selected_trend}' 트렌드와 AI, 데이터 등과의 연관성을 담아 비슷한 느낌의 일본어 트위터 게시물을 1개 작성해줘.
트위터 스타일로 자연스럽게 써주고, 너무 딱딱하지 않게 해줘.

참고 트윗:
{reference_tweets}
        """

        tweet_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": tweet_prompt}]
        )
        tweet_jp = tweet_resp.choices[0].message.content.strip()

        # 해시태그 생성
        hashtag_prompt = f"'{selected_trend}' 트렌드와 관련된 일본어 해시태그를 2~3개 생성해줘. '#' 포함해서."
        hashtag_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": hashtag_prompt}]
        )
        hashtags = hashtag_resp.choices[0].message.content.strip()

        # 한국어 번역
        translate_prompt = f"다음 일본어 트윗을 한국어로 번역해줘:\n{tweet_jp}"
        translate_resp = client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": translate_prompt}]
        )
        tweet_ko = translate_resp.choices[0].message.content.strip()

        st.markdown("### 일본어 트윗")
        st.write(tweet_jp)
        st.markdown("### 해시태그")
        st.write(hashtags)
        st.markdown("### 한국어 번역")
        st.write(tweet_ko)

        if post_type == "이미지":
            dalle_prompt = f"일본의 '{selected_trend}'와 관련된, 귀엽고 아기자기한 스타일의 일러스트"
            image_resp = client.images.generate(
                model="dall-e-3",
                prompt=dalle_prompt,
                n=1,  # 1장 생성
                size="1024x1024"
            )
            for idx, img in enumerate(image_resp.data):
                st.image(img.url, caption=f"생성된 이미지 {idx+1}")

    # 리셋 버튼(항상 노출)
    if st.button("새로운 키워드로 다시 시작"):
        st.session_state.clear()
        st.rerun()
