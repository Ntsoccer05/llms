import httpx
from fastapi import FastAPI
from fastapi.concurrency import run_in_threadpool
from config import get_settings
from utils.format import blocks_to_markdown, extract_page_id_from_url

app = FastAPI()

notion_api_key = get_settings().NOTION_API_KEY
notion_api_url = get_settings().NOTION_API_URL
datasource_id = get_settings().NOTION_DATASOURCE_ID
database_id = get_settings().NOTION_DATABASE_ID

headers = {
  'Authorization': f"Bearer {notion_api_key}",
  'Notion-Version': '2025-09-03'
}

@app.get("/")
async def databases():
  async with httpx.AsyncClient() as client:
    response = await client.get(
      f"{notion_api_url}/databases/{database_id}",
      headers=headers,
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}
    
@app.get("/datasources")
async def datasources():
  async with httpx.AsyncClient() as client:
    response = await client.get(
      f"{notion_api_url}/data_sources/{datasource_id}",
      headers=headers,
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}

"""文字列検索"""    
@app.post("/search")
async def search(query: str):
  search_headers = headers.copy()
  add_header = {
    "Content-Type": "application/json"
  }
  search_headers.update(add_header)
  payload = {
    "query": query,
    "filter": {
        "property": "object",
        "value": "page"
    },
    "sort": {
        "timestamp": "last_edited_time",
        "direction": "ascending"
    }
  }
  async with httpx.AsyncClient() as client:
    response = await client.post(
      f"{notion_api_url}/search",
      headers=search_headers,
      json=payload
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}

"""タスクIDによる検索"""
@app.post("/search/datasource")
async def search_by_datasource(task_id: str):
  number = task_id.replace("ES-", "").replace("ES", "")
  
  payload = {
    "filter": {
        "property": "タスクID",
        "unique_id": {
            "equals": int(number)
        }
    }
  }
  
  async with httpx.AsyncClient() as client:
    response = await client.post(
      f"{notion_api_url}/data_sources/{datasource_id}/query",
      headers=headers,
      json=payload
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}
    
@app.get("/page")
async def page(task_id: str):
  datasource = await search_by_datasource(task_id)
  page_id = extract_page_id_from_url(datasource["results"][0]['url'])

  async with httpx.AsyncClient() as client:
    response = await client.get(
      f"{notion_api_url}/pages/{page_id}",
      headers=headers
    )

    if response.status_code == 200:
      return response.json()
    else:
      return {"error": response.text}
    
@app.get("/page/detail")
async def page_detail(task_id: str):
  datasource = await search_by_datasource(task_id)
  page_id = extract_page_id_from_url(datasource["results"][0]['url'])
  async with httpx.AsyncClient() as client:
    # ページ基本情報を取得
    page_response = await client.get(
      f"{notion_api_url}/pages/{page_id}",
      headers=headers
    )
    
    if page_response.status_code != 200:
      return {"error": page_response.text}
    
    page_data = page_response.json()
    
    # すべてのブロックを取得（ページネーション + 子ブロック対応）
    async def get_blocks_recursive(block_id):
      all_blocks = []
      next_cursor = None
      
      while True:
        params = {}
        if next_cursor:
          params['start_cursor'] = next_cursor
        
        blocks_response = await client.get(
          f"{notion_api_url}/blocks/{block_id}/children",
          headers=headers,
          params=params
        )

        # return blocks_response.json()
        
        if blocks_response.status_code != 200:
          break
        
        blocks_data = blocks_response.json()
        
        # 各ブロックについて、has_children なら子ブロックも取得
        for block in blocks_data.get("results", []):
          if block.get("has_children"):
            block["children"] = await get_blocks_recursive(block["id"])
          all_blocks.append(block)
        
        if not blocks_data.get("has_more"):
          break
        
        next_cursor = blocks_data.get("next_cursor")
      
      return all_blocks
    
    blocks = await get_blocks_recursive(page_id)

    # # マークダウンに変換
    # markdown_content = blocks_to_markdown(blocks)
    
    return {
      # "page": page_data,
      "blocks": blocks,
      # "markdown_content": markdown_content
    }