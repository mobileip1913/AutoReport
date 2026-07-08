"""应用账号上下文：按店铺过滤可访问的数据源。"""

from __future__ import annotations

from fastapi import HTTPException, Request
from sqlalchemy.orm import Session, joinedload

from app.models import Account, AccountStore, DataSource, Store


def list_accounts(db: Session) -> list[Account]:
    return db.query(Account).order_by(Account.id).all()


def get_account(db: Session, account_id: int | None) -> Account | None:
    if not account_id:
        return None
    return db.query(Account).filter(Account.id == account_id).first()


def resolve_current_account(request: Request, db: Session) -> Account:
    del request
    account = db.query(Account).order_by(Account.id).first()
    if not account:
        raise HTTPException(status_code=503, detail="尚未初始化账号，请重启服务")
    return account


def stores_for_account(db: Session, account_id: int) -> list[Store]:
    return (
        db.query(Store)
        .join(AccountStore, AccountStore.store_id == Store.id)
        .filter(AccountStore.account_id == account_id)
        .options(joinedload(Store.data_source))
        .order_by(Store.id)
        .all()
    )


def resolve_current_store(request: Request, db: Session, account: Account) -> Store | None:
    del request
    stores = stores_for_account(db, account.id)
    return stores[0] if stores else None


def data_sources_for_account(db: Session, account_id: int) -> list[DataSource]:
    stores = stores_for_account(db, account_id)
    return [s.data_source for s in stores if s.data_source]


def allowed_data_source_ids(db: Session, account_id: int) -> set[int]:
    return {s.data_source_id for s in stores_for_account(db, account_id)}


def assert_data_source_access(request: Request, db: Session, data_source_id: int) -> None:
    account = resolve_current_account(request, db)
    if data_source_id not in allowed_data_source_ids(db, account.id):
        raise HTTPException(status_code=403, detail="无权访问该店铺的报表配置")


def assert_mapping_access(request: Request, db: Session, mapping) -> None:
    assert_data_source_access(request, db, mapping.data_source_id)


def page_context(request: Request, db: Session) -> dict:
    account = resolve_current_account(request, db)
    stores = stores_for_account(db, account.id)
    current_store = resolve_current_store(request, db, account)
    data_sources = [s.data_source for s in stores if s.data_source]
    return {
        "current_store": current_store,
        "accessible_stores": stores,
        "accessible_data_sources": data_sources,
    }
