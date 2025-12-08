# 🚀 Деплой на сервер

## Информация о сервере

- **IP адрес:** 31.172.64.62
- **Домен:** watcher.negarant.org
- **ОС:** Linux (предполагается Ubuntu/Debian)

---

## 📋 Чеклист перед деплоем

- [ ] Сервер доступен по SSH
- [ ] Установлен Python 3.10+
- [ ] Установлен PostgreSQL
- [ ] Установлен Redis
- [ ] Установлен Nginx (для проксирования)
- [ ] Домен настроен и указывает на IP сервера
- [ ] Порты открыты: 80, 443, 22

---

## 1️⃣ Подготовка сервера

### Подключение к серверу

```bash
ssh user@31.172.64.62
# или
ssh user@watcher.negarant.org
```

### Обновление системы

```bash
sudo apt update
sudo apt upgrade -y
```

### Установка необходимых пакетов

```bash
# Python и pip
sudo apt install python3 python3-pip python3-venv -y

# PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Redis
sudo apt install redis-server -y

# Nginx
sudo apt install nginx -y

# Git (если еще не установлен)
sudo apt install git -y

# Node.js и npm (для сборки фронтенда)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

---

## 2️⃣ Настройка PostgreSQL

### Создание базы данных

```bash
# Переключиться на пользователя postgres
sudo -u postgres psql

# В psql выполнить:
CREATE DATABASE cryptowatcher;
CREATE USER cryptouser WITH PASSWORD 'ваш_надежный_пароль';
GRANT ALL PRIVILEGES ON DATABASE cryptowatcher TO cryptouser;

-- Важно: Выдать права на схему public (нужно для миграций)
\c cryptowatcher
GRANT ALL ON SCHEMA public TO cryptouser;
GRANT CREATE ON SCHEMA public TO cryptouser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO cryptouser;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO cryptouser;

\q
```

### Настройка PostgreSQL для удаленного доступа (если нужно)

```bash
sudo nano /etc/postgresql/*/main/postgresql.conf
# Найти и раскомментировать:
# listen_addresses = 'localhost'

sudo nano /etc/postgresql/*/main/pg_hba.conf
# Добавить:
# host    cryptowatcher    cryptouser    0.0.0.0/0    md5
```

---

## 3️⃣ Настройка Redis

```bash
# Запустить Redis
sudo systemctl start redis-server

# Включить автозапуск
sudo systemctl enable redis-server

# Проверить статус
sudo systemctl status redis-server
```

---

## 4️⃣ Клонирование проекта

### Создание директории для проекта

```bash
# Создать директорию
mkdir -p /root/cryptowatcher
cd /root/cryptowatcher
```

### Клонирование репозитория

```bash
# Если используете Git
git clone <ваш_репозиторий> .

# Или загрузите файлы через SCP/SFTP
```

---

## 5️⃣ Настройка Backend

### Установка зависимостей

```bash
cd backend

# Удалить старое venv если есть (venv не нужно копировать на сервер!)
rm -rf venv

# Создать новое виртуальное окружение
python3 -m venv venv

# Активировать
source venv/bin/activate

# Обновить pip
pip install --upgrade pip

# Установить зависимости
pip install -r requirements.txt

# Проверить установку
pip list
```

### Настройка переменных окружения

```bash
# Создать .env файл
cp env.example.txt .env
nano .env
```

**Содержимое `.env` для продакшена (в корне проекта `/root/cryptowatcher/.env`):**

```env
# ============================================
# BACKEND НАСТРОЙКИ
# ============================================

# Application
DEBUG=False

# Database
DATABASE_URL=postgresql://cryptouser:ваш_надежный_пароль@localhost:5432/cryptowatcher

# Redis
REDIS_URL=redis://localhost:6379/0

# CoinGecko API (опционально)
COINGECKO_API_KEY=ваш_api_ключ

# Telegram Bot API
TELEGRAM_BOT_TOKEN=ваш_токен_бота

# CORS - ваш домен
ALLOWED_ORIGINS=https://watcher.negarant.org,http://watcher.negarant.org

# ============================================
# FRONTEND НАСТРОЙКИ
# ============================================

# API URL (БЕЗ /api в конце!)
VITE_API_BASE_URL=https://watcher.negarant.org
```

**Важно:** Все переменные окружения теперь в ОДНОМ файле `.env` в корне проекта!

### Применение миграций

```bash
# Убедитесь что вы в директории backend
cd /root/cryptowatcher/backend

# Активировать venv если еще не активирован
source venv/bin/activate

# Проверить что alembic.ini существует
ls -la alembic.ini

# Проверить текущую версию БД
alembic current

# Применить миграции
alembic upgrade head

# Проверить что миграции применены
alembic current
```

**Если ошибка "No config file 'alembic.ini' found":**
- Убедитесь что вы в директории `/root/cryptowatcher/backend`
- Проверьте что файл `alembic.ini` скопирован на сервер
- Проверьте что папка `alembic/` также скопирована

### Тестовый запуск backend

```bash
# Запустить на порту 8000
    python run.py

# Или через uvicorn напрямую
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Проверить: `http://31.172.64.62:8000/health`

---

## 6️⃣ Настройка Frontend

### Установка зависимостей

```bash
cd frontend

# Удалить старые зависимости если есть (чтобы избежать проблем с правами)
rm -rf node_modules package-lock.json

# Установить зависимости заново
npm install
```

### Настройка переменных окружения

**Теперь используется ОДИН общий `.env` файл в корне проекта!**

Создайте файл `.env` в корне проекта (`/root/cryptowatcher/.env`):

```bash
cd /root/cryptowatcher

# Скопировать пример
cp env.example.txt .env

# Отредактировать
nano .env
```

Или создать напрямую:

```bash
cd /root/cryptowatcher

cat > .env << 'EOF'
# Backend настройки
DATABASE_URL=postgresql://cryptouser:ВАШ_ПАРОЛЬ@localhost:5432/cryptowatcher
ALLOWED_ORIGINS=https://watcher.negarant.org,http://watcher.negarant.org
TELEGRAM_BOT_TOKEN=ВАШ_ТОКЕН
DEBUG=False
REDIS_URL=redis://localhost:6379/0
COINGECKO_API_KEY=

# Frontend настройки (БЕЗ /api в конце!)
VITE_API_BASE_URL=https://watcher.negarant.org
EOF
```

**Важно:**
- Все переменные в ОДНОМ файле `.env` в корне проекта
- `VITE_API_BASE_URL` БЕЗ `/api` в конце (иначе будет `/api/api/v1`)

### Сборка для продакшена

```bash
# Проверить что зависимости установлены
npm list --depth=0

# Собрать проект
npm run build
```

**Если ошибка "Permission denied":**
```bash
# Переустановить зависимости
rm -rf node_modules package-lock.json
npm install
npm run build
```

Результат будет в `frontend/dist/`

**Важно:** Фронтенд не требует отдельного процесса! Это статические файлы, которые Nginx отдает автоматически. После сборки файлы сразу доступны через веб-сервер.

---

## 7️⃣ Настройка Nginx

### Создание конфигурации

```bash
sudo nano /etc/nginx/sites-available/watcher.negarant.org
```

**Содержимое конфигурации:**

```nginx
# Редирект с HTTP на HTTPS
server {
    listen 80;
    server_name watcher.negarant.org;
    
    location /.well-known/acme-challenge/ {
        root /var/www/html;
    }
    
    location / {
        return 301 https://$server_name$request_uri;
    }
}

# HTTPS сервер
server {
    listen 443 ssl http2;
    server_name watcher.negarant.org;

    # SSL сертификаты (будут настроены через Certbot)
    ssl_certificate /etc/letsencrypt/live/watcher.negarant.org/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/watcher.negarant.org/privkey.pem;
    
    # SSL настройки
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;

    # Максимальный размер загружаемых файлов
    client_max_body_size 10M;

    # Логи
    access_log /var/log/nginx/watcher_access.log;
    error_log /var/log/nginx/watcher_error.log;

    # Статические файлы фронтенда
    location / {
        root /root/cryptowatcher/frontend/dist;
        try_files $uri $uri/ /index.html;
        
        # Кэширование статических файлов
        location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff|woff2|ttf|eot)$ {
            expires 1y;
            add_header Cache-Control "public, immutable";
        }
    }

    # API проксирование на backend
    location /api {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Таймауты
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        access_log off;
    }
}
```

### Активация конфигурации

```bash
# Создать симлинк
sudo ln -s /etc/nginx/sites-available/watcher.negarant.org /etc/nginx/sites-enabled/

# Проверить конфигурацию
sudo nginx -t

# Перезагрузить Nginx
sudo systemctl reload nginx
```

---

## 8️⃣ Настройка SSL (Let's Encrypt)

### Предварительная проверка

```bash
# Убедитесь что домен указывает на сервер
nslookup watcher.negarant.org
# Должен вернуть: 31.172.64.62

# Убедитесь что порты открыты
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
```

### Установка Certbot

```bash
sudo apt install certbot python3-certbot-nginx -y
```

### Получение сертификата

**Вариант 1: Автоматическая настройка (если Nginx уже настроен)**

```bash
sudo certbot --nginx -d watcher.negarant.org
```

Следуйте инструкциям:
- Введите email
- Согласитесь с условиями
- Выберите редирект с HTTP на HTTPS (рекомендуется: 2)

**Вариант 2: Ручная настройка (если Nginx еще не настроен)**

```bash
# Остановить Nginx временно
sudo systemctl stop nginx

# Получить сертификат
sudo certbot certonly --standalone -d watcher.negarant.org

# Запустить Nginx
sudo systemctl start nginx
```

Затем добавьте в конфигурацию Nginx:
```nginx
ssl_certificate /etc/letsencrypt/live/watcher.negarant.org/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/watcher.negarant.org/privkey.pem;
```

### Проверка сертификата

```bash
# Проверить список сертификатов
sudo certbot certificates

# Проверить срок действия
echo | openssl s_client -connect watcher.negarant.org:443 -servername watcher.negarant.org 2>/dev/null | \
  openssl x509 -noout -dates
```

### Автообновление сертификата

```bash
# Проверить автообновление (тестовый режим)
sudo certbot renew --dry-run
```

Certbot автоматически настроит cron для обновления сертификатов за 30 дней до истечения.

**Подробная инструкция:** См. `SSL_SETUP.md`

---

## 9️⃣ Настройка systemd для Backend

### Создание сервиса

```bash
sudo nano /etc/systemd/system/cryptowatcher.service
```

**Содержимое (если venv в корне проекта `/root/cryptowatcher/venv`):**

```ini
[Unit]
Description=CryptoWatcher Backend API
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/cryptowatcher/backend
Environment="PATH=/root/cryptowatcher/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/root/cryptowatcher/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

**Если venv в директории backend (`/root/cryptowatcher/backend/venv`):**

```ini
Environment="PATH=/root/cryptowatcher/backend/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
ExecStart=/root/cryptowatcher/backend/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**Важно:** 
- Замените пути на актуальные в зависимости от расположения venv
- Используйте `python -m uvicorn` вместо прямого вызова `uvicorn` для надежности

### Запуск сервиса

```bash
# Перезагрузить systemd
sudo systemctl daemon-reload

# Включить автозапуск
sudo systemctl enable cryptowatcher

# Запустить сервис
sudo systemctl start cryptowatcher

# Проверить статус
sudo systemctl status cryptowatcher

# Просмотр логов
sudo journalctl -u cryptowatcher -f
```

---

## 🔟 Финальная проверка

### Проверка сервисов

```bash
# PostgreSQL
sudo systemctl status postgresql

# Redis
sudo systemctl status redis-server

# Nginx
sudo systemctl status nginx

# Backend
sudo systemctl status cryptowatcher
```

### Проверка доступности

```bash
# Health check API
curl https://watcher.negarant.org/health

# Проверка фронтенда
curl https://watcher.negarant.org
```

### Проверка логов

```bash
# Backend логи
sudo journalctl -u cryptowatcher -n 50

# Nginx логи
sudo tail -f /var/log/nginx/watcher_access.log
sudo tail -f /var/log/nginx/watcher_error.log
```

---

## 🔄 Обновление приложения

### Процесс обновления

```bash
# 1. Остановить сервис
sudo systemctl stop cryptowatcher

# 2. Обновить код (если используете Git)
cd /root/cryptowatcher
git pull

# 3. Обновить зависимости backend
cd backend
source venv/bin/activate
pip install -r requirements.txt

# 4. Применить миграции (если есть новые)
alembic upgrade head

# 5. Обновить зависимости frontend
cd ../frontend
npm install

# 6. Пересобрать фронтенд
npm run build

# 7. Перезапустить сервис
sudo systemctl start cryptowatcher

# 8. Перезагрузить Nginx
sudo systemctl reload nginx
```

---

## 🛠️ Полезные команды

### Управление сервисом

```bash
# Запуск
sudo systemctl start cryptowatcher

# Остановка
sudo systemctl stop cryptowatcher

# Перезапуск
sudo systemctl restart cryptowatcher

# Статус
sudo systemctl status cryptowatcher

# Логи
sudo journalctl -u cryptowatcher -f
```

### Управление Nginx

```bash
# Перезагрузить конфигурацию
sudo systemctl reload nginx

# Перезапустить
sudo systemctl restart nginx

# Проверить конфигурацию
sudo nginx -t
```

### Мониторинг

```bash
# Использование ресурсов
htop

# Использование диска
df -h

# Использование памяти
free -h

# Активные соединения
sudo netstat -tulpn | grep :8000
```

---

## 🐛 Решение проблем

### Backend не запускается

```bash
# Проверить логи
sudo journalctl -u cryptowatcher -n 100

# Проверить порт
sudo netstat -tulpn | grep 8000

# Проверить переменные окружения
sudo systemctl show cryptowatcher | grep Environment
```

### Nginx возвращает 502 Bad Gateway

```bash
# Проверить что backend запущен
sudo systemctl status cryptowatcher

# Проверить что backend слушает на 127.0.0.1:8000
curl http://127.0.0.1:8000/health

# Проверить логи Nginx
sudo tail -f /var/log/nginx/watcher_error.log
```

### SSL сертификат не работает

```bash
# Проверить сертификат
sudo certbot certificates

# Обновить сертификат вручную
sudo certbot renew

# Проверить конфигурацию Nginx
sudo nginx -t
```

---

## 📝 Дополнительные настройки

### Firewall (UFW)

```bash
# Разрешить HTTP и HTTPS
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp

# Включить firewall
sudo ufw enable

# Проверить статус
sudo ufw status
```

### Автоматическое резервное копирование БД

Создайте скрипт `/usr/local/bin/backup_db.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/var/backups/cryptowatcher"
DATE=$(date +%Y%m%d_%H%M%S)
mkdir -p $BACKUP_DIR
pg_dump -U cryptouser cryptowatcher > $BACKUP_DIR/backup_$DATE.sql
# Удалить старые бэкапы (старше 7 дней)
find $BACKUP_DIR -name "backup_*.sql" -mtime +7 -delete
```

Добавьте в cron:
```bash
sudo crontab -e
# Добавить:
0 2 * * * /usr/local/bin/backup_db.sh
```

---

## ✅ Готово!

После выполнения всех шагов ваше приложение должно быть доступно по адресу:
**https://watcher.negarant.org**

Если возникнут проблемы - проверьте логи и убедитесь, что все сервисы запущены.

