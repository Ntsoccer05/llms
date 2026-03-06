"""
Notion API 呼び出しロジック（同期版）
Streamlit GUI およびテストから利用可能
"""
import json
import httpx
from typing import Any
from config import get_settings
from utils.format import extract_page_id_from_url, blocks_to_markdown


def _parse_error_response(response_text: str) -> dict[str, Any]:
    """Notion API のエラーレスポンスをパースして message を抽出"""
    try:
        data = json.loads(response_text)
        if isinstance(data, dict) and "message" in data:
            return {"error": data["message"], "_raw": data}
    except (json.JSONDecodeError, TypeError):
        pass
    return {"error": response_text}

def _get_headers():
    settings = get_settings()
    return {
        "Authorization": f"Bearer {settings.NOTION_API_KEY}",
        "Notion-Version": "2025-09-03",
    }

def _get_base_url():
    return get_settings().NOTION_API_URL

def _get_datasource_id():
    return get_settings().NOTION_DATASOURCE_ID

def _get_database_id():
    return get_settings().NOTION_DATABASE_ID


def fetch_databases() -> dict[str, Any]:
    """データベース情報を取得"""
    with httpx.Client() as client:
        response = client.get(
            f"{_get_base_url()}/databases/{_get_database_id()}",
            headers=_get_headers(),
        )
        if response.status_code == 200:
            return response.json()
        return _parse_error_response(response.text)


def fetch_datasources() -> dict[str, Any]:
    """データソース情報を取得"""
    with httpx.Client() as client:
        response = client.get(
            f"{_get_base_url()}/data_sources/{_get_datasource_id()}",
            headers=_get_headers(),
        )
        if response.status_code == 200:
            return response.json()
        return _parse_error_response(response.text)


def search(query: str) -> dict[str, Any]:
    """文字列検索"""
    search_headers = _get_headers()
    search_headers["Content-Type"] = "application/json"
    payload = {
        "query": query,
        "filter": {"property": "object", "value": "page"},
        "sort": {"timestamp": "last_edited_time", "direction": "ascending"},
    }
    with httpx.Client() as client:
        response = client.post(
            f"{_get_base_url()}/search",
            headers=search_headers,
            json=payload,
        )
        if response.status_code == 200:
            return response.json()
        return {"error": response.text}


def search_by_datasource(task_id: str) -> dict[str, Any]:
    """タスクIDによるデータソース検索"""
    number = task_id.replace("ES-", "").replace("ES", "")
    payload = {
        "filter": {
            "property": "タスクID",
            "unique_id": {"equals": int(number)},
        }
    }
    with httpx.Client() as client:
        response = client.post(
            f"{_get_base_url()}/data_sources/{_get_datasource_id()}/query",
            headers=_get_headers(),
            json=payload,
        )
        if response.status_code == 200:
            return response.json()
        return _parse_error_response(response.text)


def fetch_page(task_id: str) -> dict[str, Any]:
    """タスクIDからページ情報を取得"""
    datasource = search_by_datasource(task_id)
    if "error" in datasource:
        return datasource
    results = datasource.get("results", [])
    if not results:
        return {"error": "該当するページがありません"}
    page_id = extract_page_id_from_url(results[0]["url"])
    return fetch_page_by_id(page_id)


def fetch_page_by_id(page_id: str) -> dict[str, Any]:
    """ページIDからページ情報を取得"""
    with httpx.Client() as client:
        response = client.get(
            f"{_get_base_url()}/pages/{page_id}",
            headers=_get_headers(),
        )
        if response.status_code == 200:
            return response.json()
        return _parse_error_response(response.text)


def _get_blocks_recursive(client: httpx.Client, block_id: str, headers: dict) -> list:
    """再帰的にブロックを取得"""
    all_blocks = []
    next_cursor = None
    while True:
        params = {}
        if next_cursor:
            params["start_cursor"] = next_cursor
        blocks_response = client.get(
            f"{_get_base_url()}/blocks/{block_id}/children",
            headers=headers,
            params=params,
        )
        if blocks_response.status_code != 200:
            break
        blocks_data = blocks_response.json()
        for block in blocks_data.get("results", []):
            if block.get("has_children"):
                block["children"] = _get_blocks_recursive(
                    client, block["id"], headers
                )
            all_blocks.append(block)
        if not blocks_data.get("has_more"):
            break
        next_cursor = blocks_data.get("next_cursor")
    return all_blocks


def fetch_blocks(page_id: str) -> list:
    """ページIDからブロック一覧を取得（再帰）"""
    headers = _get_headers()
    with httpx.Client() as client:
        return _get_blocks_recursive(client, page_id, headers)


def fetch_page_detail(task_id: str) -> dict[str, Any]:
    """タスクIDからページ詳細（ブロック一覧）を取得（一括）"""
    datasource = search_by_datasource(task_id)
    if "error" in datasource:
        return {"error": datasource["error"], "steps": {}}
    results = datasource.get("results", [])
    if not results:
        return {"error": "該当するページがありません", "steps": {}}
    page_id = extract_page_id_from_url(results[0]["url"])
    headers = _get_headers()
    with httpx.Client() as client:
        page_response = client.get(
            f"{_get_base_url()}/pages/{page_id}",
            headers=headers,
        )
        if page_response.status_code != 200:
            return {"error": page_response.text, "steps": {}}
        page_data = page_response.json()
        blocks = _get_blocks_recursive(client, page_id, headers)
    markdown_content = blocks_to_markdown(blocks)
    return {
        "page_data": page_data,
        "blocks": blocks,
        "markdown_content": markdown_content,
        "datasource_result": datasource,
    }
