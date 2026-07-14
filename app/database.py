from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine


def build_database(database_url: str) -> tuple[AsyncEngine, async_sessionmaker]:
    engine = create_async_engine(database_url, pool_pre_ping=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    return engine, session_factory

