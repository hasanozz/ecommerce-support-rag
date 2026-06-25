from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Message, Ticket, TicketStatusHistory, User
from ..schemas.ticket import AdminTicketUpdate, TicketCreateRequest, TicketResponse
from ..services.auth import get_current_user, require_admin
from ..services.email import EmailService, process_outbox_once
from ..services.tickets import TicketService


router = APIRouter(prefix="/api", tags=["tickets"])


def ticket_response(ticket: Ticket) -> TicketResponse:
    return TicketResponse(
        id=ticket.id,
        conversation_id=ticket.conversation_id,
        source_message_id=ticket.source_message_id,
        category=ticket.category,
        department=ticket.department,
        status=ticket.status,
        user_note=ticket.user_note,
        admin_note=ticket.admin_note,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


@router.post("/messages/{message_id}/ticket", response_model=TicketResponse)
async def create_ticket_from_message(
    message_id: int,
    payload: TicketCreateRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TicketResponse:
    message = await session.scalar(
        select(Message).where(
            Message.id == message_id,
            Message.role == "ASSISTANT",
            Message.conversation.has(user_id=user.id),
        )
    )
    if message is None:
        raise HTTPException(404, "Cevap bulunamadı.")
    ticket = await TicketService().create(
        session, user, message, payload.note.strip()
    )
    await session.commit()
    await session.refresh(ticket)
    background_tasks.add_task(process_outbox_once)
    return ticket_response(ticket)


@router.get("/tickets", response_model=list[TicketResponse])
async def user_tickets(
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[TicketResponse]:
    tickets = (
        await session.scalars(
            select(Ticket)
            .where(Ticket.user_id == user.id)
            .order_by(Ticket.updated_at.desc())
        )
    ).all()
    return [ticket_response(item) for item in tickets]


@router.get("/tickets/{ticket_id}", response_model=TicketResponse)
async def user_ticket(
    ticket_id: int,
    session: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> TicketResponse:
    ticket = await session.scalar(
        select(Ticket).where(Ticket.id == ticket_id, Ticket.user_id == user.id)
    )
    if ticket is None:
        raise HTTPException(404, "Ticket bulunamadı.")
    return ticket_response(ticket)


@router.get("/admin/tickets", response_model=list[TicketResponse])
async def admin_tickets(
    status: str | None = None,
    session: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
) -> list[TicketResponse]:
    statement = select(Ticket).order_by(Ticket.updated_at.desc())
    if status:
        statement = statement.where(Ticket.status == status)
    tickets = (await session.scalars(statement)).all()
    return [ticket_response(item) for item in tickets]


@router.patch("/admin/tickets/{ticket_id}", response_model=TicketResponse)
async def update_ticket(
    ticket_id: int,
    payload: AdminTicketUpdate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
) -> TicketResponse:
    ticket = await session.get(Ticket, ticket_id)
    if ticket is None:
        raise HTTPException(404, "Ticket bulunamadı.")
    old_status = ticket.status
    ticket.status = payload.status
    ticket.admin_note = payload.admin_note.strip()
    session.add(
        TicketStatusHistory(
            ticket_id=ticket.id,
            changed_by_user_id=admin.id,
            old_status=old_status,
            new_status=ticket.status,
            note=ticket.admin_note,
        )
    )
    user = await session.get(User, ticket.user_id)
    if user:
        await EmailService().queue(
            session,
            user.email,
            f"Destek talebiniz güncellendi #{ticket.id}",
            f"Destek talebinizin yeni durumu: {ticket.status}.",
        )
    await session.commit()
    await session.refresh(ticket)
    background_tasks.add_task(process_outbox_once)
    return ticket_response(ticket)
