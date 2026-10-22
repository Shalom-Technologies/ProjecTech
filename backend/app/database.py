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
    await db.projects.create_index("assigned_to")
    await db.projects.create_index("invoice_token", unique=True, sparse=True)
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
    # A project can be paid for only once, even if two payments land at the same instant.
    try:
        await db.transactions.create_index(
            "project_id", unique=True, partialFilterExpression={"status": "success"},
            name="one_paid_transaction_per_project",
        )
    except Exception as e:  # noqa: BLE001 - old duplicate data would block it; app logic still guards
        logger.error(f"Could not create the one-payment-per-project index (duplicates in existing data?): {e}")
    await db.transactions.create_index("status")
    await db.wallet_transactions.create_index("user_id")
    await db.wallet_transactions.create_index("paystack_reference")
    await db.wallet_transactions.create_index([("created_at", -1)])
    # Reset tokens used to be stored as plain text. Remove those (they are live secrets) and
    # their old index, then index the hash that is stored now.
    await db.password_resets.delete_many({"token": {"$exists": True}})
    try:
        await db.password_resets.drop_index("token_1")
    except Exception:  # noqa: BLE001 - already gone on a fresh database
        pass
    await db.password_resets.create_index("token_hash", unique=True, sparse=True)
    await db.password_resets.create_index("user_id")
    await db.password_resets.create_index("expires_at", expireAfterSeconds=0)
    await db.email_verifications.create_index("token_hash", unique=True)
    await db.email_verifications.create_index("user_id")
    await db.email_verifications.create_index("expires_at", expireAfterSeconds=0)
    await db.email_failures.create_index([("created_at", -1)])
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