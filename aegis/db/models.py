"""ORM models: Tenant, Conversation, Message, Receipt."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from aegis.db.base import Base, TimestampMixin, new_uuid


class Tenant(Base, TimestampMixin):
    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    ens_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    registry_addr: Mapped[str | None] = mapped_column(String(64), nullable=True)

    conversations: Mapped[list[Conversation]] = relationship(
        back_populates="tenant",
        cascade="all, delete-orphan",
    )


class Conversation(Base, TimestampMixin):
    __tablename__ = "conversations"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    tenant_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    channel: Mapped[str | None] = mapped_column(String(32), nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="conversations")
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.created_at",
    )


class Message(Base, TimestampMixin):
    __tablename__ = "messages"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    conversation_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")
    receipt: Mapped[Receipt | None] = relationship(
        back_populates="message",
        cascade="all, delete-orphan",
        uselist=False,
    )


class Receipt(Base, TimestampMixin):
    __tablename__ = "receipts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=new_uuid)
    message_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("messages.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
    )
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    model_id: Mapped[str] = mapped_column(String(64), nullable=False)
    retrieval_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    tools_used: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)

    message: Mapped[Message] = relationship(back_populates="receipt")
