import os
import logging
from datetime import datetime

import config

logger = logging.getLogger(__name__)

TEMPLATES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "email_templates")


def _load_template(filename: str) -> str:
    path = os.path.join(TEMPLATES_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def get_base_html(title, content):
    """Базовый HTML-шаблон с премиальным темным дизайном, градиентом и адаптивной версткой."""
    try:
        html = _load_template("base.html")
    except Exception as e:
        logger.error(f"Ошибка загрузки base.html: {e}")
        return f"<html><head><title>{title}</title></head><body><h1>{title}</h1>{content}</body></html>"

    return (html
            .replace("{{title}}", title)
            .replace("{{content}}", content)
            .replace("{{service_name}}", config.SERVICE_NAME))


def get_welcome_email(sub_url, expire_days, limit_gb):
    """Письмо приветствия после успешной регистрации."""
    expire_str = "Бессрочно" if expire_days == 0 else f"{expire_days} дней"
    limit_str = "Безлимит" if limit_gb == 0 else f"{limit_gb} ГБ"

    title = f"Ваша подписка {config.SERVICE_NAME} активирована!"

    happ_url = f"{config.HAPP_URL}/{sub_url}"
    incy_url = f"{config.INCY_URL}/{sub_url}"

    try:
        html = _load_template("welcome.html")
        content = (html
                   .replace("{{service_name}}", config.SERVICE_NAME)
                   .replace("{{expire_days}}", expire_str)
                   .replace("{{limit_gb}}", limit_str)
                   .replace("{{sub_url}}", sub_url)
                   .replace("{{happ_url}}", happ_url)
                   .replace("{{incy_url}}", incy_url))
    except Exception as e:
        logger.error(f"Ошибка загрузки welcome.html: {e}")
        content = f"<p>Ваша подписка {config.SERVICE_NAME} активирована. Ссылка: {sub_url}</p>"

    return get_base_html(title, content)


def get_status_email(email, is_active, up, down, total, expiry_time_ms):
    """Письмо со статусом использования трафика и подписки."""
    title = f"Статус вашей подписки {config.SERVICE_NAME}"

    used_bytes = up + down
    gb_factor = 1024 * 1024 * 1024

    used_gb = round(used_bytes / gb_factor, 2)
    limit_gb = round(total / gb_factor, 2) if total > 0 else "Безлимит"

    percent = 0
    progress_bar_html = ""
    if total > 0:
        percent = min(round((used_bytes / total) * 100, 1), 100)
        progress_bar_html = f"""
            <p style="margin-bottom: 5px; color: #9ca3af;">Использовано трафика: {percent}%</p>
            <div class="progress-bar">
                <div class="progress-fill" style="width: {percent}%;"></div>
            </div>
        """

    if expiry_time_ms > 0:
        expiry_date = datetime.fromtimestamp(expiry_time_ms / 1000).strftime('%Y-%m-%d %H:%M:%S')
    else:
        expiry_date = "Бессрочно"

    status_text = "<span style='color: #10b981; font-weight: bold;'>Активна</span>" if is_active else "<span style='color: #ef4444; font-weight: bold;'>Заблокирована / Истекла</span>"

    try:
        html = _load_template("status.html")
        content = (html
                   .replace("{{service_name}}", config.SERVICE_NAME)
                   .replace("{{email}}", email)
                   .replace("{{status_text}}", status_text)
                   .replace("{{expiry_date}}", expiry_date)
                   .replace("{{used_gb}}", str(used_gb))
                   .replace("{{limit_gb}}", str(limit_gb))
                   .replace("{{progress_bar}}", progress_bar_html))
    except Exception as e:
        logger.error(f"Ошибка загрузки status.html: {e}")
        content = f"<p>Статус подписки для {email}: {status_text}. Использовано: {used_gb} ГБ из {limit_gb} ГБ.</p>"

    return get_base_html(title, content)

def get_help_email(email, sub_url=None):
    """Письмо-инструкция по командам."""
    title = f"Справка и список команд {config.SERVICE_NAME}"

    if sub_url:
        sub_info = f"""
        <p>Ваша ссылка подписки:</p>
        <div class="code-box">{sub_url}</div>
        """
    else:
        sub_info = f"<p>Вы еще не зарегистрированы в системе {config.SERVICE_NAME}. Отправьте кодовое слово с темой или телом для регистрации.</p>"

    try:
        html = _load_template("help.html")
        content = (html
                   .replace("{{service_name}}", config.SERVICE_NAME)
                   .replace("{{sub_info}}", sub_info))
    except Exception as e:
        logger.error(f"Ошибка загрузки help.html: {e}")
        content = f"<p>Справка VPN. {sub_info}</p>"

    return get_base_html(title, content)


def get_broadcast_email(subject, message_body):
    """Письмо рассылки от имени администратора."""
    title = subject
    formatted_body = message_body.replace("\n", "<br>")

    try:
        html = _load_template("broadcast.html")
        content = (html
                   .replace("{{service_name}}", config.SERVICE_NAME)
                   .replace("{{formatted_body}}", formatted_body))
    except Exception as e:
        logger.error(f"Ошибка загрузки broadcast.html: {e}")
        content = f"<p>{formatted_body}</p>"

    return get_base_html(title, content)
