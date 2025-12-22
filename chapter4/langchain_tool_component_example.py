from langchain_core.tools import tool
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, AIMessage

# 105ページ
@tool
def add(a: int, b: int) -> int:
    """足し算を行い、結果を返すツール"""
    return a + b

MODEL_ID = "jp.anthropic.claude-haiku-4-5-20251001-v1:0"

# モデルを初期化し、ツールを統合
model = init_chat_model(
    model=MODEL_ID,
    model_provider="bedrock_converse"
).bind_tools([add])

response = model.invoke("2と3を足すといくつになる？")
print(response)