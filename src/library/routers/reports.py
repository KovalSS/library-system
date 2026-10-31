"""Фіксований набір звітів і експорт у CSV (REQ-F-039...042)."""
import csv
import io
from collections import Counter
from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from library.circulation import fine_state, outstanding
from library.db import Account, Edition, Loan
from library.deps import STAFF_ROLES, get_clock, get_session, require, today
from library.errors import validation_failed
from library.schemas import iso, money

router = APIRouter()


def period(start: date = Query(alias="from"), end: date = Query(alias="to")) -> tuple[date, date]:
    """Період звіту, межі включно; `from` пізніше за `to` — помилка вхідних даних (адендум A13)."""
    if start > end:
        raise validation_failed("from", "Початок періоду пізніше за кінець.")
    return start, end


def respond(request: Request, report: dict, columns: list[str], rows: list[dict]):
    """JSON за замовчуванням; CSV з тими самими даними, якщо клієнт просить `text/csv` (REQ-F-042)."""
    if "text/csv" not in request.headers.get("accept", ""):
        return report
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return Response(content=buffer.getvalue(), media_type="text/csv")


@router.get("/reports/top-editions")
def top_editions(request: Request, bounds: tuple[date, date] = Depends(period),
                 limit: int = Query(default=10, ge=1, le=100),
                 session: Session = Depends(get_session), clock=Depends(get_clock), _=Depends(require(*STAFF_ROLES))):
    start, end = bounds
    issued = session.scalars(select(Loan.edition_id).where(Loan.issued_on >= start, Loan.issued_on <= end))
    counts = Counter(issued)
    editions = {e.id: e for e in session.scalars(select(Edition).where(Edition.id.in_(counts)))}
    ranked = sorted(counts.items(), key=lambda item: (-item[1], editions[item[0]].title))[:limit]
    items = [{"editionId": edition_id, "title": editions[edition_id].title, "author": editions[edition_id].author,
              "loansCount": count} for edition_id, count in ranked]
    report = {"from": start.isoformat(), "to": end.isoformat(), "generatedAt": iso(clock.now()), "items": items}
    return respond(request, report, ["editionId", "title", "author", "loansCount"], items)


@router.get("/reports/debtors")
def debtors(request: Request, session: Session = Depends(get_session), clock=Depends(get_clock),
            _=Depends(require(*STAFF_ROLES))):
    """Читачі з простроченою видачею та/або несплаченим штрафом на момент формування (REQ-F-040)."""
    on = today(clock)
    overdue_loans, debt = Counter(), {}
    for loan in session.scalars(select(Loan)):
        if loan.returned_on is None and fine_state(loan, on).overdue_days > 0:
            overdue_loans[loan.reader_id] += 1
        debt[loan.reader_id] = debt.get(loan.reader_id, Decimal("0")) + outstanding(loan, on)
    items = []
    for reader_id in sorted(set(overdue_loans) | {r for r, amount in debt.items() if amount > 0}):
        reader = session.get(Account, reader_id)
        items.append({"readerId": reader.id, "fullName": reader.full_name, "email": reader.email,
                      "phone": reader.phone, "overdueLoans": overdue_loans[reader_id],
                      "outstandingFine": money(debt.get(reader_id, Decimal("0")))})
    report = {"generatedAt": iso(clock.now()), "items": items}
    columns = ["readerId", "fullName", "email", "phone", "overdueLoans", "outstandingFine"]
    return respond(request, report, columns, items)


@router.get("/reports/library-load")
def library_load(request: Request, bounds: tuple[date, date] = Depends(period),
                 session: Session = Depends(get_session), clock=Depends(get_clock), _=Depends(require(*STAFF_ROLES))):
    start, end = bounds
    loans = session.scalars(select(Loan)).all()
    issued = sum(1 for loan in loans if start <= loan.issued_on <= end)
    returned = sum(1 for loan in loans if loan.returned_on and start <= loan.returned_on <= end)
    report = {"from": start.isoformat(), "to": end.isoformat(), "generatedAt": iso(clock.now()),
              "issuedCount": issued, "returnedCount": returned}
    row = {"from": report["from"], "to": report["to"], "issuedCount": issued, "returnedCount": returned}
    return respond(request, report, ["from", "to", "issuedCount", "returnedCount"], [row])
