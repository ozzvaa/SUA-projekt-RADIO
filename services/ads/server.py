import os

import httpx
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo import MongoClient
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from Ads.Types import CreateAd, JWTPayload, TagModel, Ad, AuthenticateResponse
from Ads.Seed import seed_database

security = HTTPBearer()


def get_user(token: str) -> AuthenticateResponse:
    try:
        response = app.state.users_api.post(
            "/users/authenticate",
            headers={"Authorization": f"Bearer {token}"}
        )

        response.raise_for_status()

        print(response.json())

        return AuthenticateResponse(**response.json())

    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token"
            )

        raise HTTPException(
            status_code=502,
            detail="Users service error"
        )

    except httpx.RequestError:
        raise HTTPException(
            status_code=503,
            detail="Users service unavailable"
        )


def get_current_user(
        credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AuthenticateResponse:
    return get_user(credentials.credentials)


@asynccontextmanager
async def lifespan(app: FastAPI):
    mongo_url = os.getenv(
        "ADS_DATABASE_URL", "mongodb://ads-db:27017/ads_db"
    )
    app.state.mongo_client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
    # Fail early if MongoDB is unavailable
    app.state.mongo_client.admin.command("ping")

    # Select database


    app.state.ads = app.state.mongo_client.get_database()["ads"]
    app.state.cost_classes = app.state.mongo_client.get_database()["ad_cost_classes"]
    app.state.tags = app.state.mongo_client.get_database()["ad_tags"]

    app.state.users_api = httpx.Client(
        base_url=f"http://users-api:8000",
        timeout=5.0
    )

    # Seed initial data
    seed_database(app.state.mongo_client.get_database())
    yield
    app.state.users_api.close()
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


@app.get("/ping/users")
def ping_users():
    response = app.state.users_api.get("/users")
    response.raise_for_status()
    return response.json()


@app.get("/ads/tags", response_model=list[TagModel])
def get_tags():
    tags = app.state.tags.find(
        {},
        {"_id": 0}
    )

    return [
        TagModel(
            id=tag["id"],
            name=tag["name"]
        )
        for tag in tags
    ]


@app.post("/ads", status_code=201, response_model=Ad)
def create_ad(new_ad: CreateAd, authentication: AuthenticateResponse = Depends(get_current_user)):
    available_tags = {
        tag["id"]
        for tag in app.state.tags.find({}, {"id": 1})
    }

    # Validate submitted tags
    invalid_tags = set(new_ad.tags) - available_tags

    if invalid_tags:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tag IDs: {list(invalid_tags)}"
        )

    ad = {
        "owner_id": str(authentication.user_id),
        **new_ad.model_dump(),
        "status": "draft"
    }

    result = app.state.ads.insert_one(ad)

    ad["id"] = str(result.inserted_id)

    return Ad(**ad)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000)
