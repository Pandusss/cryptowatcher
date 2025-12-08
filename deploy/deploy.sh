#!/bin/bash
# Скрипт для автоматического деплоя обновлений на сервер
# Использование: ./deploy.sh

set -e  # Остановить выполнение при ошибке

PROJECT_DIR="/root/cryptowatcher"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BACKEND_DIR="$PROJECT_DIR/backend"

echo "🚀 Начинаем деплой CryptoWatcher..."

# Переходим в директорию проекта
cd "$PROJECT_DIR"

# Проверяем, что мы в Git репозитории
if [ ! -d ".git" ]; then
    echo "❌ Ошибка: директория не является Git репозиторием"
    echo "💡 Инициализируйте Git: git init"
    exit 1
fi

# Получаем последние изменения
echo "📥 Получаем обновления из Git..."
PREVIOUS_COMMIT=$(git rev-parse HEAD)
git pull origin main || git pull origin master || {
    echo "⚠️  Не удалось получить обновления. Проверьте подключение к репозиторию."
    exit 1
}
CURRENT_COMMIT=$(git rev-parse HEAD)

# Проверяем, были ли изменения
if [ "$PREVIOUS_COMMIT" = "$CURRENT_COMMIT" ]; then
    echo "ℹ️  Нет новых изменений. Выход."
    exit 0
fi

echo "✅ Получены новые изменения: $(git log -1 --oneline)"

# Проверяем изменения во фронтенде
FRONTEND_CHANGED=false
if git diff "$PREVIOUS_COMMIT" "$CURRENT_COMMIT" --name-only | grep -q "^frontend/"; then
    FRONTEND_CHANGED=true
fi

# Проверяем изменения в бэкенде
BACKEND_CHANGED=false
if git diff "$PREVIOUS_COMMIT" "$CURRENT_COMMIT" --name-only | grep -q "^backend/"; then
    BACKEND_CHANGED=true
fi

# Обновляем фронтенд
if [ "$FRONTEND_CHANGED" = true ]; then
    echo "🔨 Обновляем фронтенд..."
    cd "$FRONTEND_DIR"
    
    # Проверяем, изменился ли package.json
    if git diff "$PREVIOUS_COMMIT" "$CURRENT_COMMIT" --name-only | grep -q "package.json"; then
        echo "📦 Обновляем зависимости npm..."
        npm install
    fi
    
    echo "🏗️  Собираем фронтенд..."
    npm run build
    
    if [ $? -eq 0 ]; then
        echo "✅ Фронтенд успешно собран"
    else
        echo "❌ Ошибка при сборке фронтенда"
        exit 1
    fi
    
    cd "$PROJECT_DIR"
fi

# Обновляем бэкенд
if [ "$BACKEND_CHANGED" = true ]; then
    echo "🔄 Обновляем бэкенд..."
    
    # Проверяем, изменился ли requirements.txt
    if git diff "$PREVIOUS_COMMIT" "$CURRENT_COMMIT" --name-only | grep -q "requirements.txt"; then
        echo "📦 Обновляем зависимости Python..."
        source venv/bin/activate
        pip install -r backend/requirements.txt
        deactivate
    fi
    
    # Проверяем, нужны ли миграции БД
    if git diff "$PREVIOUS_COMMIT" "$CURRENT_COMMIT" --name-only | grep -qE "(models/|alembic/)"; then
        echo "🗄️  Обнаружены изменения в моделях. Возможно, нужны миграции."
        echo "💡 Выполните вручную: cd backend && alembic upgrade head"
    fi
    
    echo "🔄 Перезапускаем сервис бэкенда..."
    sudo systemctl restart cryptowatcher
    
    # Ждем немного и проверяем статус
    sleep 3
    
    if sudo systemctl is-active --quiet cryptowatcher; then
        echo "✅ Бэкенд успешно перезапущен"
    else
        echo "❌ Ошибка при перезапуске бэкенда"
        echo "📋 Логи:"
        sudo journalctl -u cryptowatcher -n 20 --no-pager
        exit 1
    fi
fi

# Финальная проверка
echo ""
echo "📊 Статус сервисов:"
sudo systemctl status cryptowatcher --no-pager -l | head -10

echo ""
echo "✅ Деплой завершен успешно!"
echo "🌐 Проверьте приложение: https://watcher.negarant.org"

