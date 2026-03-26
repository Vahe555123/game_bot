"""
Модель PSN аккаунта для хранения данных авторизации по регионам.
Каждый регион (Турция, Украина) имеет свои PSN данные.
"""

from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.database.connection import Base
from app.utils.encryption import encrypt_password, decrypt_password, verify_password


class PSNAccount(Base):
    """
    Модель PSN аккаунта для определенного региона.
    Позволяет хранить разные PSN данные для разных регионов.
    """
    __tablename__ = 'psn_accounts'

    # Уникальный ключ: один аккаунт на пользователя на регион
    __table_args__ = (
        UniqueConstraint('user_id', 'region', name='uix_user_region'),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    region = Column(String(10), nullable=False, index=True, comment='Регион PSN аккаунта (UA, TR)')

    # PSN данные
    psn_email = Column(String(255), nullable=True, comment='Email для PSN аккаунта')
    psn_password_hash = Column(Text, nullable=True, comment='Зашифрованный пароль PSN аккаунта')
    psn_password_salt = Column(String(32), nullable=True, comment='Соль для шифрования пароля')

    # Платформа (может отличаться по регионам)
    platform = Column(String(50), nullable=True, comment='PlayStation платформа (PS4, PS5)')

    # Дополнительные поля для 2FA
    twofa_backup_code = Column(Text, nullable=True, comment='Резервный код 2FA (зашифрованный)')
    twofa_backup_salt = Column(String(32), nullable=True, comment='Соль для шифрования 2FA кода')

    # Метаданные
    is_active = Column(Integer, default=1, comment='Активен ли аккаунт (1=да, 0=нет)')
    created_at = Column(DateTime, default=datetime.utcnow, comment='Дата создания')
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, comment='Дата обновления')

    # Связь с пользователем
    user = relationship("User", back_populates="psn_accounts")

    def __repr__(self):
        return f"<PSNAccount(user_id={self.user_id}, region='{self.region}', email='{self.psn_email}')>"

    def set_psn_password(self, password: str):
        """Установить PSN пароль с шифрованием"""
        if not password:
            self.psn_password_hash = None
            self.psn_password_salt = None
            return

        encrypted_password, salt = encrypt_password(password)
        self.psn_password_hash = encrypted_password
        self.psn_password_salt = salt

    def get_psn_password(self) -> str:
        """Получить расшифрованный PSN пароль"""
        if not self.psn_password_hash or not self.psn_password_salt:
            return ""
        return decrypt_password(self.psn_password_hash, self.psn_password_salt)

    def verify_psn_password(self, password: str) -> bool:
        """Проверить PSN пароль"""
        if not self.psn_password_hash or not self.psn_password_salt:
            return False
        return verify_password(password, self.psn_password_hash, self.psn_password_salt)

    def set_twofa_code(self, code: str):
        """Установить резервный код 2FA с шифрованием"""
        if not code:
            self.twofa_backup_code = None
            self.twofa_backup_salt = None
            return

        encrypted_code, salt = encrypt_password(code)
        self.twofa_backup_code = encrypted_code
        self.twofa_backup_salt = salt

    def get_twofa_code(self) -> str:
        """Получить расшифрованный код 2FA"""
        if not self.twofa_backup_code or not self.twofa_backup_salt:
            return ""
        return decrypt_password(self.twofa_backup_code, self.twofa_backup_salt)

    @property
    def has_credentials(self) -> bool:
        """Проверить, есть ли PSN данные"""
        return bool(self.psn_email and self.psn_password_hash)

    @property
    def region_info(self) -> dict:
        """Получить информацию о регионе"""
        region_map = {
            'TR': {'code': 'TRY', 'symbol': '₺', 'flag': '🇹🇷', 'name': 'Турция'},
            'UA': {'code': 'UAH', 'symbol': '₴', 'flag': '🇺🇦', 'name': 'Украина'},
            'IN': {'code': 'INR', 'symbol': '₹', 'flag': '🇮🇳', 'name': 'Индия'}
        }
        return region_map.get(self.region, {'code': 'Unknown', 'symbol': '', 'flag': '', 'name': 'Неизвестно'})
