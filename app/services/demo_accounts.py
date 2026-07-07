"""Demo 账号 / 店铺种子：报表配置按店铺隔离，账号可绑定多店铺。"""

from __future__ import annotations

import copy

from sqlalchemy.orm import Session

from app.models import Account, AccountStore, DataSource, FieldMapping, Store
from app.services.seed import MEICHONG_STORE, ensure_meichong_datasource
from app.services.store_clone import clone_catalog, clone_field_mappings

DEMO_STORE_B_NAME = "美宠Demo-欧洲区店铺"
DEMO_STORE_B_SOURCE = "美宠-欧洲区Demo店铺(TK-EU)"

DEMO_ACCOUNTS = [
    ("zhang", "张财务", [MEICHONG_STORE]),
    ("li", "李运营", [DEMO_STORE_B_NAME]),
    ("wang", "王主管", [MEICHONG_STORE, DEMO_STORE_B_NAME]),
]


def _ensure_store_b_datasource(db: Session, src_ds: DataSource) -> DataSource:
    from app.services.meichong_rules import MEICHONG_CONFIG as meichong_cfg

    existing = db.query(DataSource).filter(DataSource.name == DEMO_STORE_B_SOURCE).first()
    if existing:
        return existing

    cfg = copy.deepcopy(meichong_cfg)
    cfg["meta"] = {
        **(cfg.get("meta") or {}),
        "项目": "美宠",
        "平台": "TikTok",
        "区域": "欧洲",
        "店铺名称": DEMO_STORE_B_NAME,
    }
    ds = DataSource(
        name=DEMO_STORE_B_SOURCE,
        platform="TikTok Shop",
        description="Demo 第二店铺：欧洲区独立报表配置（Catalog/映射从美宠美区克隆，便于对比权限）",
        config=cfg,
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    clone_catalog(db, src_ds.id, ds.id)
    clone_field_mappings(db, src_ds.id, ds.id)

    # 标记差异：欧区店铺用不同指标名，便于 Demo 区分
    pay_line = (
        db.query(FieldMapping)
        .filter(FieldMapping.data_source_id == ds.id, FieldMapping.label == "应支付金额")
        .first()
    )
    if pay_line:
        pay_line.label = "应支付金额(欧区口径)"
        pay_line.description = "Demo：欧区店铺独立报表配置"
        db.commit()
    return ds


def _ensure_store_record(db: Session, name: str, platform: str, data_source_id: int) -> Store:
    store = db.query(Store).filter(Store.data_source_id == data_source_id).first()
    if store:
        store.name = name
        store.platform = platform
        db.commit()
        return store
    store = Store(name=name, platform=platform, data_source_id=data_source_id)
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
    src_ds = ensure_meichong_datasource(db)
    store_a = _ensure_store_record(db, MEICHONG_STORE, "TikTok Shop", src_ds.id)
    store_b_ds = _ensure_store_b_datasource(db, src_ds)
    store_b = _ensure_store_record(db, DEMO_STORE_B_NAME, "TikTok Shop", store_b_ds.id)

    stores_by_name = {store_a.name: store_a, store_b.name: store_b}

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

        allowed_ids = {stores_by_name[n].id for n in store_names if n in stores_by_name}
        for store_name in store_names:
            store = stores_by_name.get(store_name)
            if store:
                _link_account_store(db, account, store)

        # 移除 Demo 账号不再绑定的店铺
        for link in list(account.store_links):
            if link.store_id not in allowed_ids:
                db.delete(link)
        db.commit()
