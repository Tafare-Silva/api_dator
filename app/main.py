import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings
from app.core.exceptions import BusinessRuleError, NotFoundError, business_rule_handler, not_found_handler

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Handlers de exceção customizados
app.add_exception_handler(NotFoundError, not_found_handler)
app.add_exception_handler(BusinessRuleError, business_rule_handler)


# Sem HTTPS, service workers não são confiáveis (principalmente no Safari/iOS),
# então o build web depende do navegador revalidar os arquivos a cada acesso
# em vez de servir uma cópia em cache. Sem isso, usuários iOS ficam presos
# numa versão antiga do app por dias após um deploy.
@app.middleware("http")
async def no_cache_web_build(request, call_next):
    response = await call_next(request)
    if not request.url.path.startswith(settings.API_V1_STR):
        response.headers["Cache-Control"] = "no-cache, must-revalidate"
    return response

# Rotas
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "ok", "project": settings.PROJECT_NAME}


# Build web do app Flutter (gerado com `flutter build web`, copiado para cá no deploy).
# Montado por último e na raiz para que as rotas de API acima continuem tendo prioridade;
# StaticFiles(html=True) serve index.html tanto em "/" quanto em rotas desconhecidas,
# necessário para o roteamento client-side do Flutter web funcionar.
_WEB_BUILD_DIR = os.path.join(os.path.dirname(__file__), "..", "web_build")
if os.path.isdir(_WEB_BUILD_DIR):
    app.mount("/", StaticFiles(directory=_WEB_BUILD_DIR, html=True), name="web")


# Configura o Swagger para mostrar o campo Bearer token no botão Authorize
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        routes=app.routes,
    )

    schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }

    # Aplica o BearerAuth em todos os endpoints
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            operation["security"] = [{"BearerAuth": []}]

    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi