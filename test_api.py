import requests
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv('OPENROUTER_API_KEY')
model = os.getenv('AI_MODEL', 'deepseek/deepseek-chat-v3.1')

print(f"Testing API key: {api_key[:20]}...")
print(f"Model: {model}")

response = requests.post(
    "https://openrouter.ai/api/v1/chat/completions",
    headers={
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    },
    json={
        "model": model,
        "messages": [{"role": "user", "content": "test"}]
    }
)

print(f"\nStatus: {response.status_code}")
print(f"Response: {response.text}")
