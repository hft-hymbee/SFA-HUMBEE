"""FastAPI application entrypoint for the Humbee SFA backend."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated

import structlog
import uvicorn
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

import humbee_sfa.models_registry  # noqa: F401  # Ensure model metadata is registered.
from humbee_sfa.core.db import get_db_session, get_engine, get_sessionmaker
from humbee_sfa.core.errors.handlers import install_exception_handlers
from humbee_sfa.core.settings import Settings, get_settings
from humbee_sfa.integration.humbee.client import reset_humbee_client
from humbee_sfa.modules.approvals.contracts import registry as approval_subject_registry
from humbee_sfa.modules.approvals.router import router as approvals_router
from humbee_sfa.modules.attendance.router import router as attendance_router
from humbee_sfa.modules.beats.adapter import BeatCreateAdapter, BeatEditAdapter
from humbee_sfa.modules.beats.router import router as beats_router
from humbee_sfa.modules.home.router import router as home_router
from humbee_sfa.modules.identity.router import router as identity_router
from humbee_sfa.modules.leave.adapter import LeaveAdapter
from humbee_sfa.modules.leave.router import router as leave_router
from humbee_sfa.modules.notifications.router import router as notifications_router
from humbee_sfa.modules.orders.adapter import DpOrderAdapter
from humbee_sfa.modules.orders.router import router as orders_router
from humbee_sfa.modules.org.geography_router import router as org_geography_router
from humbee_sfa.modules.org.router import router as org_router
from humbee_sfa.modules.outlets.adapter import OutletVerificationAdapter
from humbee_sfa.modules.outlets.router import router as outlets_router
from humbee_sfa.modules.reporting.projector_worker import ReportingProjectorWorker
from humbee_sfa.modules.reporting.router import router as reporting_router
from humbee_sfa.modules.routes.router import router as routes_router
from humbee_sfa.modules.routes.sweep_worker import EndOfDaySweepWorker
from humbee_sfa.modules.targets.router import router as targets_router
from humbee_sfa.platform.sms import get_sms_gateway
from humbee_sfa.platform.telemetry.logging import configure_logging
from humbee_sfa.platform.telemetry.middleware import RequestContextMiddleware

logger = structlog.get_logger("humbee_sfa.app")


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    cfg = get_settings()
    route_sweep_worker: EndOfDaySweepWorker | None = None
    reporting_projector_worker: ReportingProjectorWorker | None = None
    
    if cfg.environment != "test":
        get_sms_gateway(cfg)
        route_sweep_worker = EndOfDaySweepWorker(
            get_engine(),
            get_sessionmaker(),
            tenant_id=cfg.tenant_id,
            day_boundary_hour_ist=cfg.day_boundary_hour_ist,
            sweep_grace_minutes=cfg.route_sweep_grace_minutes,
        )
        route_sweep_worker.start()
        reporting_projector_worker = ReportingProjectorWorker(
            get_engine(), interval_seconds=cfg.reporting_projector_interval_seconds
        )
        reporting_projector_worker.start()
    try:
        yield
    finally:
        if route_sweep_worker is not None:
            route_sweep_worker.stop()
        if reporting_projector_worker is not None:
            reporting_projector_worker.stop()
        reset_humbee_client()


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or get_settings()
    configure_logging(cfg)
    docs = cfg.api_docs_enabled
    app = FastAPI(
        title=cfg.app_name,
        debug=cfg.debug,
        lifespan=_lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[*cfg.cors_web_origins, *cfg.cors_app_origins],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_exception_handlers(app)

    approval_subject_registry.register(LeaveAdapter(), replace=True)
    approval_subject_registry.register(BeatCreateAdapter(), replace=True)
    approval_subject_registry.register(BeatEditAdapter(), replace=True)
    approval_subject_registry.register(DpOrderAdapter(), replace=True)
    approval_subject_registry.register(OutletVerificationAdapter(), replace=True)
    approval_subject_registry.validate_complete()

    app.include_router(identity_router)
    app.include_router(org_router)
    app.include_router(org_geography_router)
    app.include_router(approvals_router)
    app.include_router(notifications_router)
    app.include_router(leave_router)
    app.include_router(beats_router)
    app.include_router(attendance_router)
    app.include_router(routes_router)
    app.include_router(orders_router)
    app.include_router(outlets_router)
    app.include_router(reporting_router)
    app.include_router(targets_router)
    app.include_router(home_router)

    logger.info("app_startup", environment=cfg.environment)

    @app.get("/livez")
    def livez() -> JSONResponse:
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok"})

    @app.get("/health")
    def health(session: Annotated[Session, Depends(get_db_session)]) -> JSONResponse:
        try:
            session.execute(text("SELECT 1"))
        except SQLAlchemyError as exc:
            logger.warning("health_database_unavailable", error=type(exc).__name__)
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={"status": "degraded", "database": "unavailable"},
            )
        return JSONResponse(status_code=status.HTTP_200_OK, content={"status": "ok", "database": "ok"})

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "humbee_sfa.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        access_log=False,  # RequestContextMiddleware emits the structured request log instead.
    )


if __name__ == "__main__":
    run()
