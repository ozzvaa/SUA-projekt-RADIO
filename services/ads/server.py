import os
from typing import Literal, Optional

import httpx
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pymongo import MongoClient
from bson import ObjectId
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware

from Ads.Types import CreateAd, UpdateAd, TagModel, CostClass, Ad, AuthenticateResponse, AdResponse
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
        base_url=os.getenv("USERS_API_URL", "http://users-api:8000"),
        timeout=5.0
    )
    app.state.payments_api = httpx.Client(
        base_url=os.getenv("PAYMENTS_API_URL", "http://payments-api:8000"),
        timeout=5.0
    )

    # Seed initial data
    seed_database(app.state.mongo_client.get_database())
    yield
    app.state.users_api.close()
    app.state.payments_api.close()
    app.state.mongo_client.close()


app = FastAPI(lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.get("/ads/cost_classes", response_model=list[CostClass])
def get_cost_classes():
    cost_classes = app.state.cost_classes.find(
        {},
        {"_id": 0}
    )

    return [CostClass(**cost_class) for cost_class in cost_classes]


@app.get("/ads", response_model=list[AdResponse])
def list_published_ads(
        tag_id: Optional[Literal["tag_food", "tag_sport", "tag_technology", "tag_culture", "tag_events"]] = None,
        cost_class_id: Optional[Literal["cost_short", "cost_medium", "cost_long"]] = None
):
    filters = {"status": "published"}
    if tag_id is not None:
        filters["tags"] = tag_id
    if cost_class_id is not None:
        filters["cost_class_id"] = cost_class_id

    ads = app.state.ads.find(filters)
    return [
        AdResponse(id=str(ad.pop("_id")), **ad)
        for ad in ads
    ]


@app.get("/ads/list", response_model=list[Ad])
def list_my_ads(authentication: AuthenticateResponse = Depends(get_current_user)):
    ads = app.state.ads.find({"owner_id": str(authentication.user_id)})
    return [Ad(id=str(ad.pop("_id")), **ad) for ad in ads]


@app.get("/ads/{ad_id}", response_model=Ad)
def get_ad(ad_id: str):
    if not ObjectId.is_valid(ad_id):
        raise HTTPException(status_code=404, detail="Advertisement not found")

    ad = app.state.ads.find_one({"_id": ObjectId(ad_id)})
    if ad is None:
        raise HTTPException(status_code=404, detail="Advertisement not found")

    return Ad(id=str(ad.pop("_id")), **ad)


@app.post("/ads/create", status_code=201, response_model=Ad)
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


@app.put("/ads/{ad_id}", response_model=Ad)
def update_ad(
        ad_id: str,
        update: UpdateAd,
        authentication: AuthenticateResponse = Depends(get_current_user)
):
    if not ObjectId.is_valid(ad_id):
        raise HTTPException(status_code=404, detail="Advertisement not found")

    ad_id_object = ObjectId(ad_id)
    ad = app.state.ads.find_one({"_id": ad_id_object})
    if ad is None or ad.get("owner_id") != str(authentication.user_id):
        raise HTTPException(status_code=404, detail="Advertisement not found")

    updates = update.model_dump(exclude_unset=True)
    if "title" in updates and (updates["title"] is None or not updates["title"].strip()):
        raise HTTPException(status_code=400, detail="Title must not be empty")

    if "tags" in updates:
        available_tags = {tag["id"] for tag in app.state.tags.find({}, {"id": 1})}
        invalid_tags = set(updates["tags"]) - available_tags
        if invalid_tags:
            raise HTTPException(status_code=400, detail=f"Invalid tag IDs: {list(invalid_tags)}")

    if "cost_class_id" in updates and updates["cost_class_id"] is not None:
        available_cost_classes = {
            cost_class["id"]
            for cost_class in app.state.cost_classes.find({}, {"id": 1})
        }
        if updates["cost_class_id"] not in available_cost_classes:
            raise HTTPException(status_code=400, detail="Invalid cost class ID")

    if updates:
        app.state.ads.update_one({"_id": ad_id_object}, {"$set": updates})

    updated_ad = app.state.ads.find_one({"_id": ad_id_object})
    return Ad(id=str(updated_ad.pop("_id")), **updated_ad)


@app.post("/ads/submit/{ad_id}", response_model=Ad)
def submit_ad(
        ad_id: str,
        authentication: AuthenticateResponse = Depends(get_current_user),
):
    if not ObjectId.is_valid(ad_id):
        raise HTTPException(status_code=404, detail="Advertisement not found")

    ad_id_object = ObjectId(ad_id)
    ad = app.state.ads.find_one({"_id": ad_id_object})
    if ad is None or ad.get("owner_id") != str(authentication.user_id):
        raise HTTPException(status_code=404, detail="Advertisement not found")

    if ad.get("status", "draft") != "draft":
        raise HTTPException(status_code=409, detail="Only draft advertisements can be submitted for publishing")

    cost_class_id = ad.get("cost_class_id")
    cost_class = app.state.cost_classes.find_one({"id": cost_class_id}) if cost_class_id else None
    if cost_class is None:
        raise HTTPException(status_code=400, detail="A valid cost class is required to publish an advertisement")

    try:
        # TODO Integrate with payments
        payment_response = app.state.payments_api.post(
            "/payments",
            json={
                "ad_id": str(ad_id_object),
                "user_id": str(authentication.user_id),
                "amount": cost_class["price"]
            },
            headers={"Idempotency-Key": str(ad_id_object)}
        )
        payment_response.raise_for_status()
    except httpx.HTTPStatusError:
        raise HTTPException(status_code=502, detail="Payments service rejected the payment request")
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Payments service unavailable")

    app.state.ads.update_one(
        {"_id": ad_id_object, "status": "draft"},
        {"$set": {"status": "pending"}}
    )
    updated_ad = app.state.ads.find_one({"_id": ad_id_object})
    return Ad(id=str(updated_ad.pop("_id")), **updated_ad)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="0.0.0.0", port=8000)
