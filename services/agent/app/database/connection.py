"""
Database connection management for ARIS agent.
Handles PostgreSQL connections with async support.
"""

import os
import logging
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    create_async_engine, 
    AsyncSession, 
    async_sessionmaker,
    AsyncEngine
)
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import text
from .models import Base

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database connections and sessions for ARIS agent."""
    
    def __init__(self):
        self.engine: Optional[AsyncEngine] = None
        self.session_factory: Optional[async_sessionmaker] = None
        self._initialized = False
    
    async def initialize(
        self, 
        database_url: Optional[str] = None,
        pool_size: int = 10,
        max_overflow: int = 20,
        echo: bool = False
    ) -> None:
        """Initialize database connection and session factory."""
        
        if self._initialized:
            logger.warning("DatabaseManager already initialized")
            return
        
        # Get database URL from environment or parameter
        db_url = database_url or os.getenv('DATABASE_URL')
        if not db_url:
            raise ValueError("DATABASE_URL environment variable or database_url parameter required")
        
        # Replace ${DB_PASSWORD} placeholder with actual password from environment
        # ECS secrets are injected as environment variables but DATABASE_URL may contain placeholders
        if '${DB_PASSWORD}' in db_url:
            db_password = os.getenv('DB_PASSWORD')
            logger.info(f"🔐 Checking DB_PASSWORD: present={db_password is not None}, type={type(db_password).__name__}")
            if not db_password:
                logger.error("❌ DB_PASSWORD environment variable not found - secret may not be injected correctly")
                logger.error(f"❌ Available env vars containing 'DB' or 'PASSWORD': {[k for k in os.environ.keys() if 'DB' in k.upper() or 'PASSWORD' in k.upper()]}")
                raise ValueError("DB_PASSWORD environment variable required when using ${DB_PASSWORD} placeholder in DATABASE_URL")
            # URL-encode the password to handle special characters
            import urllib.parse
            encoded_password = urllib.parse.quote(db_password, safe='')
            db_url = db_url.replace('${DB_PASSWORD}', encoded_password)
            logger.info(f"✅ Replaced ${{DB_PASSWORD}} placeholder in DATABASE_URL (password length: {len(db_password)})")
        
        # Store db_url for table creation
        self._db_url = db_url
        
        # Parse additional configuration from environment
        pool_size = int(os.getenv('DATABASE_POOL_SIZE', pool_size))
        max_overflow = int(os.getenv('DATABASE_MAX_OVERFLOW', max_overflow))
        echo = os.getenv('DATABASE_ECHO', 'false').lower() == 'true' or echo
        
        logger.info(f"🔗 Initializing database connection to PostgreSQL")
        logger.info(f"📊 Database URL: {db_url}")
        logger.info(f"📊 Pool configuration: size={pool_size}, max_overflow={max_overflow}, echo={echo}")
        
        try:
            # Ensure we're using asyncpg driver
            if not db_url.startswith('postgresql+asyncpg://'):
                if db_url.startswith('postgresql://'):
                    db_url = db_url.replace('postgresql://', 'postgresql+asyncpg://', 1)
                    logger.info(f"🔄 Updated URL to use asyncpg driver: {db_url}")
            
            # Create async engine
            self.engine = create_async_engine(
                db_url,
                pool_size=pool_size,
                max_overflow=max_overflow,
                echo=echo,
                # Use NullPool for development to avoid connection issues
                poolclass=NullPool if echo else None,
                # Connection options for asyncpg
                connect_args={
                    "server_settings": {
                        "application_name": "aris_agent",
                        "jit": "off"  # Disable JIT for better cold start performance
                    }
                }
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            self._initialized = True
            
            # Create tables if they don't exist
            await self._create_tables_if_needed()
            
            # Test connection after initialization
            await self._test_connection()
            
            logger.info("✅ Database connection initialized successfully")
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize database connection: {str(e)}")
            raise
    
    async def _create_tables_if_needed(self) -> None:
        """Create database tables if they don't exist using asyncpg."""
        try:
            logger.info("🔨 Creating database tables if they don't exist...")
            # Use asyncpg directly to execute CREATE TABLE statements
            import asyncpg
            from urllib.parse import urlparse
            
            # Parse the database URL
            parsed = urlparse(self._db_url.replace('postgresql+asyncpg://', 'postgresql://'))
            
            # Connect using asyncpg
            conn = await asyncpg.connect(
                host=parsed.hostname,
                port=parsed.port or 5432,
                user=parsed.username,
                password=parsed.password,
                database=parsed.path.lstrip('/')
            )
            
            try:
                # Import all models to ensure they're registered with Base
                from .models import Chat, Plan, Action, SessionMemory
                
                # Use SQLAlchemy to generate CREATE TABLE statements
                # Use PostgreSQL dialect directly without creating an engine (avoids psycopg2 dependency)
                from sqlalchemy.schema import CreateTable
                from sqlalchemy.dialects import postgresql
                
                # Get PostgreSQL dialect for DDL generation (doesn't require psycopg2)
                dialect = postgresql.dialect()
                
                # Generate and execute CREATE TABLE statements
                for table in Base.metadata.sorted_tables:
                    # Check if table exists
                    exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = $1
                        )
                    """, table.name)
                    
                    if not exists:
                        # Generate CREATE TABLE statement using dialect directly
                        create_stmt = str(CreateTable(table).compile(dialect=dialect))
                        logger.info(f"Creating table: {table.name}")
                        await conn.execute(create_stmt)
                    else:
                        logger.debug(f"Table {table.name} already exists")
            finally:
                await conn.close()
            
            logger.info("✅ Database tables created/verified")
        except Exception as e:
            logger.error(f"❌ Could not create tables automatically: {str(e)}")
            # Re-raise to fail initialization - tables are required
            raise
    
    async def _test_connection(self) -> None:
        """Test database connection and verify schema."""
        try:
            async with self.get_session() as session:
                # Test basic connectivity
                result = await session.execute(text("SELECT 1"))
                assert result.scalar() == 1
                
                # Verify our tables exist
                result = await session.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name IN ('chats', 'plans', 'actions', 'session_memory')
                    ORDER BY table_name
                """))
                tables = [row[0] for row in result.fetchall()]
                expected_tables = ['actions', 'chats', 'plans', 'session_memory']
                
                if set(tables) != set(expected_tables):
                    missing = set(expected_tables) - set(tables)
                    logger.error(f"❌ Missing database tables: {missing}. Found: {tables}")
                    raise ValueError(f"Missing database tables. Expected: {expected_tables}, Found: {tables}")
                
                logger.info(f"✅ Database schema verified: {len(tables)} tables found")
                
        except Exception as e:
            logger.error(f"❌ Database connection test failed: {str(e)}")
            raise
    
    @asynccontextmanager
    async def get_session(self):
        """Get an async database session with automatic cleanup."""
        if not self._initialized:
            raise RuntimeError("DatabaseManager not initialized. Call initialize() first.")
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    async def close(self) -> None:
        """Close database connections and cleanup resources."""
        if self.engine:
            logger.info("🔒 Closing database connections")
            await self.engine.dispose()
            self.engine = None
            self.session_factory = None
            self._initialized = False
            logger.info("✅ Database connections closed")
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform database health check."""
        if not self._initialized:
            return {"status": "error", "message": "Database not initialized"}
        
        try:
            async with self.get_session() as session:
                # Check connectivity
                start_time = datetime.now()
                result = await session.execute(text("SELECT 1"))
                response_time = (datetime.now() - start_time).total_seconds() * 1000
                
                # Get basic stats
                stats_result = await session.execute(text("""
                    SELECT 
                        (SELECT COUNT(*) FROM chats WHERE status = 'active') as active_chats,
                        (SELECT COUNT(*) FROM plans WHERE status = 'in_progress') as active_plans,
                        (SELECT COUNT(*) FROM session_memory) as memory_items,
                        (SELECT pg_size_pretty(pg_database_size(current_database()))) as db_size
                """))
                stats = stats_result.fetchone()
                
                return {
                    "status": "healthy",
                    "response_time_ms": round(response_time, 2),
                    "active_chats": stats[0],
                    "active_plans": stats[1], 
                    "memory_items": stats[2],
                    "database_size": stats[3]
                }
                
        except Exception as e:
            logger.error(f"❌ Database health check failed: {str(e)}")
            return {
                "status": "error", 
                "message": str(e),
                "response_time_ms": None
            }


# Global database manager instance
db_manager = DatabaseManager()


# Helper functions for common operations
async def get_db_session():
    """Get a database session - use in dependency injection."""
    async with db_manager.get_session() as session:
        yield session


async def init_database(database_url: Optional[str] = None) -> DatabaseManager:
    """Initialize database connection and return manager instance."""
    await db_manager.initialize(database_url)
    return db_manager


async def close_database() -> None:
    """Close database connections."""
    await db_manager.close()
