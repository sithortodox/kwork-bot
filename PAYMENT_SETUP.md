# ЮKassa Payment Integration Setup

## 1. Get ЮKassa Credentials

1. Register at https://yookassa.ru
2. Complete business verification (ИНН, ОГРН, bank account)
3. Get credentials from dashboard:
   - `shop_id` (e.g., 123456)
   - `secret_key` (e.g., live_XXXXXXXXXX)

## 2. Configure Environment

Add to `/root/kwork-bot/.env`:

```bash
YOOKASSA_SHOP_ID=your_shop_id
YOOKASSA_SECRET_KEY=your_secret_key
WEBHOOK_PORT=8080
```

## 3. Configure Webhook URL

In ЮKassa dashboard:
1. Go to Настройки → HTTP-уведомления
2. Set webhook URL: `http://138.124.181.35:8080/webhook/yookassa`
3. Select events to receive:
   - payment.succeeded
   - payment.canceled

**Note:** For production, use HTTPS with nginx proxy.

## 4. Set up HTTPS (Recommended)

Create nginx config `/etc/nginx/sites-available/kwork-bot`:

```nginx
server {
    listen 80;
    server_name kwork-bot.ru;
    
    location /webhook/ {
        proxy_pass http://localhost:8080/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Then:
```bash
sudo ln -s /etc/nginx/sites-available/kwork-bot /etc/nginx/sites-enabled/
sudo certbot --nginx -d kwork-bot.ru
sudo nginx -t && sudo nginx -s reload
```

Update webhook URL in ЮKassa: `https://kwork-bot.ru/webhook/yookassa`

## 5. Test Payment Flow

1. Send `/start` to bot
2. Click "💎 Подписка"
3. Select plan (Basic/Pro)
4. Choose period (monthly/yearly)
5. Click payment link
6. Complete payment on ЮKassa page
7. Subscription auto-activates via webhook

## Payment Flow

```
User → Bot → ЮKassa API → Payment Page
                          ↓
User pays → ЮKassa → Webhook → Bot → Activate subscription
```

## Testing Without Real Payments

Use ЮKassa test credentials:
- `shop_id`: test-shop
- `secret_key`: test-key

Test cards available in ЮKassa docs.

## Troubleshooting

Check webhook server logs:
```bash
docker logs kwork-bot | grep -i webhook
```

Check payment logs:
```bash
docker logs kwork-bot | grep -i payment
```

Test webhook endpoint:
```bash
curl http://138.124.181.35:8080/health
```
