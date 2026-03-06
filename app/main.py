"""
FastAPI アプリケーション。
ルートは api.routers に分割している。
"""
from fastapi import FastAPI

from api.routers import notion, branch, requirement

app = FastAPI()

app.include_router(notion.router)
app.include_router(branch.router)
app.include_router(requirement.router)
