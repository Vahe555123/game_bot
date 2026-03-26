# Deploy через GitHub -> VPS

Этот файл описывает схему, при которой:

- `origin` указывает на GitHub
- ты делаешь `git push origin main`
- GitHub Actions подключается к VPS по SSH
- на сервере подтягивается свежий код
- сервис автоматически перезапускается

## Что рекомендую для этого проекта

Для этого проекта лучше не хранить рабочую SQLite базу и `.env` внутри git-деплоя.

Причина:

- `.env` содержит секреты
- `products.db` может быть перезаписан при деплое

Лучше так:

- код: `/home/deploy/apps/game_bot2`
- `.env`: `/home/deploy/apps/game_bot2/.env`
- база: `/home/deploy/data/game_bot2/products.db`

Тогда в `.env` на сервере:

```env
DATABASE_URL=sqlite:////home/deploy/data/game_bot2/products.db
```

## 1. Подготовить VPS

Под `root`:

```bash
apt update && apt upgrade -y
apt install -y git python3 python3-venv python3-pip nginx
adduser deploy
usermod -aG sudo deploy
```

Переключиться на пользователя `deploy`:

```bash
su - deploy
mkdir -p ~/apps/game_bot2
mkdir -p ~/data/game_bot2
mkdir -p ~/.ssh
chmod 700 ~/.ssh
```

## 2. Залить SSH-ключ для GitHub Actions

На локальной машине сгенерируй отдельный deploy-ключ:

```bash
ssh-keygen -t ed25519 -f github_actions_deploy -C "github-actions-game-bot2"
```

Добавь публичный ключ на VPS:

```bash
cat github_actions_deploy.pub
```

Скопируй вывод в:

```bash
nano /home/deploy/.ssh/authorized_keys
chmod 600 /home/deploy/.ssh/authorized_keys
```

## 3. Клонировать проект на сервер

Под `deploy`:

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
DEBUG=false
HOST=127.0.0.1
PORT=8000

DATABASE_URL=sqlite:////home/deploy/data/game_bot2/products.db

TELEGRAM_BOT_TOKEN=PUT_YOUR_TOKEN_HERE
WEBAPP_URL=https://your-domain.com/webapp
MANAGER_TELEGRAM_URL=https://t.me/your_manager_username
ADMIN_TELEGRAM_IDS=123456789
```

Если у тебя уже есть локальная база и ее нужно перенести:

```bash
scp products.db deploy@YOUR_VPS_IP:/home/deploy/data/game_bot2/products.db
```

## 5. Создать systemd-сервис

Файл:

```bash
sudo nano /etc/systemd/system/game_bot2.service
```

Содержимое:

```ini
[Unit]
Description=game_bot2 FastAPI service
After=network.target

[Service]
User=deploy
Group=deploy
WorkingDirectory=/home/deploy/apps/game_bot2
Environment="PYTHONIOENCODING=utf-8"
ExecStart=/home/deploy/apps/game_bot2/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Запуск:

```bash
sudo systemctl daemon-reload
sudo systemctl enable game_bot2
sudo systemctl start game_bot2
sudo systemctl status game_bot2
```

## 6. Настроить nginx

Файл:

```bash
sudo nano /etc/nginx/sites-available/game_bot2
```

Содержимое:

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

Включить:

```bash
sudo ln -s /etc/nginx/sites-available/game_bot2 /etc/nginx/sites-enabled/game_bot2
sudo nginx -t
sudo systemctl reload nginx
```

## 7. Настроить HTTPS

Если домен уже указывает на VPS:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

После этого в `.env`:

```env
WEBAPP_URL=https://your-domain.com/webapp
```

## 8. Добавить GitHub Secrets

В GitHub репозитории открой:

- `Settings`
- `Secrets and variables`
- `Actions`

Создай secrets:

- `VPS_HOST` = IP или домен сервера
- `VPS_USER` = `deploy`
- `VPS_PORT` = `22`
- `VPS_SSH_KEY` = содержимое файла `github_actions_deploy`

Приватный ключ добавить так:

```bash
cat github_actions_deploy
```

Скопируй весь файл целиком в `VPS_SSH_KEY`.

## 9. Создать GitHub Actions workflow

Создай файл:

```text
.github/workflows/deploy.yml
```

Содержимое:

```yaml
name: Deploy to VPS

on:
  push:
    branches:
      - main

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Deploy over SSH
        uses: appleboy/ssh-action@v1.2.0
        with:
          host: ${{ secrets.VPS_HOST }}
          username: ${{ secrets.VPS_USER }}
          key: ${{ secrets.VPS_SSH_KEY }}
          port: ${{ secrets.VPS_PORT }}
          script: |
            set -e
            cd /home/deploy/apps/game_bot2
            git fetch origin main
            git reset --hard origin/main

            if [ ! -d ".venv" ]; then
              python3 -m venv .venv
            fi

            .venv/bin/pip install --upgrade pip
            .venv/bin/pip install -r requirements.txt

            sudo systemctl restart game_bot2
            sudo systemctl status game_bot2 --no-pager
```

## 10. Разрешить restart сервиса без пароля

На VPS:

```bash
sudo visudo
```

Добавь строку:

```text
deploy ALL=NOPASSWD: /bin/systemctl restart game_bot2, /bin/systemctl status game_bot2 --no-pager
```

## 11. Как теперь деплоить

Локально:

```bash
git add .
git commit -m "update"
git push origin main
```

Что произойдет:

1. Код уйдет в GitHub
2. GitHub Actions запустится автоматически
3. Сервер выполнит `git fetch` + `git reset --hard origin/main`
4. Обновятся зависимости
5. `game_bot2` будет перезапущен

## 12. Проверка и логи

На VPS:

```bash
journalctl -u game_bot2 -f
```

Проверка GitHub Actions:

- открой репозиторий на GitHub
- вкладка `Actions`
- открой последний запуск `Deploy to VPS`

## 13. Важные замечания

- Не коммить реальный `.env`
- Не держи рабочую SQLite базу внутри git-репозитория
- Если на сервере меняются файлы вручную внутри `/home/deploy/apps/game_bot2`, следующий деплой их затрет
- Для production используй домен и HTTPS, а не dev tunnel

## 14. Минимальный итог

Тебе нужно сделать только это:

1. Поднять VPS
2. Настроить `systemd`
3. Настроить `nginx`
4. Добавить GitHub Secrets
5. Создать `.github/workflows/deploy.yml`
6. Пушить в `main`

Если нужен следующий шаг, я могу сразу добавить в проект готовый `.github/workflows/deploy.yml` и шаблон `.gitignore` под этот деплой.
