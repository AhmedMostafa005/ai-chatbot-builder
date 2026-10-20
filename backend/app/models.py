import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Boolean, JSON, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector
from app.db import Base

class Bot(Base):
    __tablename__ = "bots"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(200))
    model: Mapped[str] = mapped_column(String(200), default="models/gemini-2.5-flash")
    system_prompt: Mapped[str] = mapped_column(Text, default="Answer accurately using the provided knowledge when relevant. If unsure, say so.")
    welcome_message: Mapped[str] = mapped_column(Text, default="Hello! How can I help?")
    primary_color: Mapped[str] = mapped_column(String(20), default="#2563eb")
    allowed_domains: Mapped[list] = mapped_column(JSON, default=list)
    published: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    documents: Mapped[list["Document"]] = relationship(back_populates="bot", cascade="all, delete-orphan")

class Document(Base):
    __tablename__ = "documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(30), default="processed")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    bot: Mapped[Bot] = relationship(back_populates="documents")

class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"), index=True)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Vector(384))
    chunk_index: Mapped[int] = mapped_column(Integer)

class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id: Mapped[str] = mapped_column(String(128), index=True)
    bot_id: Mapped[str] = mapped_column(ForeignKey("bots.id", ondelete="CASCADE"), index=True)
    visitor_id: Mapped[str] = mapped_column(String(128), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")

class Message(Base):
    __tablename__ = "messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    conversation: Mapped[Conversation] = relationship(back_populates="messages")
