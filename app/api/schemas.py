"""API リクエスト/レスポンス用 Pydantic モデル。"""
from pydantic import BaseModel


class BranchCheckoutRequest(BaseModel):
    branch_name: str
    base_branch: str | None = None
    repo_path: str | None = None
    github_repo: str | None = None


class RequirementGenerateRequest(BaseModel):
    markdown_body: str
    branch_name: str
    repo_path: str | None = None


class RequirementReadyAckRequest(BaseModel):
    branch_name: str
    action: str  # "approved" | "rejected"
