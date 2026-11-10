"""Штрафи читача та реєстрація оплати повної суми (REQ-F-030, 031)."""
import logging
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from library import audit
from library.access import readable_reader
from library.circulation import fine_state, outstanding
from library.db import Account, Edition, FinePayment, Loan, to_db
from library.deps import current_account, get_clock, get_or_404, get_session, require, today
from library.errors import ApiError
from library.logging_setup import LOGGER_NAME
from library.schemas import FinePaymentCreate, iso, money

router = APIRouter()
fines_log = logging.getLogger(f"{LOGGER_NAME}.fines")


def loans_with_fines(session: Session, reader_id: str, on) -> list[Loan]:
    """Повертає список видач читача, за якими є нарахований штраф."""
    loans = session.scalars(select(Loan).where(Loan.reader_id == reader_id).order_by(Loan.issued_on))
    return [loan for loan in loans if fine_state(loan, on).amount > 0]


@router.get("/readers/{reader_id}/fines")
def get_reader_fines(reader_id: str, session: Session = Depends(get_session), clock=Depends(get_clock),
                     viewer: Account = Depends(current_account)):
    """Отримує детальну інформацію про всі штрафи читача та загальну суму боргу (REQ-F-030)."""
    readable_reader(session, viewer, reader_id)
    on = today(clock)
    items = []
    for loan in loans_with_fines(session, reader_id, on):
        amount = fine_state(loan, on).amount
        items.append({"loanId": loan.id, "editionTitle": session.get(Edition, loan.edition_id).title,
                      "fineAmount": money(amount), "paidAmount": money(loan.fine_paid),
                      "outstandingAmount": money(amount - loan.fine_paid)})
    total = sum((outstanding(loan, on) for loan in loans_with_fines(session, reader_id, on)), Decimal("0"))
    return {"readerId": reader_id, "currency": "UAH", "totalOutstanding": money(total), "items": items}


@router.post("/readers/{reader_id}/fine-payments", status_code=201)
def pay_reader_fines(reader_id: str, body: FinePaymentCreate, session: Session = Depends(get_session),
                     clock=Depends(get_clock), actor: Account = Depends(require("librarian"))):
    """Реєструє повну оплату заборгованості читача зі штрафів бібліотекарем (REQ-F-030, REQ-F-031)."""
    get_or_404(session, Account, reader_id, lambda a: a.role == "reader")
    on = today(clock)
    loans = [loan for loan in loans_with_fines(session, reader_id, on) if outstanding(loan, on) > 0]
    if not loans:
        fines_log.warning("Відмова в оплаті: у читача %s немає несплаченого штрафу", reader_id)
        raise ApiError(409, "no_outstanding_fine", "Несплачених штрафів немає.")
    # Часткова оплата не підтримується: сплачується вся поточна заборгованість (REQ-F-030).
    total = sum((outstanding(loan, on) for loan in loans), Decimal("0"))
    for loan in loans:
        loan.fine_paid = fine_state(loan, on).amount
    payment = FinePayment(reader_id=reader_id, method=body.method, amount=total, paid_at=to_db(clock.now()))
    session.add(payment)
    audit.record(session, clock, actor, "fine.paid", "fine_payment", payment)
    session.commit()
    return {"id": payment.id, "readerId": reader_id, "method": payment.method, "amount": money(total),
            "currency": "UAH", "paidAt": iso(payment.paid_at)}
