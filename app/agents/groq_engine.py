import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

def explain_findings(findings):
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError("GROQ_API_KEY is missing")

    client = Groq(api_key=api_key)

    prompt = f"""
You are a Senior Kubernetes SRE Engineer.

Analyze these Kubernetes diagnostic findings:

{findings}

For each finding explain:
1. What is the issue?
2. What is its possible impact?
3. What should be checked?
4. What is the recommended safe action?

Important:
- Never recommend deleting Kubernetes system resources without verification.
- Distinguish genuine incidents from harmless system warnings.
- Do not invent missing information.
- Give practical troubleshooting steps.
- Use simple technical English.
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {"role": "user", "content": prompt}
        ],
        temperature=0.2
    )

    return response.choices[0].message.content
