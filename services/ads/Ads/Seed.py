import os

from pymongo import MongoClient


mongo_url = os.getenv(
        "ADS_DATABASE_URL", "mongodb://ads-db:27017/ads_db"
    )

client = MongoClient(mongo_url, serverSelectionTimeoutMS=5000)
db = client["ads_db"]

# Predetermined tags
tags = [
    {"id": "tag_food", "name": "Food"},
    {"id": "tag_sport", "name": "Sport"},
    {"id": "tag_technology", "name": "Technology"},
    {"id": "tag_culture", "name": "Culture"},
    {"id": "tag_events", "name": "Events"},
]

# Predetermined cost classes
cost_classes = [
    {
        "id": "cost_short",
        "title": "Short advertisement",
        "min_duration_seconds": 5,
        "max_duration_seconds": 15,
        "price": 20.0
    },
    {
        "id": "cost_medium",
        "title": "Medium advertisement",
        "min_duration_seconds": 16,
        "max_duration_seconds": 30,
        "price": 40.0
    },
    {
        "id": "cost_long",
        "title": "Long advertisement",
        "min_duration_seconds": 31,
        "max_duration_seconds": 60,
        "price": 70.0
    }
]


def seed_collection(collection, data):
    for item in data:
        collection.update_one(
            {"id": item["id"]},
            {"$setOnInsert": item},
            upsert=True
        )

def seed_database(db):
    seed_collection(db["ad_tags"], tags)
    seed_collection(db["ad_cost_classes"], cost_classes)

    print("Database seeding completed.")

