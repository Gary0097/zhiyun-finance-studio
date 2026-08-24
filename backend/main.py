# -*- coding: utf-8 -*-
"""Finance Studio HTTP and Agent entrypoint."""

from __future__ import annotations

import json
import sys
import sqlite3
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from qwenpaw.plugins.api import PluginApi

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
PLUGIN_VERSION = "0.2.0"


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
