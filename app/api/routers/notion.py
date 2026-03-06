"""Notion データソース・ページ詳細 API。"""
from fastapi import APIRouter

from config import get_settings
from services.notion_service import query_datasource_by_task_id, fetch_page_detail

router = APIRouter(prefix="", tags=["notion"])


def _notion_headers():
    s = get_settings()
    return {
        "Authorization": f"Bearer {s.NOTION_API_KEY}",
        "Notion-Version": "2025-09-03",
    }


@router.post("/search/datasource")
async def search_by_datasource(task_id: str):
    """タスクIDによる検索（/page/detail から利用）。"""
    s = get_settings()
    result = await query_datasource_by_task_id(
        task_id,
        notion_api_url=s.NOTION_API_URL,
        datasource_id=s.NOTION_DATASOURCE_ID,
        headers=_notion_headers(),
    )
    return result


@router.get("/page/detail")
async def page_detail(task_id: str):
    """ページ詳細・マークダウン・ブランチ名を取得。"""
    s = get_settings()
    import boto3
    aws = boto3.Session(
        aws_access_key_id=s.AWS_ACCESS_KEY_ID or "",
        aws_secret_access_key=s.AWS_SECRET_ACCESS_KEY or "",
        region_name=s.AWS_DEFAULT_REGION or "us-east-1",
    )
    return await fetch_page_detail(
        task_id,
        notion_api_url=s.NOTION_API_URL,
        datasource_id=s.NOTION_DATASOURCE_ID,
        headers=_notion_headers(),
        model_id=s.MODEL_ID or "",
        aws_session=aws,
    )
