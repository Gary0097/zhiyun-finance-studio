# -*- coding: utf-8 -*-
"""Finance Studio HTTP and Agent entrypoint."""

from __future__ import annotations

import json
import sys
import sqlite3
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from qwenpaw.plugins.api import PluginApi

import httpx
from uuid import uuid4
from fastapi.responses import StreamingResponse

try:
    from .finance_engine import analyze_financials, audit_expenses, forecast_cost
    from .finance_workflow import FinanceWorkflowStore
except ImportError:
    backend_dir = str(Path(__file__).resolve().parent)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)
    from finance_engine import analyze_financials, audit_expenses, forecast_cost
    from finance_workflow import FinanceWorkflowStore

router = APIRouter()
PLUGIN_VERSION = "0.3.0"


def _store() -> FinanceWorkflowStore:
    try:
        return FinanceWorkflowStore()
    except (OSError, sqlite3.Error) as exc:
        raise HTTPException(status_code=503, detail=f"财务持久化依赖不可用：{exc}") from exc


class InvoicesRequest(BaseModel):
    invoices: list[dict[str, Any]] = Field(max_length=20000)


class FinancialRecordsRequest(BaseModel):
    records: list[dict[str, Any]] = Field(max_length=100000)


class CostRequest(BaseModel):
    parameters: dict[str, Any]


class ArtifactReviewRequest(BaseModel):
    action: str
    reviewer: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=2000)


@router.get("/health")
async def health() -> dict[str, Any]:
    return {"status": "available", "version": PLUGIN_VERSION}


@router.post("/expense/audit")
async def expense_audit(request: InvoicesRequest) -> dict[str, Any]:
    try:
        return audit_expenses(request.invoices)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/finance/analyze")
async def finance_analyze(request: FinancialRecordsRequest) -> dict[str, Any]:
    try:
        return analyze_financials(request.records)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/cost/forecast")
async def cost_forecast(request: CostRequest) -> dict[str, Any]:
    try:
        return forecast_cost(request.parameters)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/artifacts/expense")
async def create_expense_artifact(request: InvoicesRequest) -> dict[str, Any]:
    try:
        payload = audit_expenses(request.invoices)
        return _store().create_artifact("expense", "报销审核结果", payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"财务持久化依赖不可用：{exc}") from exc


@router.post("/artifacts/finance")
async def create_finance_artifact(request: FinancialRecordsRequest) -> dict[str, Any]:
    try:
        payload = analyze_financials(request.records)
        return _store().create_artifact("finance", "财务分析看板", payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"财务持久化依赖不可用：{exc}") from exc


@router.post("/artifacts/cost")
async def create_cost_artifact(request: CostRequest) -> dict[str, Any]:
    try:
        payload = forecast_cost(request.parameters)
        return _store().create_artifact("cost", "成本预测", payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"财务持久化依赖不可用：{exc}") from exc


@router.get("/artifacts")
async def list_artifacts(kind: str | None = None, limit: int = 100) -> dict[str, Any]:
    try:
        return _store().list_artifacts(kind, limit)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"财务持久化依赖不可用：{exc}") from exc


@router.get("/artifacts/{artifact_id}")
async def get_artifact(artifact_id: str) -> dict[str, Any]:
    try:
        return _store().get_artifact(artifact_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="财务工件不存在") from exc


@router.post("/artifacts/{artifact_id}/reviews")
async def review_artifact(artifact_id: str, request: ArtifactReviewRequest) -> dict[str, Any]:
    try:
        return _store().review_artifact(artifact_id, request.action, request.reviewer, request.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="财务工件不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("/artifacts/{artifact_id}/export")
async def export_artifact(artifact_id: str) -> Response:
    try:
        content, media_type = _store().export_artifact(artifact_id)
        return Response(content=content, media_type=media_type,
                        headers={"Content-Disposition": 'attachment; filename="finance-artifact.json"'})
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="财务工件不存在") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def audit_review_expenses(invoices: list[dict[str, Any]]) -> dict[str, Any]:
    """Audit real invoices and persist a reviewable expense credential artifact."""
    payload = audit_expenses(invoices)
    return _store().create_artifact("expense", "报销审核结果", payload)


def run_review_financial_analysis(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute key financial ratios over real records and persist a reviewable artifact."""
    payload = analyze_financials(records)
    return _store().create_artifact("finance", "财务分析看板", payload)


def forecast_review_cost(parameters: dict[str, Any]) -> dict[str, Any]:
    """Forecast unit cost under real material/BOM price changes and persist a reviewable artifact."""
    payload = forecast_cost(parameters)
    return _store().create_artifact("cost", "成本预测", payload)




# ==== 应用内默认智能体（真实模型对话，SSE 流式） ====
CONSOLE_CHAT_URL = "http://127.0.0.1:8088/api/console/chat"
CHAT_TIMEOUT_SECONDS = 300

APP_CONTEXT = (
    "你是「制造云 AI-OS」{title}的智能助手。你可以调用 audit_review_expenses、run_review_financial_analysis、forecast_review_cost 等工具，"
    "基于用户工作台的真实业务数据回答问题；涉及分析结论时先调用对应工具再回答，不要凭空编造数据。"
)


class AgentChatRequest(BaseModel):
    """Client payload for the streaming in-app agent chat."""

    text: str = Field(min_length=1, max_length=4000, description="User message")
    session_id: str | None = Field(default=None, description="Persistent conversation id")
    user_id: str | None = Field(default="default", description="Calling user id")
    app_id: str | None = Field(default="zhiyun-finance-studio", description="Owning app id")
    context: str | None = Field(default=None, description="Extra system context from the UI")
    history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Prior turns [{{role, text}}] for multi-turn context",
    )


def _build_input(body: AgentChatRequest) -> list[dict[str, Any]]:
    """Build the console ``input`` message list from the dock payload."""
    context = APP_CONTEXT + ("\n" + body.context if body.context else "")
    input_messages: list[dict[str, Any]] = []
    if context:
        input_messages.append({"role": "system", "content": [{{"type": "text", "text": context}}]})
    for turn in body.history:
        if not isinstance(turn, dict):
            continue
        role = turn.get("role")
        text = turn.get("text")
        if not isinstance(text, str) or not text.strip():
            continue
        mapped_role = "assistant" if role in ("bot", "assistant") else "user"
        input_messages.append({{"role": mapped_role, "content": [{{"type": "text", "text": text}}]}})
    input_messages.append({{"role": "user", "content": [{{"type": "text", "text": body.text}}]}})
    return input_messages


@router.post("/agent/chat")
async def agent_chat(body: AgentChatRequest) -> StreamingResponse:
    """Proxy a user message to the real console chat and stream its SSE reply."""
    session_id = body.session_id or f"zhiyun-finance-studio-{{uuid4().hex}}"
    payload = {{
        "input": _build_input(body),
        "session_id": session_id,
        "user_id": body.user_id or "default",
        "stream": True,
        "metadata": {{
            "app_id": body.app_id or "zhiyun-finance-studio",
            "source_kind": "agent_dock",
            "data_mode": "real",
        }},
    }}

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async with httpx.AsyncClient(timeout=CHAT_TIMEOUT_SECONDS) as client:
                async with client.stream("POST", CONSOLE_CHAT_URL, json=payload) as response:
                    if response.status_code != 200:
                        err_body = await response.aread()
                        text = err_body.decode("utf-8", errors="replace")
                        yield f"data: {{json.dumps({{'error': text}})}}\n\n"
                        return
                    async for line in response.aiter_lines():
                        yield ("\n" if line == "" else line + "\n")
        except httpx.TimeoutException:
            yield f"data: {{json.dumps({{'error': '智能体响应超时，请稍后重试'}})}}\n\n"
        except Exception as exc:  # pragma: no cover - defensive
            yield f"data: {{json.dumps({{'error': f'调用智能体失败: {{exc}}'}})}}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={{"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}},
    )


class FinanceStudioPlugin:
    def register(self, api: PluginApi) -> None:
        api.register_http_router(router, prefix="/zhiyun-finance-studio", tags=["zhiyun-finance-studio"])
        api.register_tool(
            tool_name="audit_review_expenses",
            tool_func=audit_review_expenses,
            description="对真实发票做字段完整性、金额阈值、税号、税额与重复校验并生成可审阅报销审核工件。",
            icon="🧾",
            tool_type="internal",
        )
        api.register_tool(
            tool_name="run_review_financial_analysis",
            tool_func=run_review_financial_analysis,
            description="对真实财务记录计算毛利率、净利率、经营利润率、流动比率、负债率与环比趋势并生成可审阅看板。",
            icon="📉",
            tool_type="internal",
        )
        api.register_tool(
            tool_name="forecast_review_cost",
            tool_func=forecast_review_cost,
            description="按原材料/BOM价格变动、人力与制造费用占比与产量测算单位成本及年度影响，生成可审阅成本预测工件。",
            icon="🔮",
            tool_type="internal",
        )


plugin = FinanceStudioPlugin()
