import os
from fastapi import FastAPI, HTTPException, status, Depends
from pymongo import MongoClient
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_url = os.getenv(
        "ADS_DATABASE_URL", "mongodb://ads-db:27017/ads_db"
    )
    app.state.mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    # Fail early if MongoDB is unavailable
    app.state.mongo_client.admin.command("ping")
    app.state.ads = app.state.mongo_client.get_database()["ads"]
    yield
    app.state.mongo_client.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/ping")
def ping():
    return {"ping": "pong"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000)
