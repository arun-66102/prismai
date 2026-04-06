import asyncpg
import logging
from config import DATABASE_URL

logger = logging.getLogger("prism.database")

# Connection pool setup
pool = None

async def get_pool():
    global pool
    if not pool:
        if not DATABASE_URL:
            logger.error("DATABASE_URL is not set!")
            return None
        try:
            pool = await asyncpg.create_pool(DATABASE_URL)
        except Exception as e:
            logger.error(f"Failed to create database pool: {e}")
            return None
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

        # Create generation_history table
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS generation_history (
                id SERIAL PRIMARY KEY,
                user_id TEXT NOT NULL,
                gen_type TEXT NOT NULL,
                input_params JSONB NOT NULL,
                output_data TEXT,
                image_urls TEXT[],
                image_prompt TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')

async def get_db():
    p = await get_pool()
    if not p:
        raise Exception("Database connection pool is unavailable. Check DATABASE_URL and database status.")
    async with p.acquire() as conn:
        yield conn

# Helper queries
async def get_user_by_email(email: str):
    p = await get_pool()
    if not p:
        raise Exception("Database pool is unavailable.")
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE email = $1", email)
        return dict(row) if row else None

async def get_user_by_id(user_id: str):
    p = await get_pool()
    if not p:
        raise Exception("Database pool is unavailable.")
    async with p.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM users WHERE id = $1", user_id)
        return dict(row) if row else None

async def log_usage(user_id: str, endpoint: str):
    p = await get_pool()
    if not p:
        logger.error("Database pool is unavailable. Cannot log usage.")
        return
    async with p.acquire() as conn:
        await conn.execute(
            "INSERT INTO usage_logs (user_id, endpoint) VALUES ($1, $2)",
            user_id, endpoint
        )

async def get_today_usage(user_id: str, endpoint: str) -> int:
    p = await get_pool()
    if not p:
        logger.error("Database pool is unavailable. Defaulting to 0 usage.")
        return 0
    async with p.acquire() as conn:
        count = await conn.fetchval('''
            SELECT COUNT(*) 
            FROM usage_logs 
            WHERE user_id = $1 
              AND endpoint = $2 
              AND created_at::date = CURRENT_DATE
        ''', user_id, endpoint)
        return count if count else 0

async def get_total_usage(user_id: str, endpoint: str) -> int:
    p = await get_pool()
    if not p:
        logger.error("Database pool is unavailable. Defaulting to 0 usage.")
        return 0
    async with p.acquire() as conn:
        count = await conn.fetchval('''
            SELECT COUNT(*) 
            FROM usage_logs 
            WHERE user_id = $1 
              AND endpoint = $2
        ''', user_id, endpoint)
        return count if count else 0

async def get_user_count() -> int:
    p = await get_pool()
    if not p:
        raise Exception("Database pool is unavailable.")
    async with p.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")

# ─── Generation History ──────────────────────────────────────────────────────
import json

async def save_generation(user_id: str, gen_type: str, input_params: dict,
                          output_data: str = None, image_urls: list = None,
                          image_prompt: str = None):
    p = await get_pool()
    if not p:
        logger.error("Database pool is unavailable. Cannot save generation history.")
        return
    async with p.acquire() as conn:
        await conn.execute('''
            INSERT INTO generation_history (user_id, gen_type, input_params, output_data, image_urls, image_prompt)
            VALUES ($1, $2, $3::jsonb, $4, $5, $6)
        ''', user_id, gen_type, json.dumps(input_params), output_data, image_urls, image_prompt)

def _normalize_history_row(row_dict):
    """Ensure input_params is a dict (asyncpg may return JSONB as string)."""
    d = dict(row_dict)
    if isinstance(d.get("input_params"), str):
        try:
            d["input_params"] = json.loads(d["input_params"])
        except (json.JSONDecodeError, TypeError):
            d["input_params"] = {}
    return d

async def get_user_history(user_id: str, gen_type: str = None, limit: int = 20, offset: int = 0):
    p = await get_pool()
    if not p:
        raise Exception("Database pool is unavailable.")
    async with p.acquire() as conn:
        if gen_type:
            rows = await conn.fetch('''
                SELECT id, gen_type, input_params, output_data, image_urls, image_prompt, created_at
                FROM generation_history
                WHERE user_id = $1 AND gen_type = $2
                ORDER BY created_at DESC
                LIMIT $3 OFFSET $4
            ''', user_id, gen_type, limit, offset)
        else:
            rows = await conn.fetch('''
                SELECT id, gen_type, input_params, output_data, image_urls, image_prompt, created_at
                FROM generation_history
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT $2 OFFSET $3
            ''', user_id, limit, offset)
        return [_normalize_history_row(r) for r in rows]

async def get_history_item(history_id: int, user_id: str):
    p = await get_pool()
    if not p:
        raise Exception("Database pool is unavailable.")
    async with p.acquire() as conn:
        row = await conn.fetchrow('''
            SELECT id, gen_type, input_params, output_data, image_urls, image_prompt, created_at
            FROM generation_history
            WHERE id = $1 AND user_id = $2
        ''', history_id, user_id)
        return _normalize_history_row(row) if row else None

async def delete_history_item(history_id: int, user_id: str) -> bool:
    p = await get_pool()
    if not p:
        raise Exception("Database pool is unavailable.")
    async with p.acquire() as conn:
        result = await conn.execute('''
            DELETE FROM generation_history
            WHERE id = $1 AND user_id = $2
        ''', history_id, user_id)
        return result == "DELETE 1"

async def delete_all_history(user_id: str):
    p = await get_pool()
    if not p:
        raise Exception("Database pool is unavailable.")
    async with p.acquire() as conn:
        await conn.execute('''
            DELETE FROM generation_history WHERE user_id = $1
        ''', user_id)

async def get_history_count(user_id: str, gen_type: str = None) -> int:
    p = await get_pool()
    if not p:
        return 0
    async with p.acquire() as conn:
        if gen_type:
            count = await conn.fetchval('''
                SELECT COUNT(*) FROM generation_history WHERE user_id = $1 AND gen_type = $2
            ''', user_id, gen_type)
        else:
            count = await conn.fetchval('''
                SELECT COUNT(*) FROM generation_history WHERE user_id = $1
            ''', user_id)
        return count if count else 0
