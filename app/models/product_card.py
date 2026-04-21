from sqlalchemy import Column, Integer, String, Float, Text

from app.database.connection import Base


class ProductCard(Base):
    """
    Денормализованная карточка товара: одна строка на логический товар.

    Собирается из таблицы products (которая хранит по строке на (id, region)) —
    здесь UA/TR/IN поля находятся на одной строке, что позволяет каталогу
    отдавать карточки без GROUP BY.

    Покупки, избранное и cross-region resolver продолжают использовать
    таблицу products(id, region). Эта таблица — только для выдачи каталога.
    """

    __tablename__ = "product_cards"

    # group_key — обычно равен product.id, потому что у одного товара одинаковый
    # PPSA-идентификатор во всех регионах. Для редких случаев разных PPSA
    # (например Valhalla IN=PPSA01490 vs UA/TR=PPSA01532) group_key выбирается
    # по приоритету UA→TR→IN, чтобы карточка имела стабильный идентификатор.
    card_id = Column(Text, primary_key=True, comment="Идентификатор карточки (обычно = product.id)")

    # Общая информация (берётся с представителя по приоритету региона)
    name = Column(Text, nullable=True, index=True)
    main_name = Column(Text, nullable=True, index=True)
    search_names = Column(Text, nullable=True)
    sort_name = Column(Text, nullable=True, index=True, comment="lower(coalesce(main_name, name, id))")
    image = Column(Text, nullable=True)
    category = Column(Text, nullable=True, index=True)
    type = Column(Text, nullable=True)
    platforms = Column(Text, nullable=True)
    publisher = Column(Text, nullable=True)
    edition = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    info = Column(Text, nullable=True)
    compound = Column(Text, nullable=True)
    tags = Column(Text, nullable=True)
    rating = Column(Float, nullable=True)
    release_date = Column(Text, nullable=True, index=True)
    added_at = Column(Text, nullable=True, index=True)
    players_min = Column(Integer, nullable=True)
    players_max = Column(Integer, nullable=True)
    players_online = Column(Integer, nullable=True)

    # Лучшая локализация среди регионов (full → subtitles → interface → none)
    best_localization = Column(Text, nullable=True, index=True)

    # Подписки / промо (общие для всех регионов)
    ps_plus_collection = Column(Text, nullable=True, index=True)
    ea_access = Column(Text, nullable=True, index=True)

    # Агрегированные предвычисленные поля (для ORDER BY и фильтров каталога)
    min_price_rub = Column(Float, nullable=True, index=True)
    min_price_region = Column(Text, nullable=True)
    min_old_price_rub = Column(Float, nullable=True)
    max_discount_percent = Column(Integer, nullable=True, index=True)
    has_discount = Column(Integer, nullable=True, index=True, comment="0/1")
    has_ps_plus = Column(Integer, nullable=True, index=True, comment="0/1")
    has_ea_access = Column(Integer, nullable=True, index=True, comment="0/1")
    regions_mask = Column(Integer, nullable=True, comment="битовая маска: 1=UA, 2=TR, 4=IN")

    favorites_count = Column(Integer, nullable=True, index=True, server_default="0")

    # ── UA регион ─────────────────────────────────────────────────────────────
    ua_product_id = Column(Text, nullable=True, index=True)
    ua_localization = Column(Text, nullable=True)
    ua_price_uah = Column(Float, nullable=True)
    ua_old_price_uah = Column(Float, nullable=True)
    ua_price_rub = Column(Float, nullable=True)
    ua_old_price_rub = Column(Float, nullable=True)
    ua_ps_plus_price_uah = Column(Float, nullable=True)
    ua_ps_plus_price_rub = Column(Float, nullable=True)
    ua_discount_percent = Column(Integer, nullable=True)
    ua_has_discount = Column(Integer, nullable=True, comment="0/1")
    ua_discount_end = Column(Text, nullable=True)
    ua_ps_plus = Column(Integer, nullable=True)

    # ── TR регион ─────────────────────────────────────────────────────────────
    tr_product_id = Column(Text, nullable=True, index=True)
    tr_localization = Column(Text, nullable=True)
    tr_price_try = Column(Float, nullable=True)
    tr_old_price_try = Column(Float, nullable=True)
    tr_price_rub = Column(Float, nullable=True)
    tr_old_price_rub = Column(Float, nullable=True)
    tr_ps_plus_price_try = Column(Float, nullable=True)
    tr_ps_plus_price_rub = Column(Float, nullable=True)
    tr_discount_percent = Column(Integer, nullable=True)
    tr_has_discount = Column(Integer, nullable=True, comment="0/1")
    tr_discount_end = Column(Text, nullable=True)
    tr_ps_plus = Column(Integer, nullable=True)

    # ── IN регион ─────────────────────────────────────────────────────────────
    in_product_id = Column(Text, nullable=True, index=True)
    in_localization = Column(Text, nullable=True)
    in_price_inr = Column(Float, nullable=True)
    in_old_price_inr = Column(Float, nullable=True)
    in_price_rub = Column(Float, nullable=True)
    in_old_price_rub = Column(Float, nullable=True)
    in_ps_plus_price_inr = Column(Float, nullable=True)
    in_ps_plus_price_rub = Column(Float, nullable=True)
    in_discount_percent = Column(Integer, nullable=True)
    in_has_discount = Column(Integer, nullable=True, comment="0/1")
    in_discount_end = Column(Text, nullable=True)
    in_ps_plus = Column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<ProductCard(card_id={self.card_id!r}, name={self.main_name or self.name!r})>"
