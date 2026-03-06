"""Notion API を用いたデータソース・ページ取得。"""
import httpx
from fastapi.concurrency import run_in_threadpool

from utils.branch_name import build_github_branch_name
from utils.format import (
    blocks_to_markdown,
    extract_page_id_from_url,
    get_task_id_from_page_data,
    get_task_title_from_page_data,
)
from utils.status import check_contains_tag


async def query_datasource_by_task_id(
    task_id: str,
    *,
    notion_api_url: str,
    datasource_id: str,
    headers: dict,
) -> dict:
    number = task_id.replace("ES-", "").replace("ES", "")
    payload = {
        "filter": {
            "property": "タスクID",
            "unique_id": {"equals": int(number)},
        }
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{notion_api_url}/data_sources/{datasource_id}/query",
            headers=headers,
            json=payload,
        )
        if response.status_code == 200:
            return response.json()
        return {"error": response.text}


async def get_blocks_recursive(
    block_id: str,
    *,
    client: httpx.AsyncClient,
    notion_api_url: str,
    headers: dict,
) -> list:
    all_blocks = []
    next_cursor = None
    while True:
        params = {}
        if next_cursor:
            params["start_cursor"] = next_cursor
        response = await client.get(
            f"{notion_api_url}/blocks/{block_id}/children",
            headers=headers,
            params=params,
        )
        if response.status_code != 200:
            break
        data = response.json()
        for block in data.get("results", []):
            if block.get("has_children"):
                block["children"] = await get_blocks_recursive(
                    block["id"],
                    client=client,
                    notion_api_url=notion_api_url,
                    headers=headers,
                )
            all_blocks.append(block)
        if not data.get("has_more"):
            break
        next_cursor = data.get("next_cursor")
    return all_blocks


async def fetch_page_detail(
    task_id: str,
    *,
    notion_api_url: str,
    datasource_id: str,
    headers: dict,
    model_id: str,
    aws_session,
) -> dict:
    """タスクIDからページ詳細・マークダウン・ブランチ名を取得する。"""
    datasource = await query_datasource_by_task_id(
        task_id,
        notion_api_url=notion_api_url,
        datasource_id=datasource_id,
        headers=headers,
    )
    if "error" in datasource or not datasource.get("results"):
        return {"error": datasource.get("error", "No results")}
    page_id = extract_page_id_from_url(datasource["results"][0]["url"])

    async with httpx.AsyncClient(timeout=30.0) as client:
        page_response = await client.get(
            f"{notion_api_url}/pages/{page_id}",
            headers=headers,
        )
        if page_response.status_code != 200:
            return {"error": page_response.text}
        page_data = page_response.json()

        blocks = await get_blocks_recursive(
            page_id,
            client=client,
            notion_api_url=notion_api_url,
            headers=headers,
        )
    markdown_content = blocks_to_markdown(blocks)
    bug_tag = check_contains_tag(page_data, "バグ")
    task_id_val = get_task_id_from_page_data(page_data)
    task_title = get_task_title_from_page_data(page_data)
    branch_name = await run_in_threadpool(
        build_github_branch_name,
        task_id_val,
        task_title,
        bug_tag,
        model_id,
        aws_session,
    )
    return {
        "bug_tag": bug_tag,
        "branch_name": branch_name,
        "markdown_content": markdown_content,
    }
