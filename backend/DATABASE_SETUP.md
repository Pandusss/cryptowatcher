# Настройка базы данных

## Шаги для настройки PostgreSQL и миграций

### 1. Установите PostgreSQL (если еще не установлен)

**Windows:**
- Скачайте с https://www.postgresql.org/download/windows/
- Или используйте установщик через Chocolatey: `choco install postgresql`

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install postgresql postgresql-contrib
```

**Mac:**
```bash
brew install postgresql
```

### 2. Создайте базу данных

Откройте терминал и выполните:

```bash
# Подключитесь к PostgreSQL
psql -U postgres

# В консоли PostgreSQL создайте базу данных
CREATE DATABASE cryptowatcher;

# Создайте пользователя (опционально, можно использовать существующего)
CREATE USER cryptowatcher_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE cryptowatcher TO cryptowatcher_user;

# Выйдите из консоли
\q
```

### 3. Настройте `.env` файл

В папке `backend/` создайте файл `.env` на основе `env.example.txt`:

```bash
# Windows
copy env.example.txt .env

# Linux/Mac
cp env.example.txt .env
```

Отредактируйте `.env` и укажите правильный `DATABASE_URL`:

```env
DATABASE_URL=postgresql://cryptowatcher_user:your_password@localhost:5432/cryptowatcher
```

Или если используете стандартного пользователя `postgres`:

```env
DATABASE_URL=postgresql://postgres:your_postgres_password@localhost:5432/cryptowatcher
```

**Важно:** 
- Замените `your_password` на ваш реальный пароль PostgreSQL
- Если PostgreSQL работает на другом порту, измените `5432` на нужный порт

### 4. Установите зависимости (если еще не установлены)

```bash
cd backend
pip install -r requirements.txt
```

### 5. Создайте миграции

```bash
cd backend

# Создайте первую миграцию
alembic revision --autogenerate -m "Initial migration"

# Примените миграции
alembic upgrade head
```

### 6. Проверьте, что все работает

Запустите backend:

```bash
python run.py
```

Откройте http://localhost:8000/docs - должна открыться документация API.

### 7. Проверка базы данных

Вы можете проверить, что таблицы созданы:

```bash
psql -U postgres -d cryptowatcher

# В консоли PostgreSQL
\dt  # Покажет список таблиц

# Должны быть таблицы:
# - users
# - notifications

\q  # Выйти
```

## Устранение проблем

### Ошибка "could not connect to server"

- Убедитесь, что PostgreSQL запущен:
  - Windows: Проверьте службу PostgreSQL в "Службы"
  - Linux: `sudo systemctl status postgresql`
  - Mac: `brew services list`

### Ошибка "password authentication failed"

- Проверьте правильность пароля в `.env`
- Убедитесь, что пользователь существует и имеет права на базу данных

### Ошибка "database does not exist"

- Создайте базу данных (шаг 2)

### Ошибка при миграциях

- Убедитесь, что `DATABASE_URL` в `.env` правильный
- Проверьте, что все модели импортированы в `backend/app/models/__init__.py`
- Убедитесь, что `alembic/env.py` правильно настроен

