"""
Notion の本文（マークダウン）と対象フォルダを元に LLM で requirement.md を生成する。
雛形は app/prompts/requirement_prompt.md。
ストリーミング時は LLM の思考過程（reasoningContent）と本文（text）を逐次 yield する。
"""
import os
import re
from collections.abc import AsyncGenerator
from typing import Any


def _load_requirement_template() -> str:
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "prompts", "requirement_prompt.md")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _extract_urls(text: str) -> list[str]:
    url_pattern = re.compile(r"https?://[^\s\)\]\>]+")
    return list(dict.fromkeys(url_pattern.findall(text)))[:20]


def _get_folder_context(repo_path: str, max_entries: int = 80) -> str:
    if not repo_path or not os.path.isdir(repo_path):
        return ""
    lines = []
    try:
        for root, dirs, files in os.walk(repo_path, topdown=True):
            rel = os.path.relpath(root, repo_path)
            if rel == ".":
                rel = ""
            skip = {".git", "__pycache__", "node_modules", ".venv", "venv", ".env"}
            dirs[:] = [d for d in dirs if d not in skip]
            for d in dirs[:15]:
                lines.append((os.path.join(rel, d) if rel else d) + "/")
            for f in files[:25]:
                if not f.startswith("."):
                    lines.append(os.path.join(rel, f) if rel else f)
            if len(lines) >= max_entries:
                break
    except OSError:
        return ""
    return "\n".join(lines[:max_entries]) if lines else ""


def _build_prompt_and_steps(
    markdown_body: str,
    repo_path: str | None,
) -> tuple[str, list[dict[str, str]]]:
    """プロンプトとアコーディオン用 steps を組み立てる。思考過程表示用のため 2. 参照URL と 4. LLM 生成のみ steps に含める。"""
    steps: list[dict[str, str]] = []
    folder_ctx = _get_folder_context(repo_path or "") if repo_path else ""

    urls = _extract_urls(markdown_body)
    steps.append({"title": "2. 参照URL", "content": "\n".join(urls) if urls else "(なし)"})

    template = _load_requirement_template()

    prompt = f"""以下で与える「雛形」の構成・見出しを維持したまま、Notion タスク本文と対象フォルダ・参照URLを反映して requirement.md を1つ作成してください。
- 出力は requirement.md の本文のみ（説明やコードブロックの囲みは不要）
- 雛形のセクション（# Role, # Task, # Input など）は維持し、内容を Notion 本文と参照URLに基づいて具体化すること
- 対象フォルダの構成を考慮し、既存コードに沿った要件にすること

## 雛形（この構成に従う）
{template[:8000]}

## Notion タスク本文（マークダウン）
{markdown_body[:12000]}

## 対象フォルダ構成
{folder_ctx[:4000] if folder_ctx else "(なし)"}

## 参照URL
{chr(10).join(urls[:30]) if urls else "(なし)"}
"""
    return prompt, steps


async def stream_requirement_md_async(
    markdown_body: str,
    branch_name: str,
    repo_path: str | None,
    model_id: str,
    session: Any,
    *,
    thinking_budget_tokens: int = 4096,
) -> AsyncGenerator[tuple[str, Any], None]:
    """
    LLM のストリームで requirement.md を生成し、思考過程・本文を逐次 yield する。
    yield: ("steps", steps) → ("thinking", str) の 0 回以上 → ("content", str) の 0 回以上 → ("done", {"requirement_md", "steps"})
    または ("error", str)。
    """
    prompt, steps = _build_prompt_and_steps(markdown_body, repo_path or "")

    yield "steps", steps

    try:
        from strands.models import BedrockModel
    except ImportError:
        steps.append({"title": "4. LLM 生成", "content": "Strands 未インストールのためスキップ"})
        requirement_md = _load_requirement_template() or "# Requirement\n\n"
        requirement_md += "\n\n<!-- Notion 本文を元に手動で作成 -->\n\n" + markdown_body[:8000]
        yield "done", {"requirement_md": requirement_md, "steps": steps}
        return

    if not model_id:
        steps.append({"title": "4. LLM 生成", "content": "MODEL_ID 未設定のためスキップ"})
        template = _load_requirement_template()
        requirement_md = (template or "# Requirement\n\n") + "\n\n" + markdown_body[:8000]
        yield "done", {"requirement_md": requirement_md, "steps": steps}
        return

    try:
        bedrock_model = BedrockModel(
            model_id=model_id,
            boto_session=session,
            max_tokens=max(thinking_budget_tokens + 4096, 8192),
            additional_request_fields={
                "thinking": {"type": "enabled", "budget_tokens": thinking_budget_tokens},
            },
        )
        messages = [{"role": "user", "content": [{"text": prompt}]}]
        requirement_md = ""
        steps.append({"title": "4. LLM 生成（ストリーミング）", "content": "..."})
        async for event in bedrock_model.stream(messages):
            if not event:
                continue
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"].get("delta") or {}
                if "reasoningContent" in delta:
                    rc = delta["reasoningContent"]
                    if isinstance(rc, dict) and rc.get("text"):
                        yield "thinking", rc["text"]
                if "text" in delta and delta["text"]:
                    requirement_md += delta["text"]
                    yield "content", delta["text"]
            if "messageStop" in event:
                break
        steps[-1]["content"] = "完了"
        yield "done", {"requirement_md": requirement_md.strip(), "steps": steps}
    except Exception as e:
        steps.append({"title": "4. LLM 生成", "content": f"エラー: {e}"})
        template = _load_requirement_template()
        requirement_md = (template or "# Requirement\n\n") + "\n\n" + markdown_body[:8000]
        yield "error", str(e)
        yield "done", {"requirement_md": requirement_md, "steps": steps}

    # --- テスト用: LLM を使わず固定文字で返す（必要なら上記 LLM ブロックをコメントアウトし、以下を有効化）---
    # _template = _load_requirement_template()
    # _fixed_thinking = "（テスト用）雛形とNotion本文を確認し、requirement.md の構成を検討しています。\n（テスト用）固定テキストで requirement.md を返します。"
    # _fixed_md = (_template or "# Requirement\n\n") + "\n\n<!-- テスト用固定 -->\n\n" + (markdown_body[:2000] or "(本文なし)")
    # steps.append({"title": "4. LLM 生成（ストリーミング）", "content": "テスト用固定"})
    # yield "thinking", _fixed_thinking
    # yield "content", _fixed_md
    # steps[-1]["content"] = "完了"
    # yield "done", {"requirement_md": _fixed_md.strip(), "steps": steps}
    # return


def generate_requirement_md(
    markdown_body: str,
    branch_name: str,
    repo_path: str | None,
    model_id: str,
    session,
) -> tuple[str, list[dict]]:
    """
    LLM で requirement.md 本文を生成する。
    戻り値: (requirement_md, steps)  steps はアコーディオン用 [{ "title": str, "content": str }]
    """
    prompt, steps = _build_prompt_and_steps(markdown_body, repo_path)
    template = _load_requirement_template()

    requirement_md = ""
    try:
        from strands import Agent
        from strands.models import BedrockModel
    except ImportError:
        steps.append({"title": "4. LLM 生成", "content": "Strands 未インストールのためスキップ"})
        requirement_md = template or "# Requirement\n\n"
        requirement_md += "\n\n<!-- Notion 本文を元に手動で作成 -->\n\n" + markdown_body[:8000]
        return requirement_md, steps

    if not model_id:
        steps.append({"title": "4. LLM 生成", "content": "MODEL_ID 未設定のためスキップ"})
        requirement_md = template or "# Requirement\n\n"
        requirement_md += "\n\n" + markdown_body[:8000]
        return requirement_md, steps

    try:
        bedrock_model = BedrockModel(
            model_id=model_id,
            boto_session=session,
            max_tokens=2000,
        )
        agent = Agent(model=bedrock_model)
        response = agent(prompt)
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
        requirement_md = (text or "").strip() or (template + "\n\n" + markdown_body[:8000])
        steps.append({"title": "4. LLM 生成", "content": "完了"})
    except Exception as e:
        steps.append({"title": "4. LLM 生成", "content": f"エラー: {e}"})
        requirement_md = (template or "# Requirement\n\n") + "\n\n" + markdown_body[:8000]

    return requirement_md, steps

    # --- テスト用: LLM を使わず固定文字で返す（必要なら上記 LLM ブロックをコメントアウトし、以下を有効化）---
    # requirement_md = (template or "# Requirement\n\n") + "\n\n<!-- テスト用固定 -->\n\n" + (markdown_body[:2000] or "(本文なし)")
    # steps.append({"title": "4. LLM 生成", "content": "テスト用固定"})
    # return requirement_md, steps
