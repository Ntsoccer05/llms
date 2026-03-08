import boto3
from dotenv import load_dotenv

load_dotenv()

client = boto3.client("bedrock-runtime")

messages = [
  {
    "role": "user", 
    "content": [{
      "text": "こんにちは"
    }]
  }
]
# https://dev.classmethod.jp/articles/claude-haiku-4-5-bedrock/
# 日本国内に特化のためjpを追加
# MODEL_ID = "jp.anthropic.claude-sonnet-4-5-20250929-v1:0" # sonnet
MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0" # haiku

response = client.converse(
  modelId=MODEL_ID,
  messages=messages
)

print(response["output"]["message"]["content"][0]["text"])