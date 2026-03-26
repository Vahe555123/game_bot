"""
Утилиты для проверки сетевой доступности и диагностики проблем подключения
"""
import aiohttp
import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


async def check_site_availability(url: str, timeout: int = 10) -> Dict[str, any]:
    """
    Проверяет доступность сайта и возвращает диагностическую информацию
    
    Args:
        url: URL для проверки
        timeout: Таймаут в секундах
        
    Returns:
        Dict с информацией о доступности и возможных проблемах
    """
    result = {
        'available': False,
        'status_code': None,
        'response_time_ms': None,
        'headers': {},
        'error': None,
        'can_embed_iframe': False,
        'cors_allowed': False
    }
    
    try:
        start_time = asyncio.get_event_loop().time()
        
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:
            async with session.get(url, allow_redirects=True) as response:
                end_time = asyncio.get_event_loop().time()
                
                result['available'] = True
                result['status_code'] = response.status
                result['response_time_ms'] = round((end_time - start_time) * 1000, 2)
                result['headers'] = dict(response.headers)
                
                # Проверяем возможность встраивания в iframe
                x_frame_options = response.headers.get('X-Frame-Options', '').upper()
                result['can_embed_iframe'] = x_frame_options not in ['DENY', 'SAMEORIGIN']
                
                # Проверяем CORS
                access_control = response.headers.get('Access-Control-Allow-Origin', '')
                result['cors_allowed'] = access_control == '*' or access_control != ''
                
                logger.info(f"Site check for {url}: available={result['available']}, "
                          f"status={result['status_code']}, time={result['response_time_ms']}ms")
                
    except aiohttp.ClientError as e:
        result['error'] = f"Network error: {str(e)}"
        logger.error(f"Network error checking {url}: {str(e)}")
    except asyncio.TimeoutError:
        result['error'] = f"Timeout after {timeout} seconds"
        logger.error(f"Timeout checking {url}")
    except Exception as e:
        result['error'] = f"Unexpected error: {str(e)}"
        logger.error(f"Unexpected error checking {url}: {str(e)}")
    
    return result


async def diagnose_payment_site_issues(base_url: str = "https://digiseller.market") -> Dict[str, any]:
    """
    Диагностирует проблемы с сайтом оплаты
    
    Args:
        base_url: Базовый URL для проверки
        
    Returns:
        Dict с диагностической информацией и рекомендациями
    """
    diagnosis = {
        'main_site': None,
        'payment_endpoint': None,
        'recommendations': [],
        'issues_found': []
    }
    
    # Проверяем основной сайт
    diagnosis['main_site'] = await check_site_availability(base_url)
    
    # Проверяем endpoint оплаты
    payment_url = f"{base_url}/asp2/pay.asp"
    diagnosis['payment_endpoint'] = await check_site_availability(payment_url)
    
    # Анализируем результаты и даем рекомендации
    main_site = diagnosis['main_site']
    payment_site = diagnosis['payment_endpoint']
    
    if not main_site['available']:
        diagnosis['issues_found'].append("Основной сайт недоступен")
        diagnosis['recommendations'].append("Проверьте интернет-соединение")
        diagnosis['recommendations'].append("Возможно, сайт временно недоступен")
    
    if not payment_site['available']:
        diagnosis['issues_found'].append("Endpoint оплаты недоступен")
        diagnosis['recommendations'].append("Проверьте корректность URL оплаты")
    
    if main_site['available'] and not main_site['can_embed_iframe']:
        diagnosis['issues_found'].append("Сайт блокирует встраивание в iframe")
        diagnosis['recommendations'].append("Используйте 'Открыть в браузере' вместо iframe")
    
    if main_site['available'] and not main_site['cors_allowed']:
        diagnosis['issues_found'].append("CORS политика блокирует запросы")
        diagnosis['recommendations'].append("Необходимо открывать ссылку в отдельном окне")
    
    if main_site['available'] and main_site['response_time_ms'] > 5000:
        diagnosis['issues_found'].append("Медленное время ответа сервера")
        diagnosis['recommendations'].append("Подождите и повторите попытку")
    
    # Если проблем не найдено
    if not diagnosis['issues_found']:
        diagnosis['recommendations'].append("Сайт доступен и готов к использованию")
    
    return diagnosis