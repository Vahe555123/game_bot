"""
Пул HTTP-прокси для парсера PlayStation Store.

Решает 3 проблемы:
  1. Akamai/PS Store банит датацентровый IP — нужен резидентный/украинский прокси.
  2. Один прокси может «умереть» (исчерпан трафик / дневной лимит / временный бан).
     Нужно автоматически переключаться на следующий.
  3. Хочется видеть в админке состояние каждого прокси (ok / cooldown / banned).

Конфигурация в .env:
    PARSER_USE_PROXY=true
    PARSER_PROXY_LIST=http://u1:p1@host1:port1, http://u2:p2@host2:port2, ...

(Старый PARSER_PROXY_URL продолжает работать как fallback на 1 прокси.)

Не требует никаких внешних зависимостей кроме stdlib и aiohttp.
Состояние пула живёт в памяти — теряется при рестарте процесса.
"""
from __future__ import annotations

import asyncio
import os
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional


PROXY_HEALTH_URL = os.getenv("PARSER_PROXY_HEALTH_URL", "https://store.playstation.com/ru-ua/pages/browse")
PROXY_BAN_THRESHOLD = int(os.getenv("PARSER_PROXY_BAN_THRESHOLD", "10") or "10")
PROXY_COOLDOWN_SECONDS = int(os.getenv("PARSER_PROXY_COOLDOWN_SECONDS", "300") or "300")
PROXY_HEALTH_TIMEOUT = float(os.getenv("PARSER_PROXY_HEALTH_TIMEOUT", "20") or "20")


def _parse_bool(v: Optional[str], default: bool = False) -> bool:
    if not v:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on", "y", "t")


def _safe_label(url: str) -> str:
    """Маска login:password для UI/логов: возвращает host:port."""
    try:
        p = urllib.parse.urlparse(url)
        if p.hostname:
            port = f":{p.port}" if p.port else ""
            return f"{p.hostname}{port}"
    except Exception:
        pass
    return url[:30] + "…"


@dataclass
class ProxyEntry:
    url: str
    label: str
    status: str = "unknown"   # 'ok' | 'cooldown' | 'banned' | 'unknown' | 'failed_check'
    fail_count: int = 0
    success_count: int = 0
    last_check_at: float = 0.0
    last_error: Optional[str] = None
    cooldown_until: float = 0.0  # epoch seconds; 0 = не в кулдауне
    last_used_at: float = 0.0

    def to_public(self) -> dict:
        cd_left = max(0.0, self.cooldown_until - time.time()) if self.cooldown_until else 0.0
        return {
            "label": self.label,
            "status": self.status,
            "fail_count": self.fail_count,
            "success_count": self.success_count,
            "last_check_at": self.last_check_at,
            "last_used_at": self.last_used_at,
            "last_error": self.last_error,
            "cooldown_seconds_left": int(cd_left),
        }


class ProxyPool:
    """
    Потокобезопасный пул. Парсер забирает текущий прокси через .current(),
    при бане сообщает .mark_failure() — пул сам ротирует.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._proxies: list[ProxyEntry] = []
        self._active_index: int = 0
        self._enabled: bool = False
        self.reload_from_env()

    # ── загрузка/состояние ────────────────────────────────────────────────
    def reload_from_env(self) -> None:
        """Перечитывает .env. Можно дёргать руками после правки конфигурации."""
        with self._lock:
            self._enabled = _parse_bool(os.getenv("PARSER_USE_PROXY"), False)

            raw_list = (os.getenv("PARSER_PROXY_LIST") or "").strip()
            single = (os.getenv("PARSER_PROXY_URL") or "").strip()

            urls: list[str] = []
            if raw_list:
                # запятые ИЛИ переводы строк ИЛИ ; — всё считаем разделителем
                for part in raw_list.replace("\n", ",").replace(";", ",").split(","):
                    p = part.strip()
                    if p:
                        urls.append(p)
            elif single:
                urls.append(single)

            # Сохраняем существующее состояние для тех, что остались
            existing = {e.url: e for e in self._proxies}
            new_proxies: list[ProxyEntry] = []
            for u in urls:
                if u in existing:
                    new_proxies.append(existing[u])
                else:
                    new_proxies.append(ProxyEntry(url=u, label=_safe_label(u)))
            self._proxies = new_proxies

            if self._active_index >= len(self._proxies):
                self._active_index = 0

    @property
    def enabled(self) -> bool:
        return self._enabled and len(self._proxies) > 0

    def size(self) -> int:
        with self._lock:
            return len(self._proxies)

    def all_entries(self) -> list[ProxyEntry]:
        with self._lock:
            # возвращаем КОПИЮ списка (но сами entry мутабельные)
            return list(self._proxies)

    # ── активный прокси ───────────────────────────────────────────────────
    def current(self) -> Optional[ProxyEntry]:
        """Текущий active прокси. Если у активного истёк cooldown — возвращает его."""
        with self._lock:
            if not self._proxies:
                return None
            entry = self._proxies[self._active_index]
            # auto-recover из cooldown
            if entry.status == "cooldown" and time.time() >= entry.cooldown_until:
                entry.status = "ok"
                entry.cooldown_until = 0
            return entry

    def current_url(self) -> Optional[str]:
        e = self.current()
        return e.url if e else None

    def mark_used(self) -> None:
        with self._lock:
            e = self.current()
            if e:
                e.last_used_at = time.time()

    # ── ротация ───────────────────────────────────────────────────────────
    def rotate(self, *, reason: str = "manual") -> Optional[ProxyEntry]:
        """
        Перейти на следующий прокси, обходя banned/cooldown'нутые.
        Возвращает новый активный entry (или None если все мертвы).
        """
        with self._lock:
            n = len(self._proxies)
            if n == 0:
                return None
            now = time.time()
            for offset in range(1, n + 1):
                idx = (self._active_index + offset) % n
                cand = self._proxies[idx]
                # cooldown истёк → "ok"
                if cand.status == "cooldown" and now >= cand.cooldown_until:
                    cand.status = "ok"
                    cand.cooldown_until = 0
                if cand.status in ("ok", "unknown"):
                    self._active_index = idx
                    return cand
            # Все banned/cooldown → выбираем тот, у которого cooldown ближе всего к завершению
            best_idx, best_t = self._active_index, float("inf")
            for idx, cand in enumerate(self._proxies):
                t = cand.cooldown_until if cand.status == "cooldown" else now + 24 * 3600
                if t < best_t:
                    best_t, best_idx = t, idx
            self._active_index = best_idx
            return self._proxies[best_idx]

    def mark_failure(self, *, reason: str = "ban") -> Optional[ProxyEntry]:
        """
        Текущему прокси +1 fail_count. Если перебор → cooldown + rotate.
        Возвращает НОВЫЙ активный entry.
        """
        with self._lock:
            entry = self.current()
            if entry is None:
                return None
            entry.fail_count += 1
            entry.last_error = reason[:200]
            if entry.fail_count >= PROXY_BAN_THRESHOLD:
                entry.status = "cooldown"
                entry.cooldown_until = time.time() + PROXY_COOLDOWN_SECONDS
                # ротируем
                return self.rotate(reason=f"auto/{reason}")
            return entry

    def mark_success(self) -> None:
        with self._lock:
            entry = self.current()
            if entry is None:
                return
            entry.success_count += 1
            if entry.fail_count > 0:
                entry.fail_count = 0
            entry.status = "ok"

    def force_reset(self, *, label_or_url: Optional[str] = None) -> None:
        """Снять cooldown/banned принудительно (одной или всех записей)."""
        with self._lock:
            for e in self._proxies:
                if label_or_url and label_or_url not in (e.label, e.url):
                    continue
                e.status = "ok" if e.status in ("cooldown", "banned", "failed_check") else e.status
                e.cooldown_until = 0
                e.fail_count = 0
                e.last_error = None

    def select_by_label(self, label: str) -> bool:
        """Сделать активным прокси по label (host:port). Возвращает True если успешно."""
        with self._lock:
            for idx, e in enumerate(self._proxies):
                if e.label == label or e.url == label:
                    self._active_index = idx
                    return True
            return False

    # ── health-check (требует aiohttp) ────────────────────────────────────
    async def health_check_one(self, entry: ProxyEntry) -> bool:
        import aiohttp
        timeout = aiohttp.ClientTimeout(total=PROXY_HEALTH_TIMEOUT, connect=10)
        try:
            async with aiohttp.ClientSession(timeout=timeout) as s:
                async with s.get(PROXY_HEALTH_URL, proxy=entry.url, allow_redirects=False) as r:
                    body_len = 0
                    try:
                        text = await r.text()
                        body_len = len(text)
                    except Exception:
                        pass
                    with self._lock:
                        entry.last_check_at = time.time()
                        if r.status == 200 and body_len > 1000:
                            entry.status = "ok"
                            entry.last_error = None
                            return True
                        if r.status == 403:
                            entry.status = "banned"
                            entry.last_error = f"HTTP 403 (Akamai blocked, len={body_len})"
                            return False
                        entry.status = "failed_check"
                        entry.last_error = f"HTTP {r.status}, len={body_len}"
                        return False
        except Exception as exc:
            with self._lock:
                entry.last_check_at = time.time()
                entry.status = "failed_check"
                entry.last_error = f"{type(exc).__name__}: {str(exc)[:150]}"
            return False

    async def health_check_all(self) -> dict[str, bool]:
        """Параллельно пингуем все прокси. Возвращает {label: ok}."""
        entries = self.all_entries()
        if not entries:
            return {}
        results = await asyncio.gather(
            *[self.health_check_one(e) for e in entries],
            return_exceptions=True,
        )
        return {
            e.label: bool(r) if not isinstance(r, Exception) else False
            for e, r in zip(entries, results)
        }

    # ── для админки ───────────────────────────────────────────────────────
    def to_public_status(self) -> dict:
        with self._lock:
            active = self.current()
            return {
                "enabled": self.enabled,
                "size": len(self._proxies),
                "active_label": active.label if active else None,
                "active_status": active.status if active else None,
                "ban_threshold": PROXY_BAN_THRESHOLD,
                "cooldown_seconds": PROXY_COOLDOWN_SECONDS,
                "proxies": [
                    {
                        **e.to_public(),
                        "is_active": (i == self._active_index),
                    }
                    for i, e in enumerate(self._proxies)
                ],
            }


# Глобальный синглтон (один пул на процесс).
_pool_instance: Optional[ProxyPool] = None
_pool_init_lock = threading.Lock()


def get_proxy_pool() -> ProxyPool:
    global _pool_instance
    if _pool_instance is None:
        with _pool_init_lock:
            if _pool_instance is None:
                _pool_instance = ProxyPool()
    return _pool_instance
