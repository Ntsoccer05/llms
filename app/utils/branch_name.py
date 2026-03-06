"""
GitHub ブランチ名生成（タスクID + bug_tag + LLM でスラッグ生成）
AWS Strands Agent (Bedrock) を使用してタスクタイトルから適したスラッグを生成する。
"""
import re


def _fallback_slug(task_title: str) -> str:
  """LLM 未使用時のフォールバック: タイトルを英数字・ハイフンのスラッグに変換"""
  if not task_title or not task_title.strip():
    return "task"
  # スペース・記号をハイフンに、英数字とハイフンのみ残す
  s = task_title.strip()
  s = re.sub(r"[^\w\s-]", "", s)
  s = re.sub(r"[-\s]+", "-", s).strip("-").lower()
  return s[:50] if s else "task"


def _generate_slug_with_strands(task_title: str, model_id: str, session) -> str | None:
  """
  Strands Agent (Bedrock) でタスクタイトルからブランチ用スラッグを生成する。
  失敗時は None を返し、呼び出し側でフォールバックすること。
  """
  try:
    from strands import Agent
    from strands.models import BedrockModel
  except ImportError:
    return None

  if not model_id or not task_title.strip():
    return None

  try:
    bedrock_model = BedrockModel(
      model_id=model_id,
      boto_session=session,
      max_tokens=100,
    )
    agent = Agent(model=bedrock_model)
    prompt = (
      f"以下のタスクタイトルから、GitHub ブランチ名に使う短いスラッグを1つだけ生成してください。\n"
      f"条件: 英小文字とハイフンのみ、スペースなし、30文字以内。説明は不要でスラッグのみ1行で返す。\n\n"
      f"タスクタイトル: {task_title.strip()}"
    )
    response = agent(prompt)
    # Strands の応答: 文字列 / .content / メッセージリスト など
    text = None
    if isinstance(response, str):
      text = response
    elif hasattr(response, "content"):
      text = getattr(response, "content", None)
    elif hasattr(response, "messages") and response.messages:
      last = response.messages[-1]
      text = getattr(last, "content", str(last)) if hasattr(last, "content") else str(last)
    else:
      text = str(response) if response else None
    if not text:
      return None
    slug = text.strip().split("\n")[0].strip()
    slug = re.sub(r"[^a-z0-9-]", "", slug.lower()).strip("-")[:50]
    return slug or None
  except Exception:
    return None


def build_github_branch_name(
  task_id: str,
  task_title: str,
  bug_tag: bool,
  model_id: str,
  session,
) -> str:
  """
  bug_tag に応じて bug/{task_id}/{slug} または feature/{task_id}/{slug} を返す。
  スラッグは LLM (Strands/Bedrock) で生成し、失敗時はタイトルからフォールバックする。
  """
  prefix = "bug" if bug_tag else "feature"
  # タスクIDはそのまま使用（例: ES-1）
  safe_task_id = (task_id or "0").strip()
  slug = _generate_slug_with_strands(task_title, model_id, session) or _fallback_slug(task_title)
  return f"{prefix}/{safe_task_id}/{slug}"
