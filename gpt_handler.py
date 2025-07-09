from openai import OpenAI
import os

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def ask_gpt_invest_weather(news_articles):
    joined_news = "\n\n---\n\n".join(news_articles)
    system_msg = "너는 증시 분석가야. 뉴스 기반으로 오늘 단기투자 가능성에 대해 명확하게 평가해줘."

    user_prompt = f"""
다음은 오늘의 주요 뉴스입니다:

{joined_news}

이 뉴스들을 종합해 오늘의 투자 날씨를 알려줘.
- 분위기가 좋다면 '맑음'
- 부정적이면 '흐림'
- 판단이 어려우면 '안개'

문장 요약 + 날씨 코드 포함해서 알려줘.
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7,
            max_tokens=700
        )

        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"[GPT 오류] {e}")
        return "❌ GPT 처리 중 오류 발생"
