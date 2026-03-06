def check_contains_tag(page_data: dict, tag_name: str) -> bool:
  """
  ページの multi_select プロパティに指定されたタグが含まれているかチェック

  Args:
    page_data: Notion ページデータ
    tag_name: チェックするタグ名（例：「バグ」）

  Returns:
    True: タグが含まれている
    False: タグが含まれていない

  例：
    if check_contains_tag(page_data, "バグ"):
      print("このタスクはバグです")
  """
  properties = page_data.get("properties", {})

  for prop_name, prop_value in properties.items():
    # multi_select 型のプロパティを探す
    if prop_value.get("type") == "multi_select":
      multi_select_items = prop_value.get("multi_select", [])

      # multi_select の各アイテムをチェック
      for item in multi_select_items:
        if tag_name in item.get("name", ""):
          return True

  return False

def get_all_tags(page_data: dict) -> list:
  """
  ページのすべての multi_select タグを取得

  Args:
    page_data: Notion ページデータ

  Returns:
    タグ名のリスト

  例：
    tags = get_all_tags(page_data)
    # ["新規機能", "バグ", "改善"]
  """
  tags = []
  properties = page_data.get("properties", {})

  for prop_name, prop_value in properties.items():
    if prop_value.get("type") == "multi_select":
      multi_select_items = prop_value.get("multi_select", [])
      for item in multi_select_items:
        tags.append(item.get("name", ""))

  return tags