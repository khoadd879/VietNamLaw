from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api.routes import router
from db.init_db import init_db

app = FastAPI()


@app.on_event("startup")
def startup() -> None:
    init_db()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
