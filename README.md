# Kwork Notification Bot

Многопользовательский Telegram-бот для мониторинга проектов на kwork.ru с автоматическими уведомлениями, системой подписок и интеграцией с ЮKassa.

## Возможности

### Для пользователей
- **Мониторинг проектов**: Автоматический парсинг новых проектов по выбранным категориям
- **Иерархический выбор категорий**: Категория → Подкатегория → Фильтры
- **Гибкие фильтры**: Поиск по ключевым словам, диапазон бюджета, тип проекта
- **Уведомления**: Мгновенные уведомления о новых проектах в Telegram
- **История проектов**: Хранение просмотренных проектов (7-30 дней в зависимости от тарифа)
- **Реферальная система**: +7 дней подписки за каждого приглашенного пользователя
- **Промо-коды**: Скидки на подписку до 30%

### Для администраторов
- **Панель управления**: Статистика, список пользователей, рассылка
- **Управление подписками**: Ручное продление/выдача подписок
- **Промо-коды**: Создание, редактирование, удаление промо-кодов
- **Аналитика**: DAU/WAU/MAU, MRR, ARR, конверсия, отток, ARPU, LTV
- **Broadcast**: Массовые рассылки пользователям

### Технические особенности
- **API вместо браузера**: Использует kwork API вместо Playwright (размер образа 227MB вместо 1.9GB)
- **Микросервисная архитектура**: Docker контейнеры для бота и вебхук-сервера
- **Cloudflare Tunnel**: HTTPS без публичного IP, работает за NAT
- **ЮKassa интеграция**: Автоматическая обработка платежей и активация подписок

## Тарифы

| Тариф | Цена | Проекты/день | Категории | История | Особенности |
|-------|------|--------------|-----------|---------|-------------|
| **Free** | Бесплатно | 5 | 3 | Нет | Базовый доступ |
| **Basic** | 299 ₽/мес | 30 | 10 | 7 дней | Стандартный доступ |
| **Pro** | 799 ₽/мес | ∞ | ∞ | 30 дней | Полный доступ + приоритет |

### Тестовый период
- **7 дней Pro бесплатно** для новых пользователей
- Автоматический переход на Free после окончания теста

### Скидки
- **Годовая подписка**: Скидка 20%
- **Промо-коды**: WELCOME20 (20%), YEAR30 (30%), PRO500 (-500₽)

## Установка

### Требования
- Python 3.10+
- Docker и Docker Compose
- Telegram Bot Token (от [@BotFather](https://t.me/botfather))
- ЮKassa shop_id и secret_key
- (Опционально) SendGrid API key для email-уведомлений

### Локальная разработка

```bash
# Клонирование репозитория
git clone git@github.com:sithortodox/kwork-bot.git
cd kwork-bot

# Создание виртуального окружения
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или venv\Scripts\activate  # Windows

# Установка зависимостей
pip install -r requirements.txt

# Настройка переменных окружения
cp .env.example .env
# Отредактируйте .env файл

# Запуск
python main.py
```

### Docker развертывание

```bash
# Сборка образа
docker build -t kwork-bot .

# Запуск контейнера
docker run -d \
  --name kwork-bot \
  --env-file .env \
  -v $(pwd)/data:/app/data \
  -p 8080:8080 \
  kwork-bot
```

### Docker Compose

```yaml
version: '3.8'

services:
  kwork-bot:
    build: .
    container_name: kwork-bot
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./data:/app/data
    ports:
      - "8080:8080"
```

```bash
docker-compose up -d
```

## Конфигурация

### Переменные окружения (.env)

```bash
# Telegram
BOT_TOKEN=your_bot_token_here
ADMIN_CHAT_ID=your_chat_id_here

# ЮKassa
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key

# SendGrid (опционально)
SENDGRID_API_KEY=your_sendgrid_key
SENDGRID_FROM_EMAIL=noreply@yourdomain.com

# Webhook
WEBHOOK_URL=https://kwork-notification.ru
WEBHOOK_PORT=8080

# Cloudflare Tunnel (опционально)
CLOUDFLARE_TUNNEL_ID=your_tunnel_id
```

### Структура данных

```
data/
├── subscriptions.json    # Подписки пользователей
├── users.json            # Пользователи и их настройки
├── user_history.json     # История проектов
├── metrics.json          # Метрики аналитики
└── promos.json           # Промо-коды
```

## Использование

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Регистрация и приветственное сообщение |
| `/help` | Справка по использованию бота |
| `/faq` | Часто задаваемые вопросы |
| `/menu` | Главное меню |
| `/settings` | Настройки уведомлений |
| `/subscription` | Управление подпиской |
| `/categories` | Выбор категорий для мониторинга |
| `/filters` | Настройка фильтров проектов |
| `/history` | История просмотренных проектов |
| `/referral` | Реферальная ссылка и статистика |
| `/stats` | Личная статистика |
| `/export_data` | Экспорт персональных данных (GDPR) |
| `/delete_account` | Удаление аккаунта и данных (GDPR) |
| `/admin` | Панель администратора (только для админа) |

### Главное меню

```
┌─────────────────────────┐
│     Kwork Bot Menu      │
├─────────────────────────┤
│ 🔍 Категории            │
│ ⚙️ Фильтры              │
│ 💎 Подписка             │
│ 📊 Статистика           │
│ 📜 История              │
│ 👥 Рефералы             │
│ ❓ Помощь               │
└─────────────────────────┘
```

### Выбор категорий

```
1. Выберите категорию: "Тексты и переводы"
2. Выберите подкатегорию: "Тексты"
3. Настройте фильтры:
   - Ключевые слова: "статья, текст"
   - Мин. бюджет: 500₽
   - Тип: "Любой"
```

### Настройка времени уведомлений

Каждый пользователь может настроить удобное время для получения уведомлений:

```
⚙️ Настройки → ⏰ Время уведомлений

⏰ Время уведомлений
━━━━━━━━━━━━━━━━━━

🟢 Статус: ✅ Включено

📅 Активные часы:
🕐 Начало: 09:00
🕐 Конец: 21:00

🌍 Часовой пояс: Moscow

📊 Уведомления будут приходить только в указанное время.
```

**Возможности:**
- Включение/выключение ограничений по времени
- Настройка часов начала и окончания (0-23)
- Выбор часового пояса (11 зон России)
- Гибкая настройка для каждого пользователя

**Часовые пояса:**
- Europe/Moscow (МСК)
- Europe/Kaliningrad (Калининград)
- Europe/Samara (Самара)
- Asia/Yekaterinburg (Екатеринбург)
- Asia/Omsk (Омск)
- Asia/Krasnoyarsk (Красноярск)
- Asia/Irkutsk (Иркутск)
- Asia/Yakutsk (Якутск)
- Asia/Vladivostok (Владивосток)
- Asia/Magadan (Магадан)
- Asia/Kamchatka (Камчатка)

## API и Webhooks

### ЮKassa Webhook

**URL**: `https://kwork-notification.ru/webhook/yookassa`

**События**:
- `payment.succeeded` - Успешная оплата
- `payment.waiting_for_capture` - Ожидание подтверждения
- `payment.canceled` - Отмена платежа

**Payload пример**:
```json
{
  "event": "payment.succeeded",
  "object": {
    "id": "payment_id",
    "status": "succeeded",
    "amount": {
      "value": "799.00",
      "currency": "RUB"
    },
    "metadata": {
      "chat_id": "123456789",
      "plan_type": "pro_monthly"
    }
  }
}
```

### Health Check

```bash
curl https://kwork-notification.ru/health
# {"status":"ok"}
```

## GDPR Compliance

### Права пользователей

**Экспорт данных (ст. 20 GDPR):**
```bash
/export_data
```
Пользователь получает JSON-файл со всеми своими данными:
- Профиль и настройки
- Подписки
- История проектов
- Избранное

**Удаление данных (ст. 17 GDPR):**
```bash
/delete_account
```
Безвозвратное удаление всех персональных данных.

### Юридические документы

- **[Политика конфиденциальности](PRIVACY_POLICY.md)** - сбор, хранение и обработка данных
- **[Пользовательское соглашение](TERMS_OF_SERVICE.md)** - условия использования сервиса

### Соответствие требованиям

- ✅ GDPR (EU 2016/679)
- ✅ 152-ФЗ "О персональных данных" (РФ)
- ✅ 54-ФЗ "О применении контрольно-кассовой техники" (РФ)

## Админ-панель

### Доступные функции

```
┌─────────────────────────────┐
│       Admin Panel           │
├─────────────────────────────┤
│ 📊 Статистика               │
│ 👥 Пользователи             │
│ 📧 Рассылка                 │
│ 💎 Управление подписками    │
│ 🎫 Промо-коды               │
│ 📈 Аналитика                │
│ ⚙️ Настройки                │
└─────────────────────────────┘
```

### Аналитика

- **DAU/WAU/MAU** - Ежедневные/еженедельные/ежемесячные активные пользователи
- **MRR/ARR** - Месячная/годовая регулярная выручка
- **Conversion Rate** - Конверсия из триала в платного пользователя
- **Churn Rate** - Отток пользователей
- **ARPU** - Средний доход на пользователя
- **LTV** - Пожизненная ценность клиента
- **Growth Rate** - Темпы роста

## Реферальная система

### Как работает

1. Пользователь получает реферальную ссылку: `/referral`
2. Делится ссылкой с друзьями
3. Когда друг регистрируется по ссылке:
   - **Реферер**: +7 дней к текущей подписке
   - **Реферал**: +7 дней к тестовому периоду

### Ограничения

- Неограниченное количество приглашений
- Бонусы суммируются
- Работает только для новых пользователей

## Промо-коды

### Предустановленные промо-коды

| Код | Скидка | Условия |
|-----|--------|---------|
| `WELCOME20` | 20% | Для новых подписчиков |
| `YEAR30` | 30% | Только для годовых подписок |
| `PRO500` | -500₽ | Для Pro тарифа |
| `BASIC199` | -100₽ | Для Basic тарифа |

### Создание промо-кода (Admin)

```
/admin → Промо-коды → Создать промо-код

Введите данные:
- Код: SAVE25
- Скидка: 25%
- Тип: percentage
- Макс. использований: 100
- Срок действия: 30 дней
```

## Безопасность

### Рекомендации

1. **Никогда не коммитьте .env файл** в репозиторий
2. **Используйте HTTPS** для вебхуков (Cloudflare Tunnel)
3. **Валидируйте входящие данные** от ЮKassa
4. **Логируйте все платежи** для аудита
5. **Регулярно обновляйте зависимости**

### Переменные окружения

```bash
# Добавьте в .gitignore
.env
*.pem
secret_key.txt
```

## Мониторинг и логи

### Просмотр логов

```bash
# Docker logs
docker logs -f kwork-bot --tail 100

# Только ошибки
docker logs kwork-bot 2>&1 | grep ERROR

# Только платежи
docker logs kwork-bot 2>&1 | grep -E "payment|ЮKassa"
```

### Метрики

Файл `data/metrics.json` отслеживает:
- Регистрации
- Платежи
- Выручка
- Уведомления
- Рефералы
- Промо-коды

## Развертывание на сервере

### Требования к серверу

- **ОС**: Ubuntu 20.04+ или аналогичный Linux
- **RAM**: Минимум 512MB
- **Диск**: Минимум 5GB
- **Docker**: Установленный Docker и Docker Compose

### Автоматическое развертывание

```bash
# SSH доступ
ssh root@138.124.181.35

# Клонирование
git clone git@github.com:sithortodox/kwork-bot.git
cd kwork-bot

# Настройка
cp .env.example .env
nano .env

# Запуск
docker-compose up -d

# Проверка
docker ps
docker logs -f kwork-bot
```

### Cloudflare Tunnel

```bash
# Установка cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
mv cloudflared /usr/local/bin/

# Авторизация
cloudflared tunnel login

# Создание туннеля
cloudflared tunnel create kwork-bot

# Конфигурация
cat > ~/.cloudflared/config.yml <<EOF
tunnel: a6496944-01e7-4c8e-981e-c545270376af
credentials-file: /root/.cloudflared/a6496944-01e7-4c8e-981e-c545270376af.json

ingress:
  - hostname: kwork-notification.ru
    service: http://localhost:8080
  - service: http_status:404
EOF

# Запуск
cloudflared tunnel run kwork-bot
```

## Разработка

### Структура проекта

```
kwork-bot/
├── main.py              # Основной цикл, парсинг, уведомления
├── telegram_bot.py      # Bot UI, обработчики команд
├── payment.py           # ЮKassa API интеграция
├── webhook.py           # Flask webhook сервер
├── email_sender.py      # SendGrid интеграция
├── promos.py            # Промо-коды CRUD
├── analytics.py         # Бизнес-метрики
├── faq.py               # FAQ контент
├── config.py            # Конфигурация
├── requirements.txt     # Python зависимости
├── Dockerfile           # Docker образ
├── docker-compose.yml   # Docker Compose
├── .env.example         # Пример конфигурации
└── README.md            # Этот файл
```

### Добавление новой категории

1. Отредактируйте `config.py`:

```python
CATEGORIES = {
    "Новая категория": {
        "subcategories": {
            "Подкатегория 1": "subcategory_id_1",
            "Подкатегория 2": "subcategory_id_2",
        }
    }
}
```

2. Перезапустите бота

### Тестирование

```bash
# Юнит тесты
python -m pytest tests/

# Тест webhook
curl -X POST https://kwork-notification.ru/webhook/yookassa \
  -H "Content-Type: application/json" \
  -d '{"event":"payment.succeeded","object":{"id":"test123","status":"succeeded","metadata":{"chat_id":"YOUR_CHAT_ID","plan_type":"pro_monthly"}}}'
```

### Тестовые карты ЮKassa

```
Успешная оплата:        5555 5555 5555 4444
Недостаточно средств:   5555 5555 5555 0002
Ошибка банка:           5555 5555 5555 0003
```

## Troubleshooting

### Частые проблемы

**1. Бот не отвечает**
```bash
# Проверьте токен
echo $BOT_TOKEN

# Проверьте логи
docker logs kwork-bot --tail 50
```

**2. Webhook не работает**
```bash
# Проверьте DNS
dig NS kwork-notification.ru

# Проверьте туннель
cloudflared tunnel info kwork-bot

# Проверьте порт
netstat -tlnp | grep 8080
```

**3. Платежи не зачисляются**
```bash
# Проверьте webhook логи
docker logs kwork-bot 2>&1 | grep webhook

# Проверьте YOOKASSA_SECRET_KEY
```

**4. Уведомления не приходят**
```bash
# Проверьте категории пользователя
cat data/users.json | jq '.[chat_id].categories'

# Проверьте лимиты подписки
cat data/subscriptions.json | jq '.[chat_id]'
```

## Лицензия

MIT License

Copyright (c) 2026 Kwork Notification Bot

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Контакты

- **GitHub**: [sithortodox/kwork-bot](https://github.com/sithortodox/kwork-bot)
- **Issues**: [Баг-репорты и предложения](https://github.com/sithortodox/kwork-bot/issues)

## Благодарности

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API
- [ЮKassa API](https://yookassa.ru/developers) - Платежная система
- [Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) - Безопасный туннель
- [SendGrid](https://sendgrid.com/) - Email сервис
