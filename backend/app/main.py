from app.portfolio import models as portfolio_models
from app.trade_details import models as trade_detail_models
from app.execution import models as live_models
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import ORIGIN, PROD, settings
from app.core.lifespan import lifespan
from app.models import trading
from app.brokers.gateway import router as broker_gateway
from app.brokers.individual.routes import router as individual_brokers
from app.brokers.approval.routes import router as approvals
from app.execution.routes import router as execution
from app.security.mfa import router as mfa
from app.database.session import Base, engine, DB
from app.models.identity import User, Token, LoginSession, Audit
from app.security.authentication import hasher
from app.services.accounts import audit
from app.schemas.identity import Register
from app.api.health import router as router_0
from app.api.auth import router as router_1
from app.api.users import router as router_2
from app.brokers.routes import router as router_3
from app.dashboard.routes import router as router_4
from app.risk.routes import router as router_5
from app.admin.routes import router as router_6
app = FastAPI(title='GNK ALGO API', version=settings.app_version, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.origins, allow_credentials=True, allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE'], allow_headers=['Content-Type', 'X-CSRF-Token'])
app.include_router(router_0)
app.include_router(router_1)
app.include_router(router_2)
app.include_router(router_3)
app.include_router(router_4)
app.include_router(router_5)
app.include_router(router_6)

@app.middleware('http')
async def headers(request, call_next):
    response = await call_next(request)
    response.headers.update({'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY', 'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store'})
    if PROD:
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response
app.include_router(broker_gateway)
app.include_router(approvals)
app.include_router(execution)
app.include_router(mfa)

app.include_router(individual_brokers)

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def sanitized_validation_error(request,error):
    # Never echo raw inputs: broker API tokens/passwords can appear in validation input.
    return JSONResponse(status_code=422,content={'detail':[{'loc':list(item['loc']),'msg':item['msg'],'type':item['type']} for item in error.errors()]})

from app.compliance.routes import router as compliance_router
app.include_router(compliance_router)

from app.api.public import router as public_router
app.include_router(public_router)

from app.security.mfa_recovery import router as mfa_recovery_router, review_router as mfa_recovery_review_router
app.include_router(mfa_recovery_router)

app.include_router(mfa_recovery_review_router)

from app.market_data.router import router as market_router, admin_router as market_admin_router
from app.market_data.websocket_manager import router as market_ws_router
app.include_router(market_router)
app.include_router(market_admin_router)
app.include_router(market_ws_router)

from app.execution.live_routes import router as live_router,admin_router as live_admin_router
app.include_router(live_router)
app.include_router(live_admin_router)

from app.trade_details.routes import router as trade_details_router
app.include_router(trade_details_router)

from app.portfolio.routes import router as portfolio_router
app.include_router(portfolio_router)

from app.brokers.dhan.routes import router as dhan_router
app.include_router(dhan_router)
