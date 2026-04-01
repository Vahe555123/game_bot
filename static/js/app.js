// Modern PlayStation Store WebApp JavaScript

class TelegramWebApp {
    constructor() {


        this.tg = window.Telegram?.WebApp;
        this.user = null;
        this.isInitialized = false;
        this.userStorageKey = 'telegram_webapp_user';

        // Диагностическая информация
        console.log('=== Telegram WebApp Initialization ===');
        console.log('window.Telegram:', window.Telegram);
        console.log('window.Telegram.WebApp:', this.tg);
        console.log('User Agent:', navigator.userAgent);
        console.log('URL:', window.location.href);
        console.log('Hash:', window.location.hash);
        console.log('Search params:', window.location.search);

        this.init().catch(error => {
            console.error('Error during initialization:', error);
        });
    }

    async init() {



        if (this.tg) {
            try {
                console.log('Telegram WebApp found, initializing...');
                this.tg.ready();

                console.log('=== Telegram WebApp Data ===');
                console.log('initData:', this.tg.initData);
                console.log('initDataUnsafe:', this.tg.initDataUnsafe);
                console.log('version:', this.tg.version);
                console.log('platform:', this.tg.platform);
                console.log('colorScheme:', this.tg.colorScheme);

                // ПРИНУДИТЕЛЬНОЕ извлечение пользователя из Telegram данных
                this.user = null;

                // Способ 1: Прямо из initDataUnsafe
                console.log('=== Trying Method 1: initDataUnsafe ===');
                if (this.tg.initDataUnsafe && this.tg.initDataUnsafe.user) {
                    this.user = this.tg.initDataUnsafe.user;
                    console.log('✅ User found via initDataUnsafe:', this.user);
                } else {
                    console.log('❌ No user in initDataUnsafe');
                }

                // Способ 2: Если первый не сработал, парсим initData вручную
                if (!this.user && this.tg.initData) {
                    console.log('=== Trying Method 2: Manual parsing initData ===');
                    try {
                        const initDataParams = new URLSearchParams(this.tg.initData);
                        const userParam = initDataParams.get('user');
                        console.log('initData userParam:', userParam);
                        if (userParam) {
                            this.user = JSON.parse(decodeURIComponent(userParam));
                            console.log('✅ User found via initData parsing:', this.user);
                        } else {
                            console.log('❌ No user parameter in initData');
                        }
                    } catch (error) {
                        console.log('❌ Error parsing initData:', error);
                    }
                } else if (!this.user) {
                    console.log('❌ No initData available');
                }

                // Способ 3: Если ничего не работает, берем из URL хеша
                if (!this.user) {
                    console.log('=== Trying Method 3: URL hash parsing ===');
                    const hash = window.location.hash;
                    if (hash) {
                        try {
                            const hashParams = new URLSearchParams(hash.substring(1));
                            const tgWebAppData = hashParams.get('tgWebAppData');
                            console.log('Hash tgWebAppData:', tgWebAppData);
                            if (tgWebAppData) {
                                const decodedData = decodeURIComponent(tgWebAppData);
                                console.log('Decoded data:', decodedData);
                                const initData = new URLSearchParams(decodedData);
                                const userStr = initData.get('user');
                                console.log('Hash userStr:', userStr);
                                if (userStr) {
                                    this.user = JSON.parse(decodeURIComponent(userStr));
                                    console.log('✅ User found via hash parsing:', this.user);
                                } else {
                                    console.log('❌ No user in hash data');
                                }
                            } else {
                                console.log('❌ No tgWebAppData in hash');
                            }
                        } catch (error) {
                            console.log('❌ Error parsing hash:', error);
                        }
                    } else {
                        console.log('❌ No hash in URL');
                    }
                }

                // Preserve the resolved Telegram user between server-rendered page navigations.
                if (!this.user) {
                    console.log('=== Trying Method 4: Restoring cached user ===');
                    const storedUser = this.getStoredUser();
                    if (storedUser) {
                        this.user = storedUser;
                        console.log('✅ User restored from storage:', this.user);
                    } else {
                        console.log('❌ No stored user data available');
                    }
                }

                if (this.user?.id) {
                    this.storeUser(this.user);
                }

                console.log('=== Final Result ===');
                console.log('Final user:', this.user);
                console.log('User ID:', this.user?.id);


                this.setupTheme();
                this.setupMainButton();
                this.setupBackButton();
                this.setupViewport();
                this.isInitialized = true;

                console.log('✅ Telegram WebApp initialization completed');

            } catch (error) {
                console.error('Error initializing Telegram WebApp:', error);
            }
        } else {
            console.log('❌ No Telegram WebApp detected');
            console.log('This might mean:');
            console.log('1. Opening outside Telegram');
            console.log('2. Telegram WebApp script not loaded');
            console.log('3. Wrong domain/HTTPS issues');
        }
    }

    setupTheme() {
        const root = document.documentElement;
        const body = document.body;

        if (this.tg?.themeParams) {
            const theme = this.tg.themeParams;

            // Apply Telegram theme colors
            const themeMap = {
                '--tg-theme-bg-color': theme.bg_color || '#ffffff',
                '--tg-theme-text-color': theme.text_color || '#000000',
                '--tg-theme-hint-color': theme.hint_color || '#999999',
                '--tg-theme-link-color': theme.link_color || '#2481cc',
                '--tg-theme-button-color': theme.button_color || '#2481cc',
                '--tg-theme-button-text-color': theme.button_text_color || '#ffffff',
                '--tg-theme-secondary-bg-color': theme.secondary_bg_color || '#f1f1f1',
                '--tg-theme-destructive-text-color': theme.destructive_text_color || '#dc3545'
            };

            Object.entries(themeMap).forEach(([property, value]) => {
                root.style.setProperty(property, value);
            });

            const isDarkTheme = this.tg.colorScheme === 'dark';
            root.classList.toggle('tg-theme-dark', isDarkTheme);
            root.classList.toggle('tg-theme-light', !isDarkTheme);
            if (body) {
                body.classList.toggle('tg-theme-dark', isDarkTheme);
                body.classList.toggle('tg-theme-light', !isDarkTheme);
            }

            // Adjust for dark theme
            if (isDarkTheme) {
                root.style.setProperty('--shadow-sm', '0 1px 2px 0 rgba(255, 255, 255, 0.05)');
                root.style.setProperty('--shadow-md', '0 4px 6px -1px rgba(255, 255, 255, 0.1)');
                root.style.setProperty('--shadow-lg', '0 10px 15px -3px rgba(255, 255, 255, 0.1)');
            } else {
                root.style.setProperty('--shadow-sm', '0 1px 2px 0 rgba(0, 0, 0, 0.05)');
                root.style.setProperty('--shadow-md', '0 4px 6px -1px rgba(0, 0, 0, 0.1)');
                root.style.setProperty('--shadow-lg', '0 10px 15px -3px rgba(0, 0, 0, 0.1)');
            }
        } else {
            root.classList.add('tg-theme-light');
            root.classList.remove('tg-theme-dark');
            if (body) {
                body.classList.add('tg-theme-light');
                body.classList.remove('tg-theme-dark');
            }
        }
    }

    setupViewport() {
        if (this.tg) {
            // Enable closing confirmation for back button
            this.tg.enableClosingConfirmation();

            // Отключаем сворачивание окна при свайпе вверх
            if (this.tg.disableVerticalSwipes) {
                this.tg.disableVerticalSwipes();
            }

            // Set header color
            if (this.tg.setHeaderColor) {
                this.tg.setHeaderColor(this.tg.themeParams?.bg_color || '#ffffff');
            }

            // Set background color
            if (this.tg.setBackgroundColor) {
                this.tg.setBackgroundColor(this.tg.themeParams?.bg_color || '#ffffff');
            }
        }
    }

    setupMainButton() {
        if (this.tg?.MainButton) {
            this.tg.MainButton.hide();
        }
    }

    setupBackButton() {
        if (this.tg?.BackButton) {
            this.tg.BackButton.hide();
        }
    }

    showMainButton(text, callback) {
        if (this.tg?.MainButton) {
            this.tg.MainButton.setText(text);
            this.tg.MainButton.onClick(callback);
            this.tg.MainButton.show();
            return true;
        }
        return false;
    }

    hideMainButton() {
        if (this.tg?.MainButton) {
            this.tg.MainButton.hide();
            return true;
        }
        return false;
    }

    showBackButton(callback) {
        if (this.tg?.BackButton) {
            this.tg.BackButton.onClick(callback);
            this.tg.BackButton.show();
            return true;
        }
        return false;
    }

    hideBackButton() {
        if (this.tg?.BackButton) {
            this.tg.BackButton.hide();
            return true;
        }
        return false;
    }

    close() {
        if (this.tg) {
            this.tg.close();
        }
    }

    expand() {
        if (this.tg) {
            this.tg.expand();
        }
    }

    hapticFeedback(type = 'impact', style = 'medium') {
        if (this.tg?.HapticFeedback) {
            try {
                if (type === 'impact') {
                    this.tg.HapticFeedback.impactOccurred(style);
                } else if (type === 'notification') {
                    this.tg.HapticFeedback.notificationOccurred(style);
                } else if (type === 'selection') {
                    this.tg.HapticFeedback.selectionChanged();
                }
                return true;
            } catch (error) {
                console.error('Haptic feedback error:', error);
            }
        }
        return false;
    }

    storeUser(user) {
        if (!user?.id) {
            return;
        }

        const normalizedUser = {
            id: user.id,
            username: user.username || null,
            first_name: user.first_name || null,
            last_name: user.last_name || null,
            language_code: user.language_code || null
        };

        try {
            const serializedUser = JSON.stringify(normalizedUser);
            sessionStorage.setItem(this.userStorageKey, serializedUser);
            localStorage.setItem(this.userStorageKey, serializedUser);
        } catch (error) {
            console.warn('Failed to persist Telegram user data:', error);
        }
    }

    getStoredUser() {
        const storages = [sessionStorage, localStorage];

        for (const storage of storages) {
            try {
                const rawUser = storage.getItem(this.userStorageKey);
                if (!rawUser) {
                    continue;
                }

                const parsedUser = JSON.parse(rawUser);
                if (parsedUser?.id) {
                    return parsedUser;
                }
            } catch (error) {
                console.warn('Failed to read persisted Telegram user data:', error);
            }
        }

        return null;
    }

    getCurrentUser() {
        return this.user || this.getStoredUser();
    }

    // User information getters
    getUserId() {
        console.log('=== Getting User ID ===');
        console.log('this.user:', this.user);

        const currentUser = this.getCurrentUser();
        if (currentUser?.id) {
            console.log('✅ User ID found:', currentUser.id);
            return currentUser.id;
        }

        console.log('❌ No user.id, trying alternative methods...');

        // Попробуем получить из URL параметров для десктопного Telegram
        const hash = window.location.hash;
        if (hash) {
            console.log('Trying to get ID from hash:', hash);
            const hashParams = new URLSearchParams(hash.substring(1));
            const tgWebAppData = hashParams.get('tgWebAppData');

            if (tgWebAppData) {
                try {
                    const decodedData = decodeURIComponent(tgWebAppData);
                    const initData = new URLSearchParams(decodedData);
                    const userStr = initData.get('user');

                    if (userStr) {
                        const user = JSON.parse(decodeURIComponent(userStr));
                        this.user = user;
                        this.storeUser(user);
                        console.log('✅ User ID found from hash:', user.id);
                        return user.id;
                    }
                } catch (error) {
                    console.error('Error parsing user ID from hash:', error);
                }
            }
        }

        // Попробуем из initData еще раз
        if (this.tg?.initData) {
            console.log('Trying to get ID from initData:', this.tg.initData);
            try {
                const initDataParams = new URLSearchParams(this.tg.initData);
                const userParam = initDataParams.get('user');
                if (userParam) {
                    const user = JSON.parse(decodeURIComponent(userParam));
                    this.user = user;
                    this.storeUser(user);
                    console.log('✅ User ID found from initData:', user.id);
                    return user.id;
                }
            } catch (error) {
                console.error('Error parsing user ID from initData:', error);
            }
        }

        console.log('❌ No User ID found anywhere');
        return null;
    }

    getUserName() {
        return this.getCurrentUser()?.username;
    }

    getUserFirstName() {
        return this.getCurrentUser()?.first_name;
    }

    getUserLastName() {
        return this.getCurrentUser()?.last_name;
    }

    getUserFullName() {
        const firstName = this.getUserFirstName() || '';
        const lastName = this.getUserLastName() || '';
        return `${firstName} ${lastName}`.trim() || this.getUserName() || 'Пользователь';
    }

    getInitData() {
        return this.tg?.initData;
    }

    getInitDataUnsafe() {
        return this.tg?.initDataUnsafe;
    }

    isReady() {
        return this.isInitialized && this.tg != null;
    }

    getVersion() {
        return this.tg?.version;
    }

    getPlatform() {
        return this.tg?.platform;
    }

    getColorScheme() {
        return this.tg?.colorScheme;
    }

    // Navigation helpers
    goBack() {
        if (window.history.length > 1) {
            window.history.back();
        } else {
            this.close();
        }
    }

    sendData(data) {
        if (this.tg) {
            this.tg.sendData(JSON.stringify(data));
        }
    }

    async init() {
        if (this.tg) {
            try {
                console.log('Telegram WebApp found, initializing...');
                this.tg.ready();

                console.log('=== Telegram WebApp Data ===');
                console.log('initData:', this.tg.initData);
                console.log('initDataUnsafe:', this.tg.initDataUnsafe);
                console.log('version:', this.tg.version);
                console.log('platform:', this.tg.platform);
                console.log('colorScheme:', this.tg.colorScheme);

                this.user = null;
                this.refreshUserContext({ log: true });
                await this.waitForUserContext();

                console.log('=== Final Result ===');
                console.log('Final user:', this.user);
                console.log('User ID:', this.user?.id);

                this.setupTheme();
                this.setupMainButton();
                this.setupBackButton();
                this.setupViewport();
                this.isInitialized = true;

                console.log('✅ Telegram WebApp initialization completed');
            } catch (error) {
                console.error('Error initializing Telegram WebApp:', error);
            }
        } else {
            console.log('❌ No Telegram WebApp detected');
            console.log('This might mean:');
            console.log('1. Opening outside Telegram');
            console.log('2. Telegram WebApp script not loaded');
            console.log('3. Wrong domain/HTTPS issues');
        }
    }

    refreshUserContext({ log = false } = {}) {
        const userFromInitDataUnsafe = this.readUserFromInitDataUnsafe(log);
        if (userFromInitDataUnsafe?.id) {
            this.user = userFromInitDataUnsafe;
            this.storeUser(this.user);
            return this.user;
        }

        const userFromInitData = this.readUserFromInitData(log);
        if (userFromInitData?.id) {
            this.user = userFromInitData;
            this.storeUser(this.user);
            return this.user;
        }

        const userFromHash = this.readUserFromHash(log);
        if (userFromHash?.id) {
            this.user = userFromHash;
            this.storeUser(this.user);
            return this.user;
        }

        const userFromQueryParams = this.readUserFromQueryParams(log);
        if (userFromQueryParams?.id) {
            this.user = userFromQueryParams;
            this.storeUser(this.user);
            return this.user;
        }

        const storedUser = this.getStoredUser();
        if (storedUser?.id) {
            if (log) {
                console.log('=== Trying Method 5: Restoring cached user ===');
                console.log('✅ User restored from storage:', storedUser);
            }
            this.user = storedUser;
            return this.user;
        }

        if (log) {
            console.log('❌ No stored user data available');
        }

        return this.user;
    }

    async waitForUserContext(maxWait = 4000, checkInterval = 200) {
        let waited = 0;

        while (waited < maxWait) {
            const user = this.refreshUserContext({ log: false });
            if (user?.id) {
                return user;
            }

            await new Promise(resolve => setTimeout(resolve, checkInterval));
            waited += checkInterval;
        }

        return this.refreshUserContext({ log: false });
    }

    readUserFromInitDataUnsafe(log = false) {
        if (log) {
            console.log('=== Trying Method 1: initDataUnsafe ===');
        }

        if (this.tg?.initDataUnsafe?.user) {
            if (log) {
                console.log('✅ User found via initDataUnsafe:', this.tg.initDataUnsafe.user);
            }
            return this.tg.initDataUnsafe.user;
        }

        if (log) {
            console.log('❌ No user in initDataUnsafe');
        }

        return null;
    }

    readUserFromInitData(log = false) {
        if (log) {
            console.log('=== Trying Method 2: Manual parsing initData ===');
        }

        if (!this.tg?.initData) {
            if (log) {
                console.log('❌ No initData available');
            }
            return null;
        }

        try {
            const initDataParams = new URLSearchParams(this.tg.initData);
            const userParam = initDataParams.get('user');
            if (log) {
                console.log('initData userParam:', userParam);
            }

            if (userParam) {
                const user = JSON.parse(decodeURIComponent(userParam));
                if (log) {
                    console.log('✅ User found via initData parsing:', user);
                }
                return user;
            }

            if (log) {
                console.log('❌ No user parameter in initData');
            }
        } catch (error) {
            if (log) {
                console.log('❌ Error parsing initData:', error);
            }
        }

        return null;
    }

    readUserFromHash(log = false) {
        if (log) {
            console.log('=== Trying Method 3: URL hash parsing ===');
        }

        const hash = window.location.hash;
        if (!hash) {
            if (log) {
                console.log('❌ No hash in URL');
            }
            return null;
        }

        try {
            const hashParams = new URLSearchParams(hash.substring(1));
            const tgWebAppData = hashParams.get('tgWebAppData');
            if (log) {
                console.log('Hash tgWebAppData:', tgWebAppData);
            }

            if (!tgWebAppData) {
                if (log) {
                    console.log('❌ No tgWebAppData in hash');
                }
                return null;
            }

            const decodedData = decodeURIComponent(tgWebAppData);
            if (log) {
                console.log('Decoded data:', decodedData);
            }

            const initData = new URLSearchParams(decodedData);
            const userStr = initData.get('user');
            if (log) {
                console.log('Hash userStr:', userStr);
            }

            if (userStr) {
                const user = JSON.parse(decodeURIComponent(userStr));
                if (log) {
                    console.log('✅ User found via hash parsing:', user);
                }
                return user;
            }

            if (log) {
                console.log('❌ No user in hash data');
            }
        } catch (error) {
            if (log) {
                console.log('❌ Error parsing hash:', error);
            }
        }

        return null;
    }

    readUserFromQueryParams(log = false) {
        if (log) {
            console.log('=== Trying Method 4: Query params fallback ===');
        }

        try {
            const params = new URLSearchParams(window.location.search);
            const userId = params.get('tg_user_id');
            if (log) {
                console.log('Query tg_user_id:', userId);
            }

            if (!userId) {
                if (log) {
                    console.log('❌ No tg_user_id in query params');
                }
                return null;
            }

            const user = {
                id: Number(userId),
                username: params.get('tg_username') || null,
                first_name: params.get('tg_first_name') || null,
                last_name: params.get('tg_last_name') || null,
                language_code: params.get('tg_language_code') || 'ru'
            };

            if (!Number.isFinite(user.id)) {
                if (log) {
                    console.log('❌ Invalid tg_user_id in query params');
                }
                return null;
            }

            if (log) {
                console.log('✅ User found via query params:', user);
            }

            return user;
        } catch (error) {
            if (log) {
                console.log('❌ Error parsing query params:', error);
            }
        }

        return null;
    }

    getCurrentUser() {
        return this.user || this.refreshUserContext({ log: false }) || this.getStoredUser();
    }


}

// Enhanced API Client with better error handling and caching
class APIClient {
    constructor(baseURL = '/api') {
        // Автоматически определяем базовый URL для API
        if (window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1') {
            // Для продакшена используем текущий origin
            this.baseURL = window.location.origin + '/api';
        } else {
            // Для разработки используем относительный путь
            this.baseURL = baseURL;
        }
        this.cache = new Map();
        this.cacheTimeout = 5 * 60 * 1000; // 5 minutes


    }

    async request(endpoint, options = {}) {
        // Убираем дублирование /api/ в URL
        const cleanEndpoint = endpoint.startsWith('/api/') ? endpoint.substring(4) : endpoint;
        const url = `${this.baseURL}${cleanEndpoint}`;
        const config = {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        };

        console.log('🌐 API Request:', {
            method: options.method || 'GET',
            url: url,
            endpoint: endpoint,
            cleanEndpoint: cleanEndpoint,
            baseURL: this.baseURL,
            body: options.body,
            headers: config.headers
        });

        try {
            const response = await fetch(url, config);

            console.log('📡 API Response:', {
                url: url,
                status: response.status,
                statusText: response.statusText,
                ok: response.ok,
                headers: Object.fromEntries(response.headers.entries())
            });

            if (!response.ok) {
                const errorData = await response.text();
                console.error('❌ API Error Response:', {
                    url: url,
                    status: response.status,
                    errorData: errorData
                });
                throw new Error(`HTTP ${response.status}: ${errorData}`);
            }

            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            } else {
                return await response.text();
            }
        } catch (error) {
            console.error(`❌ API request failed:`, {
                url: url,
                error: error,
                message: error.message,
                stack: error.stack
            });
            throw error;
        }
    }

    async get(endpoint, params = {}, useCache = false) {
        // Убираем дублирование /api/ в URL
        const cleanEndpoint = endpoint.startsWith('/api/') ? endpoint.substring(4) : endpoint;
        const url = new URL(`${this.baseURL}${cleanEndpoint}`, window.location.origin);
        Object.keys(params).forEach(key => {
            if (params[key] !== null && params[key] !== undefined && params[key] !== '') {
                url.searchParams.append(key, params[key]);
            }
        });

        const fullUrl = url.pathname + url.search;

        // Check cache
        if (useCache && this.cache.has(fullUrl)) {
            const cached = this.cache.get(fullUrl);
            if (Date.now() - cached.timestamp < this.cacheTimeout) {
                return cached.data;
            }
        }

        const data = await this.request(fullUrl);

        // Cache the response
        if (useCache) {
            this.cache.set(fullUrl, {
                data: data,
                timestamp: Date.now()
            });
        }

        return data;
    }

    async post(endpoint, data = {}) {
        console.log('🔵 API POST Request:', {
            endpoint: endpoint,
            data: data,
            dataStringified: JSON.stringify(data)
        });
        try {
            const result = await this.request(endpoint, {
                method: 'POST',
                body: JSON.stringify(data)
            });
            console.log('✅ API POST Success:', {
                endpoint: endpoint,
                result: result
            });
            return result;
        } catch (error) {
            console.error('❌ API POST Error:', {
                endpoint: endpoint,
                data: data,
                error: error,
                errorMessage: error.message,
                errorStack: error.stack
            });
            throw error;
        }
    }

    async put(endpoint, data = {}) {
        return this.request(endpoint, {
            method: 'PUT',
            body: JSON.stringify(data)
        });
    }

    async delete(endpoint) {
        return this.request(endpoint, {
            method: 'DELETE'
        });
    }

    clearCache() {
        this.cache.clear();
    }

    // Remove expired cache entries
    cleanCache() {
        const now = Date.now();
        for (const [key, value] of this.cache.entries()) {
            if (now - value.timestamp >= this.cacheTimeout) {
                this.cache.delete(key);
            }
        }
    }
}

// Enhanced User Manager
class UserManager {
    constructor(apiClient, telegramApp) {
        this.api = apiClient;
        this.tg = telegramApp;
        this.currentUser = null;
        this.isInitialized = false;
    }

    async initUser() {
        const userId = this.tg.getUserId();
        if (!userId) {
            console.warn('No Telegram user ID available');
            return null;
        }

        try {
            // Try to get existing user
            this.currentUser = await this.api.get(`/users/${userId}`, {}, true);
            this.isInitialized = true;
            return this.currentUser;
        } catch (error) {
            // User doesn't exist, create new one
            try {
                const userData = {
                    telegram_id: userId,
                    username: this.tg.getUserName(),
                    first_name: this.tg.getUserFirstName(),
                    last_name: this.tg.getUserLastName(),
                    language_code: this.tg.getInitDataUnsafe()?.user?.language_code || 'ru'
                };

                this.currentUser = await this.api.post('/users/', userData);
                this.isInitialized = true;
                return this.currentUser;
            } catch (createError) {
                console.error('Failed to create user:', createError);
                return null;
            }
        }
    }

    async updateUser(data) {
        if (!this.currentUser) {
            throw new Error('User not initialized');
        }

        try {
            this.currentUser = await this.api.put(`/users/${this.currentUser.telegram_id}`, data);
            return this.currentUser;
        } catch (error) {
            console.error('Failed to update user:', error);
            throw error;
        }
    }

    getCurrentUser() {
        return this.currentUser;
    }

    getUserId() {
        return this.currentUser?.telegram_id || this.tg.getUserId();
    }

    isUserInitialized() {
        return this.isInitialized;
    }
}

// Enhanced Favorites Manager
class FavoritesManager {
    constructor(apiClient, userManager) {
        this.api = apiClient;
        this.userManager = userManager;
        this.favorites = new Set();
        this.listeners = new Set();
    }

    normalizeProductId(productId) {
        if (productId === null || productId === undefined) {
            return '';
        }

        return String(productId).trim();
    }

    async loadFavorites() {
        const userId = this.userManager.getUserId();
        if (!userId) return;

        try {
            // ИСПРАВЛЕНИЕ: Не используем кеш (useCache = false), чтобы всегда получать актуальные данные
            const favorites = await this.api.get(`/users/${userId}/favorites/`, {}, false);
            this.favorites = new Set(
                favorites
                    .map(f => this.normalizeProductId(f.product_id))
                    .filter(Boolean)
            );

            // КРИТИЧЕСКИ ВАЖНО: Сохраняем регионы избранного в localStorage
            favorites.forEach(f => {
                const normalizedProductId = this.normalizeProductId(f.product_id);
                if (normalizedProductId && f.region) {
                    localStorage.setItem(`favorite_region_${normalizedProductId}`, f.region);
                }
            });

            this.notifyListeners();
            return Array.from(this.favorites);
        } catch (error) {
            console.error('Error loading favorites:', error);
            return [];
        }
    }

    async addToFavorites(productId) {
        const userId = this.userManager.getUserId();
        if (!userId) {
            throw new Error('User not authenticated');
        }
        const normalizedProductId = this.normalizeProductId(productId);

        try {
            await this.api.post(`/users/${userId}/favorites/`, {
                product_id: normalizedProductId
            });
            this.favorites.add(normalizedProductId);
            this.notifyListeners();
            return true;
        } catch (error) {
            console.error('Error adding to favorites:', error);
            throw error;
        }
    }

    async removeFromFavorites(productId) {
        const userId = this.userManager.getUserId();
        if (!userId) {
            throw new Error('User not authenticated');
        }
        const normalizedProductId = this.normalizeProductId(productId);

        try {
            await this.api.delete(`/users/${userId}/favorites/${normalizedProductId}`);
            this.favorites.delete(normalizedProductId);

            // КРИТИЧЕСКИ ВАЖНО: Удаляем сохраненный регион из localStorage
            localStorage.removeItem(`favorite_region_${normalizedProductId}`);
            console.log('🗑️ Removed favorite region from localStorage for product:', productId);

            this.notifyListeners();
            return true;
        } catch (error) {
            console.error('Error removing from favorites:', error);
            throw error;
        }
    }

    isFavorite(productId) {
        return this.favorites.has(this.normalizeProductId(productId));
    }

    getFavorites() {
        return Array.from(this.favorites);
    }

    // Event listener pattern for favorites changes
    addListener(callback) {
        this.listeners.add(callback);
    }

    removeListener(callback) {
        this.listeners.delete(callback);
    }

    notifyListeners() {
        this.listeners.forEach(callback => {
            try {
                callback(this.getFavorites());
            } catch (error) {
                console.error('Error in favorites listener:', error);
            }
        });
    }
}

// Enhanced Utility Functions
class Utils {
    static formatPrice(price, currency = 'UAH') {
        if (!price || isNaN(price)) return 'Цена не указана';

        const currencySymbols = {
            'UAH': '₴',
            'TRL': '₺',
            'USD': '$',
            'EUR': '€'
        };

        const symbol = currencySymbols[currency] || currency;
        return `${parseFloat(price).toLocaleString()} ${symbol}`;
    }

    static formatDate(dateString, locale = 'ru-RU') {
        if (!dateString) return '';

        try {
            const date = new Date(dateString);
            return date.toLocaleDateString(locale, {
                year: 'numeric',
                month: 'long',
                day: 'numeric'
            });
        } catch (error) {
            return dateString;
        }
    }

    static truncateText(text, maxLength = 100) {
        if (!text || text.length <= maxLength) return text;
        return text.substring(0, maxLength).trim() + '...';
    }

    static debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func.apply(this, args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }

    static throttle(func, limit) {
        let inThrottle;
        return function() {
            const args = arguments;
            const context = this;
            if (!inThrottle) {
                func.apply(context, args);
                inThrottle = true;
                setTimeout(() => inThrottle = false, limit);
            }
        };
    }

    static showToast(message, type = 'info', duration = 3000) {
        // Create toast container if it doesn't exist
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            container.style.cssText = `
                position: fixed;
                top: 20px;
                right: 20px;
                z-index: 10000;
                display: flex;
                flex-direction: column;
                gap: 10px;
            `;
            document.body.appendChild(container);
        }

        // Create toast
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.cssText = `
            background: var(--tg-theme-bg-color);
            color: var(--tg-theme-text-color);
            border: 1px solid var(--tg-theme-button-color);
            border-radius: var(--border-radius-md);
            padding: var(--spacing-md);
            box-shadow: var(--shadow-lg);
            max-width: 300px;
            animation: slideInRight 0.3s ease-out;
        `;

        const icon = {
            'success': '✅',
            'error': '❌',
            'warning': '⚠️',
            'info': 'ℹ️'
        }[type] || 'ℹ️';

        toast.innerHTML = `
            <div style="display: flex; align-items: center; gap: var(--spacing-sm);">
                <span style="font-size: 1.2em;">${icon}</span>
                <span>${message}</span>
            </div>
        `;

        container.appendChild(toast);

        // Auto remove toast
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-in';
            setTimeout(() => {
                if (toast.parentNode) {
                    toast.parentNode.removeChild(toast);
                }
            }, 300);
        }, duration);

        return toast;
    }

    static createLoadingSkeleton(count = 6) {
        const container = document.createElement('div');
        container.className = 'skeleton-grid';

        for (let i = 0; i < count; i++) {
            const skeleton = document.createElement('div');
            skeleton.className = 'skeleton-card';
            skeleton.innerHTML = `
                <div class="skeleton-image"></div>
                <div class="skeleton-content">
                    <div class="skeleton-text short"></div>
                    <div class="skeleton-text medium"></div>
                    <div class="skeleton-text short"></div>
                </div>
            `;
            container.appendChild(skeleton);
        }

        return container;
    }

    static async loadImage(src) {
        return new Promise((resolve, reject) => {
            const img = new Image();
            img.onload = () => resolve(img);
            img.onerror = reject;
            img.src = src;
        });
    }

    static isValidEmail(email) {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }

    static sanitizeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    static copyToClipboard(text) {
        if (navigator.clipboard) {
            return navigator.clipboard.writeText(text);
        } else {
            // Fallback for older browsers
            const textArea = document.createElement('textarea');
            textArea.value = text;
            document.body.appendChild(textArea);
            textArea.select();
            document.execCommand('copy');
            document.body.removeChild(textArea);
            return Promise.resolve();
        }
    }

    static getQueryParam(param) {
        const urlParams = new URLSearchParams(window.location.search);
        return urlParams.get(param);
    }

    static setQueryParam(param, value) {
        const url = new URL(window.location);
        url.searchParams.set(param, value);
        window.history.replaceState({}, '', url);
    }

    static removeQueryParam(param) {
        const url = new URL(window.location);
        url.searchParams.delete(param);
        window.history.replaceState({}, '', url);
    }
}

// Swipe Gesture Handler
class SwipeGestureHandler {
    constructor() {
        this.startX = 0;
        this.startY = 0;
        this.endX = 0;
        this.endY = 0;
        this.currentX = 0;
        this.currentY = 0;
        this.minSwipeDistance = 80; // Минимальное расстояние для свайпа (уменьшено для лучшей отзывчивости)
        this.maxVerticalDistance = 150; // Максимальное вертикальное отклонение
        this.isEnabled = true;
        this.isSwiping = false;
        this.swipeThreshold = 30; // Порог для начала визуального feedback
        this.swipeIndicator = null;
        this.isMouseDown = false;
        this.hasShownInstruction = localStorage.getItem('swipe_instruction_shown') === 'true';
        this.init();
    }

    init() {
        // Добавляем обработчики touch событий
        document.addEventListener('touchstart', this.handleTouchStart.bind(this), { passive: false });
        document.addEventListener('touchmove', this.handleTouchMove.bind(this), { passive: false });
        document.addEventListener('touchend', this.handleTouchEnd.bind(this), { passive: true });
        document.addEventListener('touchcancel', this.handleTouchCancel.bind(this), { passive: true });

        // Обработчик для десктопных браузеров (mouse события)
        document.addEventListener('mousedown', this.handleMouseDown.bind(this));
        document.addEventListener('mousemove', this.handleMouseMove.bind(this));
        document.addEventListener('mouseup', this.handleMouseUp.bind(this));
        document.addEventListener('mouseleave', this.handleMouseLeave.bind(this));

        // Создаем индикатор свайпа
        this.createSwipeIndicator();

        // Показываем инструкцию для новых пользователей
        if (!this.hasShownInstruction) {
            setTimeout(() => this.showSwipeInstruction(), 2000);
        }
    }

    handleTouchStart(event) {
        if (!this.isEnabled) return;

        const touch = event.touches[0];
        this.startX = touch.clientX;
        this.startY = touch.clientY;
        this.currentX = touch.clientX;
        this.currentY = touch.clientY;
        this.isSwiping = false;

        // Добавляем класс для предотвращения выделения текста
        document.body.classList.add('swipe-active');
    }

    handleTouchMove(event) {
        if (!this.isEnabled) return;

        const touch = event.touches[0];
        this.currentX = touch.clientX;
        this.currentY = touch.clientY;

        const deltaX = this.currentX - this.startX;
        const deltaY = Math.abs(this.currentY - this.startY);

        // Проверяем, начался ли свайп
        if (!this.isSwiping && Math.abs(deltaX) > this.swipeThreshold && deltaY < this.maxVerticalDistance) {
            this.isSwiping = true;
            document.body.classList.add('swipe-area');
        }

        // Показываем визуальную обратную связь для свайпа вправо
        if (this.isSwiping && deltaX > 0) {
            this.showSwipeIndicator();
            // Предотвращаем прокрутку страницы при горизонтальном свайпе
            event.preventDefault();
        }
    }

    handleTouchEnd(event) {
        if (!this.isEnabled) return;

        const touch = event.changedTouches[0];
        this.endX = touch.clientX;
        this.endY = touch.clientY;

        // Убираем классы
        document.body.classList.remove('swipe-active', 'swipe-area');
        this.hideSwipeIndicator();

        if (this.isSwiping) {
            this.handleSwipe();
        }

        this.isSwiping = false;
    }

    handleTouchCancel(event) {
        if (!this.isEnabled) return;

        // Сбрасываем состояние при отмене touch события
        document.body.classList.remove('swipe-active', 'swipe-area');
        this.hideSwipeIndicator();
        this.isSwiping = false;
    }

    handleMouseDown(event) {
        if (!this.isEnabled) return;

        this.startX = event.clientX;
        this.startY = event.clientY;
        this.currentX = event.clientX;
        this.currentY = event.clientY;
        this.isMouseDown = true;
        this.isSwiping = false;

        document.body.classList.add('swipe-active');
    }

    handleMouseMove(event) {
        if (!this.isEnabled || !this.isMouseDown) return;

        this.currentX = event.clientX;
        this.currentY = event.clientY;

        const deltaX = this.currentX - this.startX;
        const deltaY = Math.abs(this.currentY - this.startY);

        if (!this.isSwiping && Math.abs(deltaX) > this.swipeThreshold && deltaY < this.maxVerticalDistance) {
            this.isSwiping = true;
            document.body.classList.add('swipe-area');
        }

        if (this.isSwiping && deltaX > 0) {
            this.showSwipeIndicator();
        }
    }

    handleMouseUp(event) {
        if (!this.isEnabled || !this.isMouseDown) return;

        this.endX = event.clientX;
        this.endY = event.clientY;
        this.isMouseDown = false;

        document.body.classList.remove('swipe-active', 'swipe-area');
        this.hideSwipeIndicator();

        if (this.isSwiping) {
            this.handleSwipe();
        }

        this.isSwiping = false;
    }

    handleMouseLeave(event) {
        if (!this.isEnabled || !this.isMouseDown) return;

        // Сбрасываем состояние при выходе мыши за пределы документа
        this.isMouseDown = false;
        this.isSwiping = false;
        document.body.classList.remove('swipe-active', 'swipe-area');
        this.hideSwipeIndicator();
    }

    handleSwipe() {
        const deltaX = this.endX - this.startX;
        const deltaY = Math.abs(this.endY - this.startY);

        // Проверяем, что это горизонтальный свайп
        if (deltaY > this.maxVerticalDistance) {
            return;
        }

        // Свайп вправо (назад)
        if (deltaX > this.minSwipeDistance) {
            this.onSwipeRight();
        }
        // Свайп влево (вперед) - можно использовать для других целей
        else if (deltaX < -this.minSwipeDistance) {
            this.onSwipeLeft();
        }
    }

    onSwipeRight() {
        // Свайп вправо - возврат назад
        console.log('Swipe right detected - going back');

        // Тактильная обратная связь
        if (window.tgApp && window.tgApp.hapticFeedback) {
            window.tgApp.hapticFeedback('impact', 'light');
        }

        // Переход назад
        this.goBack();
    }

    onSwipeLeft() {
        // Свайп влево - можно использовать для других действий
        console.log('Swipe left detected');

        // Тактильная обратная связь
        if (window.tgApp && window.tgApp.hapticFeedback) {
            window.tgApp.hapticFeedback('selection');
        }
    }

    goBack() {
        // Если есть Telegram WebApp, используем его навигацию
        if (window.tgApp && window.tgApp.goBack) {
            window.tgApp.goBack();
            return;
        }

        // Иначе используем стандартную браузерную навигацию
        if (window.history.length > 1) {
            window.history.back();
        } else {
            // Если нет истории, закрываем WebApp или переходим на главную
            if (window.location.pathname !== '/webapp/' && window.location.pathname !== '/webapp') {
                window.location.href = '/webapp/';
            }
        }
    }

    enable() {
        this.isEnabled = true;
    }

    disable() {
        this.isEnabled = false;
    }

    // Метод для временного отключения свайпов (например, во время прокрутки)
    temporaryDisable(duration = 500) {
        this.disable();
        setTimeout(() => this.enable(), duration);
    }

    createSwipeIndicator() {
        this.swipeIndicator = document.createElement('div');
        this.swipeIndicator.className = 'swipe-indicator';
        this.swipeIndicator.innerHTML = '←';
        document.body.appendChild(this.swipeIndicator);
    }

    showSwipeIndicator() {
        if (this.swipeIndicator) {
            this.swipeIndicator.classList.add('show');
        }
    }

    hideSwipeIndicator() {
        if (this.swipeIndicator) {
            this.swipeIndicator.classList.remove('show');
        }
    }

    showSwipeInstruction() {
        const instruction = document.createElement('div');
        instruction.className = 'swipe-instruction';
        instruction.innerHTML = `
            <div class="swipe-instruction-content">
                <div class="swipe-instruction-icon">👈</div>
                <div class="swipe-instruction-title">Свайп для навигации</div>
                <div class="swipe-instruction-text">
                    Проведите пальцем вправо для возврата на предыдущую страницу
                </div>
                <button class="btn btn-primary" onclick="this.parentElement.parentElement.remove()">
                    Понятно
                </button>
            </div>
        `;

        document.body.appendChild(instruction);

        // Показываем инструкцию
        setTimeout(() => {
            instruction.classList.add('show');
        }, 100);

        // Автоматически скрываем через 5 секунд
        setTimeout(() => {
            instruction.classList.remove('show');
            setTimeout(() => {
                if (instruction.parentElement) {
                    instruction.parentElement.removeChild(instruction);
                }
            }, 300);
        }, 5000);

        // Помечаем, что инструкция была показана
        localStorage.setItem('swipe_instruction_shown', 'true');
        this.hasShownInstruction = true;

        // Добавляем обработчик клика для закрытия
        instruction.addEventListener('click', (event) => {
            if (event.target === instruction) {
                instruction.classList.remove('show');
                setTimeout(() => {
                    if (instruction.parentElement) {
                        instruction.parentElement.removeChild(instruction);
                    }
                }, 300);
            }
        });
    }

    // Метод для принудительного показа инструкции (для отладки)
    forceShowInstruction() {
        localStorage.removeItem('swipe_instruction_shown');
        this.hasShownInstruction = false;
        this.showSwipeInstruction();
    }
}

// Initialize global instances
const tgApp = new TelegramWebApp();
const apiClient = new APIClient();
const userManager = new UserManager(apiClient, tgApp);
const favoritesManager = new FavoritesManager(apiClient, userManager);
const swipeHandler = new SwipeGestureHandler();

// Export to window for global access
window.tgApp = tgApp;
window.apiClient = apiClient;
window.userManager = userManager;
window.favoritesManager = favoritesManager;
window.swipeHandler = swipeHandler;

// Add CSS animations for toasts
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }

    @keyframes slideOutRight {
        from { transform: translateX(0); opacity: 1; }
        to { transform: translateX(100%); opacity: 0; }
    }
`;
document.head.appendChild(style);

// Auto-initialize user when app loads
document.addEventListener('DOMContentLoaded', async () => {
    try {
        if (tgApp.isReady()) {
            await userManager.initUser();
            // ОПТИМИЗАЦИЯ: loadFavorites вызывается в ModernProductCatalog.init()
            // Убираем дублирующий вызов здесь
            // await favoritesManager.loadFavorites();
        }
    } catch (error) {
        console.error('Error during app initialization:', error);
    }

    // Setup back button visibility
    setupBackButtonVisibility();

    // Clean API cache periodically
    setInterval(() => {
        apiClient.cleanCache();
    }, 60000); // Clean every minute
});

// Setup back button visibility management
function setupBackButtonVisibility() {
    const backButton = document.getElementById('backButton');
    if (!backButton) return;

    // Show back button on non-main pages
    function updateBackButtonVisibility() {
        const isMainPage = window.location.pathname === '/webapp/' ||
                          window.location.pathname === '/webapp' ||
                          window.location.pathname === '/';

        const hasHistory = window.history.length > 1;

        if (!isMainPage && hasHistory) {
            backButton.classList.add('show');
        } else {
            backButton.classList.remove('show');
        }

        // ИСПРАВЛЕНИЕ iOS: Управление Telegram BackButton
        updateTelegramBackButton(isMainPage);
    }

    // Update on page load
    updateBackButtonVisibility();

    // Update on navigation
    window.addEventListener('popstate', updateBackButtonVisibility);

    // ИСПРАВЛЕНИЕ iOS BFCache: Обновляем при загрузке страницы из кеша
    window.addEventListener('pageshow', (event) => {
        console.log('📄 [app.js] pageshow event, persisted:', event.persisted);
        updateBackButtonVisibility();
    });

    // Update when location changes (for SPA navigation)
    const originalPushState = history.pushState;
    const originalReplaceState = history.replaceState;

    history.pushState = function() {
        originalPushState.apply(history, arguments);
        setTimeout(updateBackButtonVisibility, 100);
    };

    history.replaceState = function() {
        originalReplaceState.apply(history, arguments);
        setTimeout(updateBackButtonVisibility, 100);
    };
}

// iOS: Функция для управления Telegram BackButton
function updateTelegramBackButton(isMainPage) {
    const tg = window.Telegram?.WebApp;
    if (!tg || !tg.BackButton) return;

    if (isMainPage) {
        // На главной странице скрываем BackButton - Telegram покажет кнопку "Закрыть"
        tg.BackButton.hide();
        console.log('✅ [app.js] Telegram BackButton hidden (main page)');
    }
    // Примечание: на других страницах BackButton показывается в их собственном коде
}

// Export for global access
window.TelegramWebApp = TelegramWebApp;
window.APIClient = APIClient;
window.UserManager = UserManager;
window.FavoritesManager = FavoritesManager;
window.SwipeGestureHandler = SwipeGestureHandler;
window.Utils = Utils;
