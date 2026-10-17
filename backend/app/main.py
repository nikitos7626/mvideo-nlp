import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import settings
from app.routers import extract
from app.schemas import CardIn, CardOut


app = FastAPI(title="Attribute Extraction API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(extract.router)


@app.post("/extract", response_model=CardOut, include_in_schema=False)
def extract_alias(card: CardIn) -> CardOut:
    """Алиас для автоматических тестеров: POST /extract -> CardOut"""
    return extract._run(card)


@app.get("/")
def root_ui(request: Request):
    """
    Интерактивный веб-интерфейс М.Видео AI.
    Если запрос отправлен клиентом API или скриптом (Accept: application/json),
    возвращает JSON со схемой и ссылками на эндпоинты.
    """
    accept = request.headers.get("accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return JSONResponse({
            "service": "M.Video Product Attribute Extraction API",
            "version": "0.2.0",
            "status": "online",
            "endpoints": {
                "extract": "POST /api/extract",
                "extract_alias": "POST /extract",
                "batch": "POST /api/extract/batch",
                "brand_register": "POST /api/extract/brands/register",
                "health": "GET /api/extract/health",
                "swagger_docs": "/docs",
                "openapi_schema": "/openapi.json"
            }
        })
    static_file = os.path.join(os.path.dirname(__file__), "static", "index.html")
    return FileResponse(static_file)


@app.get("/health")
def root_health() -> dict:
    return {"ok": True}