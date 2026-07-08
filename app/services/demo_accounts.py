"""Demo 账号 / 店铺种子：仅保留美宠真实店铺。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import (
    Account,
    AccountStore,
    CatalogColumn,
    CatalogFile,
    CatalogSheet,
    DataImport,
    DataRow,
    DataSource,
    EtlBatch,
    FieldMapping,
    FieldMappingPart,
    MappingLog,
    ReportRun,
    ReportValue,
    Store,
)
from app.services.meichong_rules import MEICHONG_CONFIG
from app.services.production_store import production_store_table_exists, sync_store_production_ids
from app.services.seed import MEICHONG_STORE, ensure_meichong_datasource

# 已废弃的 Demo 欧区店（启动时自动清理）
LEGACY_DEMO_STORE_B_NAME = "美宠Demo-欧洲区店铺"
LEGACY_DEMO_STORE_B_SOURCE = "美宠-欧洲区Demo店铺(TK-EU)"

DEMO_ACCOUNTS = [
    ("zhang", "张财务", [MEICHONG_STORE]),
    ("li", "李运营", [MEICHONG_STORE]),
    ("wang", "王主管", [MEICHONG_STORE]),
]


def _remove_legacy_demo_store_b(db: Session) -> None:
    """删除已存在的 Demo 欧区数据源、店铺及关联配置。"""
    ds = db.query(DataSource).filter(DataSource.name == LEGACY_DEMO_STORE_B_SOURCE).first()
    if not ds:
        return

    ds_id = ds.id
    mapping_ids = [m.id for m in db.query(FieldMapping).filter(FieldMapping.data_source_id == ds_id).all()]
    if mapping_ids:
        db.query(ReportValue).filter(ReportValue.mapping_id.in_(mapping_ids)).update(
            {ReportValue.mapping_id: None}, synchronize_session=False
        )

    run_ids = [r.id for r in db.query(ReportRun).filter(ReportRun.data_source_id == ds_id).all()]
    if run_ids:
        db.query(ReportValue).filter(ReportValue.report_run_id.in_(run_ids)).delete(synchronize_session=False)
        db.query(ReportRun).filter(ReportRun.id.in_(run_ids)).delete(synchronize_session=False)

    for m in db.query(FieldMapping).filter(FieldMapping.data_source_id == ds_id).all():
        db.query(FieldMappingPart).filter(FieldMappingPart.mapping_id == m.id).delete(synchronize_session=False)
        db.delete(m)

    file_ids = [f.id for f in db.query(CatalogFile).filter(CatalogFile.data_source_id == ds_id).all()]
    if file_ids:
        sheet_ids = [
            s.id
            for s in db.query(CatalogSheet).filter(CatalogSheet.file_id.in_(file_ids)).all()
        ]
        if sheet_ids:
            db.query(CatalogColumn).filter(CatalogColumn.sheet_id.in_(sheet_ids)).delete(synchronize_session=False)
            db.query(CatalogSheet).filter(CatalogSheet.id.in_(sheet_ids)).delete(synchronize_session=False)
        db.query(CatalogFile).filter(CatalogFile.id.in_(file_ids)).delete(synchronize_session=False)

    db.query(EtlBatch).filter(EtlBatch.data_source_id == ds_id).delete(synchronize_session=False)

    imports = db.query(DataImport).filter(DataImport.data_source_id == ds_id).all()
    import_ids = [i.id for i in imports]
    if import_ids:
        db.query(DataRow).filter(DataRow.data_import_id.in_(import_ids)).delete(synchronize_session=False)
        db.query(MappingLog).filter(MappingLog.data_import_id.in_(import_ids)).delete(synchronize_session=False)
    for imp in imports:
        db.delete(imp)

    store = db.query(Store).filter(Store.data_source_id == ds_id).first()
    if store:
        db.query(AccountStore).filter(AccountStore.store_id == store.id).delete(synchronize_session=False)
        db.delete(store)

    db.delete(ds)
    db.commit()


def _ensure_store_record(
    db: Session,
    name: str,
    platform: str,
    data_source_id: int,
    *,
    production_store_id: int | None = None,
    shop_code: str | None = None,
) -> Store:
    store = db.query(Store).filter(Store.data_source_id == data_source_id).first()
    if store:
        store.name = name
        store.platform = platform
        if production_store_id is not None:
            store.production_store_id = production_store_id
        if shop_code is not None:
            store.shop_code = shop_code
        db.commit()
        return store
    store = Store(
        name=name,
        platform=platform,
        data_source_id=data_source_id,
        production_store_id=production_store_id,
        shop_code=shop_code,
    )
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


def _link_account_store(db: Session, account: Account, store: Store) -> None:
    exists = (
        db.query(AccountStore)
        .filter(AccountStore.account_id == account.id, AccountStore.store_id == store.id)
        .first()
    )
    if not exists:
        db.add(AccountStore(account_id=account.id, store_id=store.id))
        db.commit()


def ensure_demo_accounts(db: Session) -> None:
    _remove_legacy_demo_store_b(db)

    src_ds = ensure_meichong_datasource(db)
    cfg = MEICHONG_CONFIG
    store = _ensure_store_record(
        db,
        MEICHONG_STORE,
        "TikTok Shop",
        src_ds.id,
        production_store_id=cfg.get("production_store_id"),
        shop_code=cfg.get("shop_code"),
    )
    if production_store_table_exists():
        sync_store_production_ids(db)

    for login_name, display_name, store_names in DEMO_ACCOUNTS:
        account = db.query(Account).filter(Account.login_name == login_name).first()
        if not account:
            account = Account(login_name=login_name, display_name=display_name)
            db.add(account)
            db.commit()
            db.refresh(account)
        else:
            account.display_name = display_name
            db.commit()

        allowed_ids = {store.id} if MEICHONG_STORE in store_names else set()
        for store_name in store_names:
            if store_name == MEICHONG_STORE:
                _link_account_store(db, account, store)

        for link in list(account.store_links):
            if link.store_id not in allowed_ids:
                db.delete(link)
        db.commit()
