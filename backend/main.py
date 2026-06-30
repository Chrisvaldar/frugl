import logging

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from routers import compare, receipt
from services.rate_limit import check_rate_limit

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("app.log"),
    ],
)

PRODUCTION_FRONTEND_ORIGIN = "https://open-home-loans-take-home-task.vercel.app"

app = FastAPI(title="Frugl")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        PRODUCTION_FRONTEND_ORIGIN,
    ],
    allow_origin_regex=r"https://open-home-loans-take-home-task.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path.startswith("/api/"):
        client_ip = request.client.host if request.client else "unknown"
        try:
            check_rate_limit(client_ip)
        except HTTPException as exc:
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail},
            )
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(compare.router, prefix="/api")
app.include_router(receipt.router, prefix="/api")
