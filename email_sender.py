import os
import logging
from datetime import datetime, timedelta
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content

from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "noreply@kwork-bot.ru")

EMAIL_ENABLED = bool(SENDGRID_API_KEY)


def send_email(to_email: str, subject: str, html_content: str) -> bool:
    if not EMAIL_ENABLED:
        log.warning("SendGrid not configured, email not sent to %s", to_email)
        return False
    
    try:
        message = Mail(
            from_email=Email(SENDGRID_FROM_EMAIL, "Kwork Bot"),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            log.info("Email sent to %s: %s", to_email, subject)
            return True
        else:
            log.error("SendGrid error: %s %s", response.status_code, response.body)
            return False
            
    except Exception as e:
        log.error("Failed to send email to %s: %s", to_email, e)
        return False


def send_trial_ending_email(user_email: str, days_left: int, chat_id: int):
    subject = f"⏰ Триал заканчивается через {days_left} дн. | Kwork Bot"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">🤖 Kwork Bot</h1>
        </div>
        
        <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #333;">⏰ Триал заканчивается!</h2>
            
            <p style="font-size: 16px; color: #666;">
                Ваш пробный период тарифа <b>⭐ Pro</b> закончится через <b>{days_left} дней</b>.
            </p>
            
            <div style="background: white; padding: 20px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #667eea;">
                <h3 style="margin-top: 0; color: #333;">⭐ Pro тариф включает:</h3>
                <ul style="color: #666; line-height: 1.8;">
                    <li>✅ Безлимит уведомлений</li>
                    <li>✅ Все категории и фильтры</li>
                    <li>✅ Приоритетная доставка</li>
                    <li>✅ История проектов за 30 дней</li>
                </ul>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="https://t.me/kwork_projects_bot?start=subscription" 
                   style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; 
                          padding: 15px 40px; 
                          text-decoration: none; 
                          border-radius: 25px; 
                          font-size: 18px; 
                          font-weight: bold;
                          display: inline-block;">
                    💎 Оформить подписку
                </a>
            </div>
            
            <p style="color: #999; font-size: 14px; text-align: center;">
                После окончания триала вы перейдете на Free тариф с ограничениями.
            </p>
        </div>
        
        <div style="background: #333; color: #999; padding: 20px; text-align: center; font-size: 12px;">
            <p>🤖 Kwork Bot — мониторинг проектов на kwork.ru</p>
            <p>Telegram: @kwork_projects_bot</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user_email, subject, html)


def send_subscription_ending_email(user_email: str, days_left: int, plan_name: str, chat_id: int):
    subject = f"⏰ Подписка {plan_name} заканчивается через {days_left} дн."
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">🤖 Kwork Bot</h1>
        </div>
        
        <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #333;">⚠️ Подписка заканчивается!</h2>
            
            <p style="font-size: 16px; color: #666;">
                Ваша подписка <b>{plan_name}</b> закончится через <b>{days_left} дней</b>.
            </p>
            
            <div style="background: #fff3cd; padding: 15px; border-radius: 10px; margin: 20px 0; border-left: 4px solid #ffc107;">
                <p style="margin: 0; color: #856404;">
                    ⚠️ После окончания подписки вы потеряете доступ к премиум-функциям.
                </p>
            </div>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="https://t.me/kwork_projects_bot?start=subscription" 
                   style="background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); 
                          color: white; 
                          padding: 15px 40px; 
                          text-decoration: none; 
                          border-radius: 25px; 
                          font-size: 18px; 
                          font-weight: bold;
                          display: inline-block;">
                    🔄 Продлить подписку
                </a>
            </div>
        </div>
        
        <div style="background: #333; color: #999; padding: 20px; text-align: center; font-size: 12px;">
            <p>🤖 Kwork Bot — мониторинг проектов на kwork.ru</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user_email, subject, html)


def send_payment_success_email(user_email: str, plan_name: str, amount: str, period: str):
    subject = f"✅ Подписка {plan_name} активирована!"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">✅ Оплата прошла успешно!</h1>
        </div>
        
        <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #333;">🎉 Спасибо за подписку!</h2>
            
            <div style="background: white; padding: 20px; border-radius: 10px; margin: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <table style="width: 100%; color: #666;">
                    <tr>
                        <td style="padding: 10px 0;">📦 Тариф:</td>
                        <td style="padding: 10px 0; text-align: right; font-weight: bold;">{plan_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0;">💰 Сумма:</td>
                        <td style="padding: 10px 0; text-align: right; font-weight: bold;">{amount}₽</td>
                    </tr>
                    <tr>
                        <td style="padding: 10px 0;">📅 Период:</td>
                        <td style="padding: 10px 0; text-align: right; font-weight: bold;">{period}</td>
                    </tr>
                </table>
            </div>
            
            <p style="color: #666; text-align: center;">
                Теперь вам доступны все преимущества {plan_name} тарифа!
            </p>
        </div>
        
        <div style="background: #333; color: #999; padding: 20px; text-align: center; font-size: 12px;">
            <p>🤖 Kwork Bot — мониторинг проектов на kwork.ru</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user_email, subject, html)


def send_weekly_stats_email(user_email: str, stats: dict):
    subject = "📊 Ваша статистика за неделю | Kwork Bot"
    
    html = f"""
    <html>
    <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0;">📊 Еженедельная статистика</h1>
        </div>
        
        <div style="padding: 30px; background: #f9f9f9;">
            <h2 style="color: #333;">Ваши результаты за неделю:</h2>
            
            <div style="background: white; padding: 20px; border-radius: 10px; margin: 20px 0; box-shadow: 0 2px 10px rgba(0,0,0,0.1);">
                <table style="width: 100%; color: #666;">
                    <tr>
                        <td style="padding: 15px 0; border-bottom: 1px solid #eee;">📬 Получено проектов:</td>
                        <td style="padding: 15px 0; text-align: right; font-weight: bold; border-bottom: 1px solid #eee;">{stats.get('projects_received', 0)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 15px 0; border-bottom: 1px solid #eee;">📂 Активных категорий:</td>
                        <td style="padding: 15px 0; text-align: right; font-weight: bold; border-bottom: 1px solid #eee;">{stats.get('categories', 0)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 15px 0; border-bottom: 1px solid #eee;">⚙️ Фильтров:</td>
                        <td style="padding: 15px 0; text-align: right; font-weight: bold; border-bottom: 1px solid #eee;">{stats.get('filters', 0)}</td>
                    </tr>
                    <tr>
                        <td style="padding: 15px 0;">⭐ Ваш тариф:</td>
                        <td style="padding: 15px 0; text-align: right; font-weight: bold;">{stats.get('plan', 'Free')}</td>
                    </tr>
                </table>
            </div>
        </div>
        
        <div style="background: #333; color: #999; padding: 20px; text-align: center; font-size: 12px;">
            <p>🤖 Kwork Bot — мониторинг проектов на kwork.ru</p>
        </div>
    </body>
    </html>
    """
    
    return send_email(user_email, subject, html)


def check_and_send_notifications():
    from telegram_bot import load_users, load_subscriptions, get_user_plan
    
    if not EMAIL_ENABLED:
        return
    
    users = load_users()
    subs = load_subscriptions()
    now = time.time()
    
    for uid, user_data in users.items():
        chat_id = int(uid)
        user_sub = subs.get(uid, {})
        
        user_email = user_data.get("email")
        if not user_email:
            continue
        
        # Trial ending (1 day before)
        if user_sub.get("trial_ends_at"):
            trial_ends = user_sub["trial_ends_at"]
            days_left = (trial_ends - now) / (24 * 60 * 60)
            
            if 0 < days_left <= 1 and not user_sub.get("trial_notified"):
                send_trial_ending_email(user_email, int(days_left), chat_id)
                user_sub["trial_notified"] = True
                save_subscriptions(subs)
        
        # Subscription ending (3 days before)
        if user_sub.get("expires_at"):
            expires = user_sub["expires_at"]
            days_left = (expires - now) / (24 * 60 * 60)
            
            if 0 < days_left <= 3 and not user_sub.get("expires_notified"):
                plan = get_user_plan(chat_id)
                send_subscription_ending_email(user_email, int(days_left), f"{plan['emoji']} {plan['name']}", chat_id)
                user_sub["expires_notified"] = True
                save_subscriptions(subs)


import time
from telegram_bot import save_subscriptions
