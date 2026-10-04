"""
Generates a short reactive caption/title via Groq -- deliberately reactive
rather than a neutral description (see spec rationale: MrBeast content and
general reaction-style framing both fare better than flat reposting).
Requires env var: GROQ_API_KEY
"""
import os
from groq import Groq

SYSTEM_PROMPT = """You write short, punchy, reactive captions for viral short-form
video reposts. Given a source title, write ONE caption under 100 characters that
reacts to the clip rather than just describing it -- think "bro really said--" energy,
not a neutral summary. No hashtags. No quotation marks around the output."""


def generate_caption(title: str) -> str:
    client = Groq(api_key=os.environ["GROQ_API_KEY"])
    response = client.chat.completions.create(
        # Check console.groq.com/docs/models for the current model list before
        # relying on this -- Groq's lineup changes fairly often.
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Source title: {title}"},
        ],
        max_tokens=60,
        temperature=0.9,
    )
    return response.choices[0].message.content.strip()
