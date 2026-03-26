"""SQLAlchemy models and database setup."""

import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, JSON, Enum as SAEnum, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, sessionmaker
import enum

from config import get_settings


# --- Enums ---

class TaskStatus(str, enum.Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_FOR_HUMAN = "waiting_for_human"
    COMPLETED = "completed"
    FAILED = "failed"


# --- Base ---

class Base(DeclarativeBase):
    pass


# --- Models ---

class TaskModel(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title = Column(String(500), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(SAEnum(TaskStatus), default=TaskStatus.QUEUED, nullable=False)
    assigned_agent = Column(String(100), nullable=True)
    result = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    human_input_request = Column(Text, nullable=True)
    human_input_response = Column(Text, nullable=True)
    thread_id = Column(String(100), nullable=True)  # LangGraph thread ID
    metadata_json = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ActionLogModel(Base):
    __tablename__ = "action_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    task_id = Column(String, nullable=False, index=True)
    agent_name = Column(String(100), nullable=True)
    action = Column(String(200), nullable=False)
    detail = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class MCPServerModel(Base):
    __tablename__ = "mcp_servers"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, unique=True, index=True)
    transport = Column(String(50), nullable=False, default="stdio")
    command = Column(String(500), nullable=False)
    args = Column(Text, nullable=False, default="")
    env_json = Column(JSON, default=list)
    status = Column(String(50), nullable=False, default="configured")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class AgentProfileModel(Base):
    __tablename__ = "agent_profiles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(200), nullable=False, unique=True, index=True)
    role = Column(String(300), nullable=False)
    system_prompt = Column(Text, nullable=False)
    model = Column(String(120), nullable=False, default="gpt-5-mini")
    temperature = Column(String(20), nullable=False, default="0.2")
    tools_json = Column(JSON, default=list)
    status = Column(String(50), nullable=False, default="configured")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc),
                        onupdate=lambda: datetime.now(timezone.utc))


class ChatMessageModel(Base):
    __tablename__ = "chat_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    thread_id = Column(String(200), nullable=False, index=True)
    role = Column(String(20), nullable=False)  # user | agent | system
    content = Column(Text, nullable=False)
    agent_name = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)


# --- Engine & Session ---

settings = get_settings()

async_engine = create_async_engine(settings.database_url, echo=False)
async_session_factory = async_sessionmaker(async_engine, class_=AsyncSession, expire_on_commit=False)

sync_engine = create_engine(settings.database_url_sync, echo=False)
sync_session_factory = sessionmaker(bind=sync_engine)


async def init_db():
    """Create all tables."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for FastAPI."""
    async with async_session_factory() as session:
        yield session
