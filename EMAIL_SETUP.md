# Email Notifications Setup (SendGrid)

## 1. Create SendGrid Account

1. Go to https://sendgrid.com
2. Sign up for free account (100 emails/day free)
3. Verify your email

## 2. Get API Key

1. Go to Settings → API Keys
2. Click "Create API Key"
3. Name: `kwork-bot`
4. Permissions: `Mail Send` (Full Access)
5. Copy the API key (you won't see it again!)

## 3. Verify Sender Email

1. Go to Settings → Sender Authentication
2. Verify a Single Sender
3. Enter your email (e.g., `noreply@yourdomain.com`)
4. Confirm via email link

## 4. Configure Bot

Add to `/root/kwork-bot/.env`:

```bash
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxxx
SENDGRID_FROM_EMAIL=noreply@yourdomain.com
```

Restart bot:
```bash
docker restart kwork-bot
```

## 5. Test Email

```bash
docker exec kwork-bot python -c "
from email_sender import send_email
send_email('your@email.com', 'Test', '<h1>Test from Kwork Bot</h1>')
"
```

## Email Types

### Trial Ending (1 day before)
- Subject: "⏰ Триал заканчивается через 1 дн."
- Sent to users with trial ending soon
- Includes upgrade link

### Subscription Ending (3 days before)
- Subject: "⏰ Подписка заканчивается через 3 дн."
- Sent to Basic/Pro users
- Includes renewal link

### Payment Success
- Subject: "✅ Подписка активирована!"
- Sent after successful payment
- Includes subscription details

### Weekly Stats (Pro only)
- Subject: "📊 Ваша статистика за неделю"
- Projects received
- Active categories/filters

## Cron Schedule

Email notifications run daily at 10:00 MSK:

```cron
0 10 * * * docker exec kwork-bot python check_notifications.py
```

To run manually:
```bash
docker exec kwork-bot python check_notifications.py
```

## Email Logs

```bash
tail -f /var/log/kwork-email.log
```

## Rate Limits

SendGrid Free:
- 100 emails/day
- 1000 emails/month

If you need more:
- Essentials: $14.95/mo for 50k emails
- Pro: custom pricing

## Troubleshooting

### Emails not sending

1. Check API key is correct:
```bash
docker exec kwork-bot env | grep SENDGRID
```

2. Check sender email is verified in SendGrid

3. Check logs:
```bash
docker logs kwork-bot | grep -i email
```

### Users not getting emails

1. User must set email in Settings menu
2. Email must be valid format
3. Check spam folder

## Templates

All email templates are in `email_sender.py`:
- Modern responsive design
- Gradient headers
- Mobile-friendly
- Russian language

Customize templates by editing `email_sender.py`.
