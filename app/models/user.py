from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.connection import Base
import hashlib
import secrets
from app.utils.encryption import encrypt_password, decrypt_password, verify_password

class User(Base):
    """Модель пользователя Telegram"""
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True, comment='ID пользователя в Telegram')
    username = Column(String(255), nullable=True, comment='Username пользователя в Telegram')
    first_name = Column(String(255), nullable=True, comment='Имя пользователя')
    last_name = Column(String(255), nullable=True, comment='Фамилия пользователя')
    preferred_region = Column(String(10), default='UA', comment='Предпочитаемый регион (UA, TR, IN)')

    # Настройки отображения регионов (по умолчанию включена только Турция)
    show_ukraine_prices = Column(Boolean, default=False, comment='Показывать цены Украины')
    show_turkey_prices = Column(Boolean, default=True, comment='Показывать цены Турции')
    show_india_prices = Column(Boolean, default=False, comment='Показывать цены Индии')

    # Email для привязки покупки (общий для всех регионов - Турция, Индия, Украина)
    payment_email = Column(String(255), nullable=True, comment='Email для привязки покупки на oplata.info')

    # PSN данные пользователя
    platform = Column(String(50), nullable=True, comment='PlayStation платформа (PS4, PS5)')
    psn_email = Column(String(255), nullable=True, comment='Email для PSN аккаунта')
    psn_password_hash = Column(Text, nullable=True, comment='Зашифрованный пароль PSN аккаунта')
    psn_password_salt = Column(String(32), nullable=True, comment='Соль для шифрования пароля')

    is_active = Column(Boolean, default=True, comment='Активен ли пользователь')
    created_at = Column(DateTime, default=datetime.utcnow, comment='Дата регистрации')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='Дата последнего обновления')

    # Связь с избранными товарами
    favorite_products = relationship("UserFavoriteProduct", back_populates="user", cascade="all, delete-orphan")

    # Связь с PSN аккаунтами (по регионам)
    psn_accounts = relationship("PSNAccount", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username='{self.username}')>"

    @property
    def full_name(self):
        """Полное имя пользователя"""
        parts = [self.first_name, self.last_name]
        return " ".join(filter(None, parts)) or self.username or f"User {self.telegram_id}"

    def get_enabled_regions(self):
        """Получить список включенных регионов"""
        regions = []
        if self.show_ukraine_prices:
            regions.append('UA')
        if self.show_turkey_prices:
            regions.append('TR')
        if self.show_india_prices:
            regions.append('IN')
        # Если все регионы выключены, возвращаем Турцию по умолчанию
        if not regions:
            regions = ['TR']
        return regions

    def get_preferred_region_info(self):
        """Получить информацию о предпочитаемом регионе"""
        region_map = {
            'TR': {'code': 'TRL', 'symbol': '₺', 'flag': '🇹🇷', 'name': 'Турция'},
            'UA': {'code': 'UAH', 'symbol': '₴', 'flag': '🇺🇦', 'name': 'Украина'},
            'IN': {'code': 'INR', 'symbol': '₹', 'flag': '🇮🇳', 'name': 'Индия'}
        }
        return region_map.get(self.preferred_region, region_map['UA'])

    def set_psn_password(self, password: str):
        """Установить PSN пароль с шифрованием"""
        if not password:
            self.psn_password_hash = None
            self.psn_password_salt = None
            return

        # Шифруем пароль
        encrypted_password, salt = encrypt_password(password)

        self.psn_password_hash = encrypted_password
        self.psn_password_salt = salt

    def verify_psn_password(self, password: str) -> bool:
        """Проверить PSN пароль"""
        if not self.psn_password_hash or not self.psn_password_salt:
            return False

        return verify_password(password, self.psn_password_hash, self.psn_password_salt)

    def get_psn_password(self) -> str:
        """
        Получить расшифрованный PSN пароль

        Returns:
            str: Расшифрованный PSN пароль или пустая строка если пароль не задан
        """
        if not self.psn_password_hash or not self.psn_password_salt:
            return ""

        return decrypt_password(self.psn_password_hash, self.psn_password_salt)

    @property
    def has_psn_credentials(self) -> bool:
        """Проверить, есть ли PSN данные у пользователя (старые глобальные)"""
        return bool(self.psn_email and self.psn_password_hash)

    def get_psn_account_for_region(self, region: str):
        """
        Получить PSN аккаунт для указанного региона.

        Args:
            region: Код региона (UA, TR)

        Returns:
            PSNAccount или None
        """
        for account in self.psn_accounts:
            if account.region == region and account.is_active:
                return account
        return None

    def has_psn_credentials_for_region(self, region: str) -> bool:
        """
        Проверить, есть ли PSN данные для указанного региона.

        Args:
            region: Код региона (UA, TR)

        Returns:
            True если есть настроенный аккаунт
        """
        account = self.get_psn_account_for_region(region)
        return account is not None and account.has_credentials

    def get_all_psn_accounts(self) -> list:
        """Получить все активные PSN аккаунты пользователя"""
        return [acc for acc in self.psn_accounts if acc.is_active]
