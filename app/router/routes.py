"""
路由配置模块，负责设置和配置应用程序的路由
"""

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.core.security import verify_auth_token
from app.log.logger import get_routes_logger
from app.router import gemini_routes, openai_routes, config_routes, log_routes, scheduler_routes, stats_routes # 新增导入 stats_routes
from app.service.key.key_manager import get_key_manager_instance
from app.service.stats_service import StatsService

logger = get_routes_logger()

# 配置Jinja2模板
templates = Jinja2Templates(directory="app/templates")


def setup_routers(app: FastAPI) -> None:
    """
    设置应用程序的路由

    Args:
        app: FastAPI应用程序实例
    """
    # 包含API路由
    app.include_router(openai_routes.router)
    app.include_router(gemini_routes.router)
    app.include_router(gemini_routes.router_v1beta)
    app.include_router(config_routes.router)
    app.include_router(log_routes.router)
    app.include_router(scheduler_routes.router) # 新增包含 scheduler 路由
    app.include_router(stats_routes.router) # 包含 stats API 路由

    # 添加页面路由
    setup_page_routes(app)

    # 添加健康检查路由
    setup_health_routes(app)
    setup_api_stats_routes(app) # Add API stats routes


def setup_page_routes(app: FastAPI) -> None:
    """
    设置页面相关的路由

    Args:
        app: FastAPI应用程序实例
    """

    @app.get("/", response_class=HTMLResponse)
    async def auth_page(request: Request):
        """认证页面"""
        return templates.TemplateResponse("auth.html", {"request": request})

    @app.post("/auth")
    async def authenticate(request: Request):
        """处理认证请求"""
        try:
            form = await request.form()
            auth_token = form.get("auth_token")
            if not auth_token:
                logger.warning("Authentication attempt with empty token")
                return RedirectResponse(url="/", status_code=302)

            if verify_auth_token(auth_token):
                logger.info("Successful authentication")
                response = RedirectResponse(url="/config", status_code=302)
                response.set_cookie(
                    key="auth_token", value=auth_token, httponly=True, max_age=3600
                )
                return response
            logger.warning("Failed authentication attempt with invalid token")
            return RedirectResponse(url="/", status_code=302)
        except Exception as e:
            logger.error(f"Authentication error: {str(e)}")
            return RedirectResponse(url="/", status_code=302)

    @app.get("/keys", response_class=HTMLResponse)
    async def keys_page(request: Request):
        """密钥管理页面"""
        try:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to keys page")
                return RedirectResponse(url="/", status_code=302)

            key_manager = await get_key_manager_instance()
            keys_status = await key_manager.get_keys_by_status()
            total_keys = len(keys_status["valid_keys"]) + len(keys_status["invalid_keys"])
            valid_key_count = len(keys_status["valid_keys"])
            invalid_key_count = len(keys_status["invalid_keys"])

            stats_service = StatsService()
            api_stats = await stats_service.get_api_usage_stats()
            logger.info(f"API stats retrieved: {api_stats}")

            logger.info(f"Keys status retrieved successfully. Total keys: {total_keys}")
            return templates.TemplateResponse(
                "keys_status.html",
                {
                    "request": request,
                    "valid_keys": keys_status["valid_keys"],
                    "invalid_keys": keys_status["invalid_keys"],
                    "total_keys": total_keys, # Renamed for clarity
                    "valid_key_count": valid_key_count, # Added count
                    "invalid_key_count": invalid_key_count, # Added count
                    "api_stats": api_stats, # <-- Pass stats to template
                },
            )
        except Exception as e:
            logger.error(f"Error retrieving keys status or API stats: {str(e)}")
            # Optionally, render template with error or default stats
            # For now, re-raise to show error page
            raise
            
    @app.get("/config", response_class=HTMLResponse)
    async def config_page(request: Request):
        """配置编辑页面"""
        try:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to config page")
                return RedirectResponse(url="/", status_code=302)
                
            logger.info("Config page accessed successfully")
            return templates.TemplateResponse("config_editor.html", {"request": request})
        except Exception as e:
            logger.error(f"Error accessing config page: {str(e)}")
            raise
            
    @app.get("/logs", response_class=HTMLResponse)
    async def logs_page(request: Request):
        """错误日志页面"""
        try:
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to logs page")
                return RedirectResponse(url="/", status_code=302)
                
            logger.info("Logs page accessed successfully")
            return templates.TemplateResponse("error_logs.html", {"request": request})
        except Exception as e:
            logger.error(f"Error accessing logs page: {str(e)}")
            raise


def setup_health_routes(app: FastAPI) -> None:
    """
    设置健康检查相关的路由

    Args:
        app: FastAPI应用程序实例
    """

    @app.get("/health")
    async def health_check(request: Request):
        """健康检查端点"""
        logger.info("Health check endpoint called")
        return {"status": "healthy"}


def setup_api_stats_routes(app: FastAPI) -> None:
    """
    设置 API 统计相关的路由

    Args:
        app: FastAPI应用程序实例
    """
    @app.get("/api/stats/details")
    async def api_stats_details(request: Request, period: str):
        """获取指定时间段内的 API 调用详情"""
        try:
            # 验证认证
            auth_token = request.cookies.get("auth_token")
            if not auth_token or not verify_auth_token(auth_token):
                logger.warning("Unauthorized access attempt to API stats details")
                # Returning JSON error instead of redirect for API endpoint
                return {"error": "Unauthorized"}, 401

            logger.info(f"Fetching API call details for period: {period}")
            # Use the service instance here as well
            stats_service = StatsService() # Create an instance
            details = await stats_service.get_api_call_details(period)
            return details
        except ValueError as e:
            logger.warning(f"Invalid period requested for API stats details: {period} - {str(e)}")
            return {"error": str(e)}, 400
        except Exception as e:
            logger.error(f"Error fetching API stats details for period {period}: {str(e)}")
            return {"error": "Internal server error"}, 500
