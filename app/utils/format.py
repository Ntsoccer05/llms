import re

def extract_rich_text(rich_texts):
  """Rich text 配列からテキストを抽出"""
  return "".join([rt.get("text", {}).get("content", "") for rt in rich_texts])

def blocks_to_markdown(blocks, level=0):
  """Notion blocks をマークダウンに変換"""
  markdown = ""
  indent = "  " * level
  
  for block in blocks:
      block_type = block.get("type")
      
      if block_type == "heading_1":
          text = extract_rich_text(block.get("heading_1", {}).get("rich_text", []))
          markdown += f"# {text}\n\n"
      
      elif block_type == "heading_2":
          text = extract_rich_text(block.get("heading_2", {}).get("rich_text", []))
          markdown += f"## {text}\n\n"
      
      elif block_type == "heading_3":
          text = extract_rich_text(block.get("heading_3", {}).get("rich_text", []))
          markdown += f"### {text}\n\n"
      
      elif block_type == "paragraph":
          text = extract_rich_text(block.get("paragraph", {}).get("rich_text", []))
          if text:
              markdown += f"{text}\n\n"
      
      elif block_type == "bulleted_list_item":
          text = extract_rich_text(block.get("bulleted_list_item", {}).get("rich_text", []))
          markdown += f"{indent}- {text}\n"
          
          if block.get("has_children") and "children" in block:
              markdown += blocks_to_markdown(block["children"], level + 1)
      
      elif block_type == "numbered_list_item":
          text = extract_rich_text(block.get("numbered_list_item", {}).get("rich_text", []))
          markdown += f"{indent}1. {text}\n"
          
          if block.get("has_children") and "children" in block:
              markdown += blocks_to_markdown(block["children"], level + 1)
      
      elif block_type == "image":
          url = block.get("image", {}).get("file", {}).get("url", "")
          if url:
              markdown += f"![image]({url})\n\n"
      
      elif block_type == "code":
          code = extract_rich_text(block.get("code", {}).get("rich_text", []))
          language = block.get("code", {}).get("language", "")
          markdown += f"```{language}\n{code}\n```\n\n"
      
      elif block.get("has_children") and "children" in block:
          markdown += blocks_to_markdown(block["children"], level)
  
  return markdown

def get_task_id_from_page_data(page_data: dict) -> str:
  """Notion ページの タスクID プロパティから 'ES-1' 形式のIDを取得"""
  props = page_data.get("properties", {})
  # タスクID または unique_id 型のプロパティを探す
  for name, prop in props.items():
    if prop.get("type") == "unique_id":
      uid = prop.get("unique_id", {})
      prefix = uid.get("prefix") or "ES"
      num = uid.get("number")
      if num is not None:
        return f"{prefix}-{num}"
  return ""


def get_task_title_from_page_data(page_data: dict) -> str:
  """Notion ページの タスク名（title 型）からタイトル文字列を取得"""
  props = page_data.get("properties", {})
  for name, prop in props.items():
    if prop.get("type") == "title":
      title_list = prop.get("title", [])
      if title_list:
        return (title_list[0].get("plain_text") or "").strip()
  return ""


def extract_page_id_from_url(url: str) -> str:
    """
    Notion ページURLからページIDを抽出してUUID形式に変換
    
    入力例：
    - https://www.notion.so/spectable-312e29314502808c898bca710d44c46d
    - 312e29314502808c898bca710d44c46d
    
    出力例：
    - 312e2931-4502-808c-898b-ca710d44c46d
    """
    # URL または 直接的なIDの場合
    if url.startswith('http'):
        # URLの末尾から32文字（ハイフンなし）を抽出
        match = re.search(r'([a-f0-9]{32})$', url)
        if match:
            page_id = match.group(1)
        else:
            raise ValueError(f"Invalid Notion URL: {url}")
    else:
        # 直接的なIDの場合
        page_id = url.replace('-', '')
    
    # UUID形式に変換（ハイフンを挿入）
    if len(page_id) == 32:
        uuid_format = f"{page_id[:8]}-{page_id[8:12]}-{page_id[12:16]}-{page_id[16:20]}-{page_id[20:]}"
        return uuid_format
    else:
        raise ValueError(f"Invalid page ID length: {page_id}")