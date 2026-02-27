import asyncpg
import logging
from config import DATABASE_URL

logger = logging.getLogger("prism.database")

# Connection pool setup
pool = None

async def get_pool():
    global pool
    if not pool:
        pool = await asyncpg.create_pool(DATABASE_URL)
    return pool

async def init_db():
    p = await get_pool()
    async with p.acquire() as conn:
        # Create users table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                role TEXT DEFAULT 'user',
                tier TEXT DEFAULT 'free',
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            )
        ''')
        
        # Create usage_logs table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS usage_logs (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

async def get_db():
    global pool
    if not pool:
        pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        yield conn

# Helper queries
async def get_user_by_email(email: str):
    global pool
    if not pool: pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
        return dict(row) if row else None

async def get_user_by_id(user_id: str):
    global pool
    if not pool: pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None

async def log_usage(user_id: str, endpoint: str):
    global pool
    if not pool: pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO usage_logs (user_id, endpoint) VALUES ($1, $2)",
            user_id, endpoint
        )

async def get_today_usage(user_id: str, endpoint: str) -> int:
    global pool
    if not pool: pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        count = await conn.fetchval('''
            SELECT COUNT(*) 
            FROM usage_logs 
            WHERE user_id = $1 
              AND endpoint = $2 
              AND created_at::date = CURRENT_DATE
        ''', user_id, endpoint)
        return count if count else 0

async def get_user_count() -> int:
    global pool
    if not pool: pool = await asyncpg.create_pool(DATABASE_URL)
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")
