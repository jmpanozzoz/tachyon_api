"""Canonical PostgreSQL starter templates; optional packages are never imported here."""

DATABASE = r'''"""Application engine, one session per request or independent worker task."""
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from starlette.requests import Request


def database(url):
    engine = create_async_engine(url, pool_size=5, max_overflow=5, pool_timeout=3,
                                 connect_args={"timeout": 3, "command_timeout": 5})
    return engine, async_sessionmaker(engine, expire_on_commit=False)


async def get_session(request: Request):
    async with request.app.state.sessions() as session:
        # Services commit before returning success. Exit rolls back pending work.
        yield session
'''

APP = r'''"""PostgreSQL starter: lifespan engine, request sessions, commit before success."""
from contextlib import asynccontextmanager
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from tachyon_api import Body, Depends, Struct, Tachyon
from config import settings
from shared.database import database, get_session
from shared.models import Note


@asynccontextmanager
async def lifespan(app):
    engine, sessions = database(settings.DATABASE_URL)
    app.state.sessions = sessions
    try:
        yield
    finally:
        await engine.dispose()


app = Tachyon(lifespan=lifespan)


class NoteInput(Struct):
    name: str


class NoteOutput(Struct):
    id: str
    name: str


@app.get("/")
async def root():
    return {"status": "ok", "app": settings.APP_NAME}


@app.get("/health/ready")
async def ready(session: AsyncSession = Depends(get_session)):
    await session.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.post("/notes", response_model=NoteOutput)
async def create_note(data: NoteInput = Body(...), session: AsyncSession = Depends(get_session)):
    from tachyon_api import HTTPException
    if not 1 <= len(data.name) <= 120:
        raise HTTPException(422, "name must contain 1 to 120 characters")
    note = Note(name=data.name)
    session.add(note)
    await session.commit()
    return NoteOutput(id=note.id, name=note.name)


@app.get("/notes", response_model=list[NoteOutput])
async def list_notes(session: AsyncSession = Depends(get_session)):
    notes = (await session.scalars(select(Note).order_by(Note.id).limit(100))).all()
    return [NoteOutput(id=note.id, name=note.name) for note in notes]
'''

MODELS = r'''"""Example persistence. Replace the domain model for your application."""
from uuid import uuid4
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=lambda: uuid4().hex)
    name: Mapped[str] = mapped_column(String(120))
'''

MIGRATION_ENV = r'''import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from config import settings
from shared.models import Base


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


async def online():
    engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    context.configure(url=settings.DATABASE_URL, target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    asyncio.run(online())
'''

MIGRATION = r'''"""Initial starter schema; review migrations before applying them."""
from alembic import op
import sqlalchemy as sa
revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("notes", sa.Column("id", sa.String(32), primary_key=True), sa.Column("name", sa.String(120), nullable=False))


def downgrade():
    raise RuntimeError("Use a data-preserving restore procedure; do not drop notes implicitly")
'''

README = r'''# PostgreSQL starter

This project uses a development capability added after Tachyon 1.4.3.
Install the matching candidate wheel before its requirements until 1.5 is published.

1. Create a virtual environment and install `requirements.txt`.
2. Set DATABASE_URL to your disposable development PostgreSQL database using `postgresql+asyncpg://`.
3. Run `alembic upgrade head` once before starting HTTP workers.
4. Run `tachyon doctor --app app:app` and optionally `tachyon doctor --connect`.
5. Run `pytest tests/`, then `tachyon run`.
6. POST `/notes` with `{"name":"example"}` and GET `/notes`.

This starter intentionally has no authentication; run it locally until adding
application authorization. It is not the full KYC reference. `generate` continues
to produce its documented in-memory modules; adapt repositories explicitly.
The engine is owned by lifespan; sessions belong to requests. Services must commit
before returning success. Do not share a session across tasks or background jobs.
Alembic owns migrations, Uvicorn owns serving. Back up data before schema changes.
'''
