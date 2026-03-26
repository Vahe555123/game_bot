// Общие функции для админской панели PlayStation Store

// Утилиты для работы с cookies
function setCookie(name, value, days = 7) {
    const expires = new Date();
    expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = `${name}=${value};expires=${expires.toUTCString()};path=/`;
}

function getCookie(name) {
    const nameEQ = name + "=";
    const ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
        let c = ca[i];
        while (c.charAt(0) === ' ') c = c.substring(1, c.length);
        if (c.indexOf(nameEQ) === 0) return c.substring(nameEQ.length, c.length);
    }
    return null;
}

function deleteCookie(name) {
    document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
}

// Система уведомлений (Toast)
class ToastManager {
    constructor() {
        this.container = this.createContainer();
        document.body.appendChild(this.container);
    }

    createContainer() {
        const container = document.createElement('div');
        container.className = 'toast-container position-fixed top-0 end-0 p-3';
        container.style.zIndex = '1080';
        return container;
    }

    show(message, type = 'info', duration = 5000) {
        const toast = this.createToast(message, type);
        this.container.appendChild(toast);

        // Показываем toast
        const bsToast = new bootstrap.Toast(toast, {
            delay: duration,
            autohide: true
        });
        bsToast.show();

        // Удаляем после скрытия
        toast.addEventListener('hidden.bs.toast', () => {
            this.container.removeChild(toast);
        });
    }

    createToast(message, type) {
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.setAttribute('role', 'alert');
        toast.setAttribute('aria-live', 'assertive');
        toast.setAttribute('aria-atomic', 'true');

        const iconMap = {
            success: 'bi-check-circle-fill text-success',
            error: 'bi-exclamation-triangle-fill text-danger',
            warning: 'bi-exclamation-triangle-fill text-warning',
            info: 'bi-info-circle-fill text-info'
        };

        const bgMap = {
            success: 'bg-success',
            error: 'bg-danger',
            warning: 'bg-warning',
            info: 'bg-info'
        };

        const icon = iconMap[type] || iconMap.info;
        const bgColor = bgMap[type] || bgMap.info;

        toast.innerHTML = `
            <div class="toast-header ${bgColor} text-white">
                <i class="bi ${icon} me-2"></i>
                <strong class="me-auto">Уведомление</strong>
                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="toast" aria-label="Close"></button>
            </div>
            <div class="toast-body">
                ${message}
            </div>
        `;

        return toast;
    }
}

// Создаем глобальный менеджер уведомлений
const toastManager = new ToastManager();

// Функция для показа уведомлений
function showToast(message, type = 'info', duration = 5000) {
    toastManager.show(message, type, duration);
}

// Функции для работы с API
async function apiRequest(url, options = {}) {
    const token = getCookie('admin_token');
    
    const defaultOptions = {
        headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
        }
    };

    const config = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...options.headers
        }
    };

    try {
        const response = await fetch(url, config);
        
        if (response.status === 401) {
            // Токен истек, перенаправляем на страницу входа
            window.location.href = '/admin/login';
            return null;
        }

        return response;
    } catch (error) {
        console.error('API Request Error:', error);
        showToast('Ошибка сети. Проверьте подключение к интернету.', 'error');
        return null;
    }
}

// Функция для GET запросов
async function apiGet(url) {
    const response = await apiRequest(url);
    return response ? response.json() : null;
}

// Функция для POST запросов
async function apiPost(url, data) {
    const response = await apiRequest(url, {
        method: 'POST',
        body: JSON.stringify(data)
    });
    return response ? response.json() : null;
}

// Функция для PUT запросов
async function apiPut(url, data) {
    const response = await apiRequest(url, {
        method: 'PUT',
        body: JSON.stringify(data)
    });
    return response ? response.json() : null;
}

// Функция для DELETE запросов
async function apiDelete(url) {
    const response = await apiRequest(url, {
        method: 'DELETE'
    });
    return response ? response.json() : null;
}

// Утилиты для работы с формами
function serializeForm(form) {
    const formData = new FormData(form);
    const data = {};
    
    for (let [key, value] of formData.entries()) {
        // Обработка чекбоксов
        if (form.elements[key] && form.elements[key].type === 'checkbox') {
            data[key] = form.elements[key].checked;
        } else {
            data[key] = value;
        }
    }
    
    return data;
}

function populateForm(form, data) {
    for (let key in data) {
        const element = form.elements[key];
        if (element) {
            if (element.type === 'checkbox') {
                element.checked = data[key];
            } else {
                element.value = data[key] || '';
            }
        }
    }
}

// Функции для работы с таблицами
function addTableRow(tableId, rowData) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    const row = tbody.insertRow();
    
    rowData.forEach(cellData => {
        const cell = row.insertCell();
        cell.innerHTML = cellData;
    });
    
    return row;
}

function removeTableRow(row) {
    row.remove();
}

function clearTable(tableId) {
    const table = document.getElementById(tableId);
    const tbody = table.querySelector('tbody');
    tbody.innerHTML = '';
}

// Функции для работы с загрузкой
function showLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = `
            <div class="d-flex justify-content-center align-items-center py-4">
                <div class="spinner-border text-primary" role="status">
                    <span class="visually-hidden">Загрузка...</span>
                </div>
            </div>
        `;
    }
}

function hideLoading(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.innerHTML = '';
    }
}

// Функции для работы с модальными окнами
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        const bsModal = new bootstrap.Modal(modal);
        bsModal.show();
        return bsModal;
    }
    return null;
}

function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        const bsModal = bootstrap.Modal.getInstance(modal);
        if (bsModal) {
            bsModal.hide();
        }
    }
}

// Функции для работы с датами
function formatDate(dateString, options = {}) {
    const defaultOptions = {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    };
    
    const config = { ...defaultOptions, ...options };
    return new Date(dateString).toLocaleDateString('ru-RU', config);
}

function formatRelativeTime(dateString) {
    const now = new Date();
    const date = new Date(dateString);
    const diffInSeconds = Math.floor((now - date) / 1000);
    
    if (diffInSeconds < 60) {
        return 'только что';
    } else if (diffInSeconds < 3600) {
        const minutes = Math.floor(diffInSeconds / 60);
        return `${minutes} мин. назад`;
    } else if (diffInSeconds < 86400) {
        const hours = Math.floor(diffInSeconds / 3600);
        return `${hours} ч. назад`;
    } else {
        const days = Math.floor(diffInSeconds / 86400);
        return `${days} дн. назад`;
    }
}

// Функции для работы с числами
function formatNumber(number, decimals = 0) {
    return Number(number).toLocaleString('ru-RU', {
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals
    });
}

function formatCurrency(amount, currency = 'UAH') {
    const currencyMap = {
        'UAH': '₴',
        'TRL': '₺',
        'INR': '₹',
        'USD': '$',
        'EUR': '€'
    };
    
    const symbol = currencyMap[currency] || currency;
    return `${formatNumber(amount, 2)} ${symbol}`;
}

// Функции для работы с URL
function updateURL(params) {
    const url = new URL(window.location);
    
    for (let key in params) {
        if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
            url.searchParams.set(key, params[key]);
        } else {
            url.searchParams.delete(key);
        }
    }
    
    window.history.pushState({}, '', url);
}

function getURLParams() {
    const params = new URLSearchParams(window.location.search);
    const result = {};
    
    for (let [key, value] of params.entries()) {
        result[key] = value;
    }
    
    return result;
}

// Функции для работы с локальным хранилищем
function saveToStorage(key, data) {
    try {
        localStorage.setItem(key, JSON.stringify(data));
    } catch (error) {
        console.error('Ошибка сохранения в localStorage:', error);
    }
}

function loadFromStorage(key, defaultValue = null) {
    try {
        const item = localStorage.getItem(key);
        return item ? JSON.parse(item) : defaultValue;
    } catch (error) {
        console.error('Ошибка загрузки из localStorage:', error);
        return defaultValue;
    }
}

function removeFromStorage(key) {
    try {
        localStorage.removeItem(key);
    } catch (error) {
        console.error('Ошибка удаления из localStorage:', error);
    }
}

// Функции для работы с поиском
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Функция для копирования в буфер обмена
async function copyToClipboard(text) {
    try {
        await navigator.clipboard.writeText(text);
        showToast('Скопировано в буфер обмена', 'success');
    } catch (error) {
        console.error('Ошибка копирования:', error);
        showToast('Ошибка копирования', 'error');
    }
}

// Функция для скачивания файла
function downloadFile(data, filename, type = 'application/octet-stream') {
    const blob = new Blob([data], { type });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
}

// Инициализация при загрузке страницы
document.addEventListener('DOMContentLoaded', function() {
    // Инициализация всех tooltip'ов
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    const tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Инициализация всех popover'ов
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    const popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Автоматическое скрытие алертов через 5 секунд
    const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
    alerts.forEach(alert => {
        setTimeout(() => {
            const bsAlert = new bootstrap.Alert(alert);
            bsAlert.close();
        }, 5000);
    });

    // Добавляем обработчик для всех ссылок с классом 'copy-link'
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('copy-link') || e.target.closest('.copy-link')) {
            e.preventDefault();
            const link = e.target.classList.contains('copy-link') ? e.target : e.target.closest('.copy-link');
            const text = link.getAttribute('data-copy') || link.href || link.textContent;
            copyToClipboard(text);
        }
    });

    console.log('Админка PlayStation Store загружена');
});

// Глобальные переменные
window.AdminApp = {
    apiGet,
    apiPost,
    apiPut,
    apiDelete,
    showToast,
    showModal,
    hideModal,
    formatDate,
    formatRelativeTime,
    formatNumber,
    formatCurrency,
    copyToClipboard,
    downloadFile,
    debounce
}; 