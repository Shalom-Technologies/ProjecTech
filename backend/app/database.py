from motor.motor_asyncio import AsyncIOMotorClient
from app.config import settings
import logging

logger = logging.getLogger(__name__)

client: AsyncIOMotorClient = None
db = None


async def connect_to_mongo():
    global client, db
    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.DATABASE_NAME]
    # Verify connection
    await db.command("ping")
    logger.info(f"Connected to MongoDB: {settings.DATABASE_NAME}")
    await db.users.create_index("email", unique=True)
    await db.projects.create_index("salesperson_id")
    await db.projects.create_index("status")
    await db.projects.create_index("category")
    await db.projects.create_index([("created_at", -1)])
    await db.conversations.create_index("participants")
    await db.conversations.create_index("project_id")
    await db.messages.create_index("conversation_id")
    await db.messages.create_index([("conversation_id", 1), ("created_at", -1)])
    await db.notifications.create_index("user_id")
    await db.notifications.create_index([("created_at", -1)])
    await db.transactions.create_index("transaction_id", unique=True)
    await db.transactions.create_index("paystack_reference")
    await db.transactions.create_index("project_id")
    await db.transactions.create_index("status")
    await db.wallet_transactions.create_index("user_id")
    await db.wallet_transactions.create_index([("created_at", -1)])
    await db.password_resets.create_index("token", unique=True)
    await db.password_resets.create_index("user_id")
    await db.password_resets.create_index("expires_at", expireAfterSeconds=0)
    await db.reviews.create_index("reviewed_user_id")
    await db.reviews.create_index([("project_id", 1), ("reviewer_id", 1)], unique=True)


async def close_mongo_connection():
    global client
    if client:
        client.close()
        logger.info("MongoDB connection closed")


def get_database():
    if db is None:
        raise RuntimeError("Database not initialized. Call connect_to_mongo() first.")
    return db