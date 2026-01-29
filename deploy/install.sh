#!/bin/bash
#
# Скрипт установки мультиагентной системы на Ubuntu Server
#
# Использование:
#   chmod +x install.sh
#   sudo ./install.sh
#

set -e

echo "=========================================="
echo "Установка мультиагентной системы"
echo "Яндекс Директ + ML Analytics"
echo "=========================================="

# Проверка прав root
if [ "$EUID" -ne 0 ]; then
    echo "Запустите скрипт с правами root: sudo ./install.sh"
    exit 1
fi

# Переменные
APP_USER="directbot"
APP_DIR="/opt/yandex-direct-agent"
VENV_DIR="$APP_DIR/venv"
LOG_DIR="/var/log/yandex-direct-agent"
DATA_DIR="/var/lib/yandex-direct-agent/data"

echo ""
echo ">>> Обновление системы..."
apt-get update
apt-get upgrade -y

echo ""
echo ">>> Установка зависимостей..."
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3-pip \
    git \
    curl \
    wget \
    supervisor \
    nginx \
    certbot \
    python3-certbot-nginx

echo ""
echo ">>> Создание пользователя приложения..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -m -d /home/$APP_USER -s /bin/bash $APP_USER
    echo "Пользователь $APP_USER создан"
else
    echo "Пользователь $APP_USER уже существует"
fi

echo ""
echo ">>> Создание директорий..."
mkdir -p $APP_DIR
mkdir -p $LOG_DIR
mkdir -p $DATA_DIR
mkdir -p $DATA_DIR/exports
mkdir -p $DATA_DIR/reports

echo ""
echo ">>> Копирование файлов приложения..."
# Если запускаем из директории проекта
if [ -f "../orchestrator/main.py" ]; then
    cp -r ../* $APP_DIR/
else
    echo "Файлы проекта не найдены. Скопируйте их вручную в $APP_DIR"
fi

echo ""
echo ">>> Создание виртуального окружения Python..."
python3.11 -m venv $VENV_DIR

echo ""
echo ">>> Установка Python зависимостей..."
$VENV_DIR/bin/pip install --upgrade pip
$VENV_DIR/bin/pip install -r $APP_DIR/requirements.txt

echo ""
echo ">>> Настройка прав доступа..."
chown -R $APP_USER:$APP_USER $APP_DIR
chown -R $APP_USER:$APP_USER $LOG_DIR
chown -R $APP_USER:$APP_USER $DATA_DIR
chmod 750 $APP_DIR
chmod 750 $LOG_DIR
chmod 750 $DATA_DIR

echo ""
echo ">>> Создание файла окружения..."
if [ ! -f "$APP_DIR/.env" ]; then
    cat > $APP_DIR/.env << 'EOF'
# Яндекс Директ API
YANDEX_DIRECT_TOKEN=your_token_here
YANDEX_CLIENT_LOGIN=
YANDEX_API_MODE=production

# OpenRouter API (Claude)
OPENROUTER_API_KEY=your_openrouter_key_here
CLAUDE_MODEL=anthropic/claude-sonnet-4

# Настройки приложения
DATA_DIR=/var/lib/yandex-direct-agent/data
LOG_LEVEL=INFO
EOF
    chmod 600 $APP_DIR/.env
    chown $APP_USER:$APP_USER $APP_DIR/.env
    echo "Файл .env создан. Отредактируйте его: nano $APP_DIR/.env"
else
    echo "Файл .env уже существует"
fi

echo ""
echo ">>> Настройка Supervisor..."
cat > /etc/supervisor/conf.d/yandex-direct-agent.conf << EOF
[program:yandex-direct-agent]
command=$VENV_DIR/bin/python -m orchestrator.main
directory=$APP_DIR
user=$APP_USER
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
stdout_logfile=$LOG_DIR/agent.log
stderr_logfile=$LOG_DIR/agent_error.log
environment=HOME="/home/$APP_USER",USER="$APP_USER"

[program:yandex-direct-scheduler]
command=$VENV_DIR/bin/python -m deploy.scheduler
directory=$APP_DIR
user=$APP_USER
autostart=true
autorestart=true
stdout_logfile=$LOG_DIR/scheduler.log
stderr_logfile=$LOG_DIR/scheduler_error.log
environment=HOME="/home/$APP_USER",USER="$APP_USER"
EOF

echo ""
echo ">>> Настройка cron для ежедневного запуска..."
cat > /etc/cron.d/yandex-direct-agent << EOF
# Ежедневная выгрузка данных в 03:00
0 3 * * * $APP_USER cd $APP_DIR && $VENV_DIR/bin/python -m orchestrator.main >> $LOG_DIR/daily_run.log 2>&1

# Оптимизация ставок в 10:00 (без автоприменения)
0 10 * * 1-5 $APP_USER cd $APP_DIR && $VENV_DIR/bin/python -c "import asyncio; from orchestrator.main import Orchestrator; o = Orchestrator(); asyncio.run(o.run_bid_optimization())" >> $LOG_DIR/optimization.log 2>&1
EOF

chmod 644 /etc/cron.d/yandex-direct-agent

echo ""
echo ">>> Перезапуск сервисов..."
supervisorctl reread
supervisorctl update

echo ""
echo "=========================================="
echo "УСТАНОВКА ЗАВЕРШЕНА"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo "1. Отредактируйте файл конфигурации:"
echo "   nano $APP_DIR/.env"
echo ""
echo "2. Добавьте токены:"
echo "   - YANDEX_DIRECT_TOKEN"
echo "   - OPENROUTER_API_KEY"
echo ""
echo "3. Запустите сервис:"
echo "   supervisorctl start yandex-direct-agent"
echo ""
echo "4. Проверьте логи:"
echo "   tail -f $LOG_DIR/agent.log"
echo ""
echo "Полезные команды:"
echo "  supervisorctl status                    - статус сервисов"
echo "  supervisorctl restart yandex-direct-agent - перезапуск"
echo "  journalctl -u supervisor -f             - логи supervisor"
echo ""
