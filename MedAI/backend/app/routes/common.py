from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


class Pagination:
    def __init__(self, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        self.limit = limit
        self.offset = offset


def paginate(db: Session, stmt: Select, page: Pagination) -> tuple[list, int]:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    items = list(db.scalars(stmt.limit(page.limit).offset(page.offset)).unique())
    return items, total
