# Deploy через GitHub -> VPS -> PM2

Этот вариант делает ровно то, что тебе нужно:

- `git push origin main`
- GitHub Actions подключается к VPS
- сервер подтягивает свежий код
- PM2 перезапускает приложение автоматически

## Как устроен этот проект сейчас

У тебя **web app и Telegram-бот живут в одном процессе**.

Это важно:

- FastAPI стартует из `main.py`
- бот поднимается в `lifespan`, если есть `TELEGRAM_BOT_TOKEN`
- при `DEBUG=true` бот запускается в polling
- при `DEBUG=false` код пытается перейти на webhook

В текущем коде webhook-эндпоинта для Telegram нет, поэтому **если бот нужен именно сейчас, на сервере оставляй `DEBUG=true`**.

Это нормально для этого проекта, потому что PM2 мы запускаем через `uvicorn`, а не через `python main.py`, то есть `DEBUG=true` здесь включает polling бота, но не включает uvicorn reload.

## 1. Установить на VPS Node.js, npm и PM2

Под `root`:

```bash
apt update && apt upgrade -y
apt install -y git python3 python3-venv python3-pip nginx nodejs npm
npm install -g pm2
```

Проверь:

```bash
pm2 -v
node -v
npm -v
```

## 2. Подготовить папки на сервере

Под пользователем `deploy`:

```bash
mkdir -p /home/deploy/apps/game_bot2
mkdir -p /home/deploy/data/game_bot2
mkdir -p /home/deploy/.ssh
chmod 700 /home/deploy/.ssh
```

## 3. Клонировать проект на VPS

```bash
cd /home/deploy/apps
git clone https://github.com/YOUR_GITHUB_USERNAME/YOUR_REPO.git game_bot2
cd /home/deploy/apps/game_bot2
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

## 4. Создать `.env` на сервере

Файл:

```bash
nano /home/deploy/apps/game_bot2/.env
```

Пример:

```env
DEBUG=true
HOST=127.0.0.1
PORT=8000

DATABASE_URL=sqlite:////home/deploy/data/game_bot2/products.db

TELEGRAM_BOT_TOKEN=PUT_YOUR_TOKEN_HERE
WEBAPP_URL=https://your-domain.com/webapp
MANAGER_TELEGRAM_URL=https://t.me/your_manager_username
ADMIN_TELEGRAM_IDS=123456789
```

Если нужно перенести текущую SQLite базу:

```bash
scp products.db deploy@YOUR_VPS_IP:/home/deploy/data/game_bot2/products.db
```

## 5. Что уже добавлено в репозиторий

В проект уже добавлены:

- `start_pm2.sh`
- `ecosystem.config.cjs`
- `.github/workflows/deploy.yml`

PM2 будет запускать приложение через:

```bash
./.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
```

Хост и порт берутся из `.env`.

## 6. GitHub Secrets

В репозитории GitHub нужны secrets:

- `VPS_HOST`
- `VPS_USER`
- `VPS_PORT`
- `VPS_SSH_KEY`

Где:

- `VPS_HOST` = IP или домен VPS
- `VPS_USER` = `deploy`
- `VPS_PORT` = `22`
- `VPS_SSH_KEY` = приватный ключ для GitHub Actions

## 7. Как работает деплой

Workflow при пуше в `main` делает:

1. SSH на VPS
2. `git fetch origin main`
3. `git reset --hard origin/main`
4. обновляет Python-зависимости
5. выполняет:

```bash
pm2 startOrReload ecosystem.config.cjs --only game_bot2 --update-env
pm2 save
pm2 show game_bot2
```

## 8. Как первый раз запустить через PM2 на сервере

На VPS:

```bash
cd /home/deploy/apps/game_bot2
chmod +x start_pm2.sh
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup
```

После `pm2 startup` PM2 покажет команду вида:

```bash
sudo env PATH=$PATH:/usr/bin pm2 startup systemd -u deploy --hp /home/deploy
```

Ее нужно просто скопировать и выполнить один раз.

## 9. Как понять, включен ли бот

На сервере проверь:

```bash
cat /home/deploy/apps/game_bot2/.env | grep -E '^(DEBUG|TELEGRAM_BOT_TOKEN|TELEGRAM_WEBHOOK_URL)='
```

Логика такая:

- если `TELEGRAM_BOT_TOKEN` пустой -> бот выключен
- если `TELEGRAM_BOT_TOKEN` заполнен и `DEBUG=true` -> бот должен стартовать в polling
- если `DEBUG=false` -> бот уйдет в webhook-режим, но в текущем проекте webhook-роута нет

Лучший практический способ проверки:

```bash
pm2 logs game_bot2 --lines 100
```

Если бот поднялся, в логах будут строки вроде:

- `ИНФОРМАЦИЯ О TELEGRAM БОТЕ`
- `Бот готов к приему команд`

## 10. Как понять, на каком порту работает приложение

Смотри значение `PORT` в `.env`:

```bash
cat /home/deploy/apps/game_bot2/.env | grep '^PORT='
```

И проверь, что процесс реально слушает этот порт:

```bash
ss -ltnp | grep 8000
```

Проверка health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

## 11. Полезные PM2-команды

Статус:

```bash
pm2 list
pm2 show game_bot2
```

Логи:

```bash
pm2 logs game_bot2
pm2 logs game_bot2 --lines 200
```

Перезапуск:

```bash
pm2 restart game_bot2
```

Остановка:

```bash
pm2 stop game_bot2
```

Удаление из PM2:

```bash
pm2 delete game_bot2
```

## 12. HTTPS и nginx

Nginx по-прежнему нужен как reverse proxy перед PM2-приложением.

Пример:

```nginx
server {
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

HTTPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

## 13. Как теперь деплоить

Локально:

```bash
git add .
git commit -m "update"
git push origin main
```

После этого:

- код обновится на VPS
- PM2 перезапустит процесс
- бот и web app поднимутся в одном процессе

## 14. Самое важное в твоем случае

Если ты хочешь, чтобы бот реально работал сейчас, на сервере для этого проекта оставь:

```env
DEBUG=true
TELEGRAM_BOT_TOKEN=...
PORT=8000
```

А статус потом смотри так:

```bash
pm2 show game_bot2
pm2 logs game_bot2 --lines 100
curl http://127.0.0.1:8000/health
```
