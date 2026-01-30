#!/bin/bash
#
# Скрипт установки мультиагентной системы на Ubuntu Server
# С поддержкой REST API и генерации PDF отчётов
#
# Использование:
#   chmod +x install.sh
#   sudo ./install.sh
#

set -e

echo "=========================================="
echo "Установка мультиагентной системы"
echo "Яндекс Директ + ML Analytics + API"
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
API_PORT=8000

echo ""
echo ">>> Обновление системы..."
apt-get update
apt-get upgrade -y

echo ""
echo ">>> Установка системных зависимостей..."
apt-get install -y \
    python3.11 \
    python3.11-venv \
    python3.11-dev \
    python3-pip \
    git \
    curl \
    wget \
    supervisor \
    nginx \
    certbot \
    python3-certbot-nginx

echo ""
echo ">>> Установка LaTeX для генерации PDF..."
apt-get install -y \
    texlive-latex-base \
    texlive-latex-extra \
    texlive-fonts-recommended \
    texlive-fonts-extra \
    texlive-lang-cyrillic \
    texlive-xetex \
    latexmk

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
mkdir -p $DATA_DIR/charts

echo ""
echo ">>> Копирование файлов приложения..."
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
if [ -f "$SCRIPT_DIR/../orchestrator/main.py" ]; then
    cp -r $SCRIPT_DIR/../* $APP_DIR/
    echo "Файлы скопированы из $SCRIPT_DIR/.."
else
    echo "ВНИМАНИЕ: Файлы проекта не найдены."
    echo "Скопируйте их вручную в $APP_DIR"
fi

echo ""
echo ">>> Создание виртуального окружения Python..."
python3.11 -m venv $VENV_DIR

echo ""
echo ">>> Установка Python зависимостей..."
$VENV_DIR/bin/pip install --upgrade pip wheel setuptools
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
# ==========================================
# КОНФИГУРАЦИЯ МУЛЬТИАГЕНТНОЙ СИСТЕМЫ
# ==========================================

# --- Яндекс Директ API ---
YANDEX_DIRECT_TOKEN=your_token_here
YANDEX_CLIENT_LOGIN=
YANDEX_API_MODE=production

# --- OpenRouter API (Claude Sonnet 4.5) ---
OPENROUTER_API_KEY=your_openrouter_key_here
CLAUDE_MODEL=anthropic/claude-sonnet-4

# --- API Server ---
API_HOST=0.0.0.0
API_PORT=8000

# --- Настройки приложения ---
DATA_DIR=/var/lib/yandex-direct-agent/data
LOG_LEVEL=INFO
EOF
    chmod 600 $APP_DIR/.env
    chown $APP_USER:$APP_USER $APP_DIR/.env
    echo "Файл .env создан"
else
    echo "Файл .env уже существует"
fi

echo ""
echo ">>> Настройка Supervisor..."
cat > /etc/supervisor/conf.d/yandex-direct-agent.conf << EOF
[program:yandex-direct-api]
command=$VENV_DIR/bin/uvicorn api.main:app --host 0.0.0.0 --port $API_PORT
directory=$APP_DIR
user=$APP_USER
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=30
stdout_logfile=$LOG_DIR/api.log
stderr_logfile=$LOG_DIR/api_error.log
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

[group:yandex-direct]
programs=yandex-direct-api,yandex-direct-scheduler
EOF

echo ""
echo ">>> Настройка Nginx..."
cat > /etc/nginx/sites-available/yandex-direct-api << EOF
server {
    listen 80;
    server_name _;

    # API endpoints
    location /api {
        proxy_pass http://127.0.0.1:$API_PORT;
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 300;
        proxy_connect_timeout 300;
        proxy_send_timeout 300;

        # CORS headers
        add_header 'Access-Control-Allow-Origin' '*' always;
        add_header 'Access-Control-Allow-Methods' 'GET, POST, PUT, DELETE, OPTIONS' always;
        add_header 'Access-Control-Allow-Headers' 'Origin, Content-Type, Accept, Authorization' always;

        if (\$request_method = 'OPTIONS') {
            return 204;
        }
    }

    # Swagger docs
    location /docs {
        proxy_pass http://127.0.0.1:$API_PORT/docs;
        proxy_set_header Host \$host;
    }

    location /redoc {
        proxy_pass http://127.0.0.1:$API_PORT/redoc;
        proxy_set_header Host \$host;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:$API_PORT/openapi.json;
        proxy_set_header Host \$host;
    }

    # Health check
    location /health {
        proxy_pass http://127.0.0.1:$API_PORT/api/status;
        proxy_set_header Host \$host;
    }

    # Увеличиваем лимит размера загружаемых файлов
    client_max_body_size 100M;
}
EOF

ln -sf /etc/nginx/sites-available/yandex-direct-api /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Проверка конфигурации nginx
nginx -t

echo ""
echo ">>> Настройка cron..."
cat > /etc/cron.d/yandex-direct-agent << EOF
# Ежедневная выгрузка данных в 03:00
0 3 * * * $APP_USER cd $APP_DIR && $VENV_DIR/bin/python -m orchestrator.main >> $LOG_DIR/daily_run.log 2>&1

# Генерация отчётов в 08:00
0 8 * * 1-5 $APP_USER cd $APP_DIR && $VENV_DIR/bin/python -c "
import asyncio
from orchestrator.main import Orchestrator
async def run():
    o = Orchestrator()
    await o.start()
    await o.run_daily_pipeline()
    await o.stop()
asyncio.run(run())
" >> $LOG_DIR/report.log 2>&1

# Очистка старых файлов раз в неделю
0 4 * * 0 $APP_USER find $DATA_DIR -name "*.json" -mtime +30 -delete
0 4 * * 0 $APP_USER find $DATA_DIR -name "*.csv" -mtime +30 -delete
EOF

chmod 644 /etc/cron.d/yandex-direct-agent

echo ""
echo ">>> Перезапуск сервисов..."
supervisorctl reread
supervisorctl update
systemctl restart nginx

echo ""
echo "=========================================="
echo "УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО!"
echo "=========================================="
echo ""
echo "Следующие шаги:"
echo ""
echo "1. Отредактируйте файл конфигурации:"
echo "   sudo nano $APP_DIR/.env"
echo ""
echo "2. Добавьте API ключи:"
echo "   - YANDEX_DIRECT_TOKEN (https://oauth.yandex.ru/)"
echo "   - OPENROUTER_API_KEY (https://openrouter.ai/keys)"
echo ""
echo "3. Запустите сервисы:"
echo "   sudo supervisorctl start yandex-direct:*"
echo ""
echo "4. Проверьте работу API:"
echo "   curl http://localhost/api/status"
echo ""
echo "5. Откройте документацию API:"
echo "   http://YOUR_SERVER_IP/docs"
echo ""
echo "=========================================="
echo "Полезные команды:"
echo "=========================================="
echo "  supervisorctl status                  - статус сервисов"
echo "  supervisorctl restart yandex-direct:* - перезапуск всех"
echo "  tail -f $LOG_DIR/api.log        - логи API"
echo "  tail -f $LOG_DIR/scheduler.log  - логи планировщика"
echo ""
echo "Для HTTPS выполните:"
echo "  sudo certbot --nginx -d your-domain.com"
echo ""
