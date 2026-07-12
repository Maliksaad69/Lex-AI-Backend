# quickstart.py
import os
import mistralai
from mistralai.client import Mistral

MISTRAL_API_KEY = "KPJd4GmacV6YzdwtLFkkIWtWl1k0aQzV"
client = Mistral(api_key=MISTRAL_API_KEY)

system_prompt = "you are a customer support system"
user_prompt = "what is the name of the president of pakistan"
model = "codestral-2508"
temperature = 0.7
max_tokens = 4096
chat_completion = client.chat.complete(
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    model=model,
    temperature=temperature,
    max_tokens=max_tokens,
)

print(chat_completion.choices[0].message.content)
