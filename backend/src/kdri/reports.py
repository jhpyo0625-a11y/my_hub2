"""The SOLE accessor for `reports` and `chat_messages` (권한정책 TB-3).

Every read/write of user-owned report data goes through this module, keyed on
the caller's identity (session_key for anonymous, user_id later). A read of a
report the caller does not own returns None -> the API answers 404, not 403,
so a non-owner cannot even confirm the report exists.

No other module may issue `SELECT ... FROM reports/chat_messages`.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from kdri.db import ChatMessage, Report


def _owns(row: Report, session_key: Optional[str], user_id: Optional[int]) -> bool:
    if user_id is not None and row.user_id is not None:
        return row.user_id == user_id
    if session_key is not None and row.session_key is not None:
        return row.session_key == session_key
    return False


def create_report(
    session: Session,
    session_key: Optional[str],
    profile_json: dict,
    result_json: list,
    trace_json: dict,
    parent_id: Optional[int] = None,
    user_id: Optional[int] = None,
) -> Report:
    version = 1
    if parent_id is not None:
        parent = session.get(Report, parent_id)
        if parent is not None:
            version = parent.version + 1
    row = Report(
        user_id=user_id,
        session_key=session_key,
        version=version,
        parent_id=parent_id,
        profile_json=profile_json,
        result_json=result_json,
        trace_json=trace_json,
    )
    session.add(row)
    session.commit()
    return row


def get_report_owned(
    session: Session,
    report_id: int,
    session_key: Optional[str],
    user_id: Optional[int] = None,
) -> Optional[Report]:
    """Return the report only if the caller owns it, else None (=> 404)."""
    row = session.get(Report, report_id)
    if row is None or not _owns(row, session_key, user_id):
        return None
    return row


def delete_report(
    session: Session,
    report_id: int,
    session_key: Optional[str],
    user_id: Optional[int] = None,
) -> bool:
    """Delete an owned report. DB FKs cascade chat_messages and null children."""
    row = get_report_owned(session, report_id, session_key, user_id)
    if row is None:
        return False
    session.execute(delete(Report).where(Report.id == report_id))
    session.commit()
    return True


def list_reports(
    session: Session,
    session_key: Optional[str],
    user_id: Optional[int] = None,
) -> list[Report]:
    stmt = select(Report)
    if user_id is not None:
        stmt = stmt.where(Report.user_id == user_id)
    else:
        stmt = stmt.where(Report.session_key == session_key)
    stmt = stmt.order_by(Report.created_at.desc())
    return list(session.execute(stmt).scalars())


def add_chat_message(
    session: Session, report_id: int, role: str, content: str
) -> ChatMessage:
    msg = ChatMessage(report_id=report_id, role=role, content=content)
    session.add(msg)
    session.commit()
    return msg


def get_chat_messages(session: Session, report_id: int) -> list[ChatMessage]:
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.report_id == report_id)
        .order_by(ChatMessage.created_at)
    )
    return list(session.execute(stmt).scalars())
