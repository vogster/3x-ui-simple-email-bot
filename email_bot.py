import time
import logging
import imaplib
import smtplib
import email
import uuid
import requests
from email.utils import parseaddr
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import config
import templates
from xui_client import XuiClient


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_email_body(msg):
    """Извлекает текстовое содержимое из объекта сообщения email."""
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                charset = part.get_content_charset() or "utf-8"
                try:
                    body += part.get_payload(decode=True).decode(charset, errors="ignore")
                except Exception as e:
                    logger.debug(f"Ошибка декодирования plain text части: {e}")
            elif content_type == "text/html" and "attachment" not in content_disposition and not body:
                charset = part.get_content_charset() or "utf-8"
                try:
                    body += part.get_payload(decode=True).decode(charset, errors="ignore")
                except Exception as e:
                    logger.debug(f"Ошибка декодирования html части: {e}")
    else:
        content_type = msg.get_content_type()
        if content_type in ("text/plain", "text/html"):
            charset = msg.get_content_charset() or "utf-8"
            try:
                body = msg.get_payload(decode=True).decode(charset, errors="ignore")
            except Exception as e:
                logger.debug(f"Ошибка декодирования простого сообщения: {e}")
    return body

def send_email_reply(to_email: str, subject: str, html_content: str):
    """Отправляет ответное письмо пользователю через SMTP."""
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = config.SMTP_USER
    msg['To'] = to_email

    msg.attach(MIMEText(html_content, 'html', 'utf-8'))
    
    try:
        if config.SMTP_PORT == 465:
            server = smtplib.SMTP_SSL(config.SMTP_SERVER, config.SMTP_PORT, timeout=10)
        else:
            server = smtplib.SMTP(config.SMTP_SERVER, config.SMTP_PORT, timeout=10)
            server.starttls()
            
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.sendmail(config.SMTP_USER, [to_email], msg.as_string())
        server.quit()
        logger.info(f"Письмо успешно отправлено на {to_email}. Тема: {subject}")
    except Exception as e:
        logger.error(f"Не удалось отправить письмо на {to_email}. Ошибка: {e}")
        raise

def send_gotify_notification(title: str, message: str):
    """Отправляет уведомление в Gotify, если настроены URL и токен."""
    if not config.GOTIFY_URL or not config.GOTIFY_TOKEN:
        logger.debug("Gotify не настроен. Пропуск отправки уведомления.")
        return

    url = f"{config.GOTIFY_URL.rstrip('/')}/message"
    headers = {
        "X-Gotify-Key": config.GOTIFY_TOKEN
    }
    payload = {
        "title": title,
        "message": message,
        "priority": config.GOTIFY_PRIORITY
    }
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=10)
        if response.status_code == 200:
            logger.info("Уведомление в Gotify успешно отправлено.")
        else:
            logger.error(f"Не удалось отправить уведомление в Gotify. Статус: {response.status_code}, Ответ: {response.text}")
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в Gotify: {e}")

def handle_registration(email_addr: str):
    """Обработка регистрации пользователя в панели и БД."""

    xui = XuiClient()
    client_info = xui.get_client_data(email_addr)

    if client_info:
        client = client_info.get("client", {})
        sub_url = f"{config.XUI_SUBSCRIPTION_BASE_URL}/{client.get("subId")}"
        subject = "Ваша подписка VPN"
        html = templates.get_welcome_email(sub_url, config.EXPIRE_DAYS, config.LIMIT_GB)
        send_email_reply(email_addr, subject, html)
        logger.info(f"Пользователь {email_addr} уже зарегистрирован. Выслана повторная ссылка.")
        return

    client_uuid = str(uuid.uuid4())

    
    logger.info(f"Регистрация нового пользователя: {email_addr} ...")
    success_uuid, success_inbounds = xui.add_client(
        email=email_addr,
        client_uuid=client_uuid,
        limit_gb=config.LIMIT_GB,
        expire_days=config.EXPIRE_DAYS,
        inbound_ids=config.XUI_INBOUND_IDS
    )

    client_info = xui.get_client_data(email_addr)

    if client_info:
        client = client_info.get("client", {})
        sub_id = client.get("subId")
        sub_url = f"{config.XUI_SUBSCRIPTION_BASE_URL}/{sub_id}"
        subject = "Ваша подписка VPN активирована!"
        html = templates.get_welcome_email(sub_url, config.EXPIRE_DAYS, config.LIMIT_GB)
        send_email_reply(email_addr, subject, html)
        logger.info(f"Пользователь {email_addr} успешно зарегистрирован.")
        send_gotify_notification(
            title="Новая регистрация VPN",
            message=f"Пользователь {email_addr} успешно зарегистрирован."
        )
    else:
        subject = "Ошибка создания подписки VPN"
        html = templates.get_base_html(
            subject, 
            "<p>К сожалению, не удалось автоматически создать подписку. Пожалуйста, попробуйте позже или обратитесь к администратору.</p>"
        )
        send_email_reply(email_addr, subject, html)
        logger.error(f"Не удалось зарегистрировать пользователя {email_addr} в 3x-ui.")

def handle_status(email_addr: str):
    """Запрос статистики трафика и статуса подписки."""
    xui = XuiClient()

    client_info = xui.get_client_data(email_addr)
    if not client_info:
        subject = "Вы не зарегистрированы"
        html = templates.get_base_html(
            subject,
            f"<p>Вы еще не зарегистрированы в нашей VPN системе. Отправьте кодовое слово для регистрации.</p>"
        )
        send_email_reply(email_addr, subject, html)
        return

    traffic = xui.get_client_traffic(email_addr)
    if traffic:
        up = traffic.get("up", 0)
        down = traffic.get("down", 0)
        total = traffic.get("total", 0)
        expiry_time = traffic.get("expiryTime", 0)
        enable = traffic.get("enable", True)
        is_user_enable = client_info.get("enable", True)
        
        is_active = enable and is_user_enable
        
        subject = "Статус вашей подписки VPN"
        html = templates.get_status_email(email_addr, is_active, up, down, total, expiry_time)
        send_email_reply(email_addr, subject, html)
    else:
        subject = "Ошибка получения статуса"
        html = templates.get_base_html(
            subject,
            "<p>Ваш профиль найден в базе данных, но отсутствует на VPN-сервере. Пожалуйста, обратитесь к администратору.</p>"
        )
        send_email_reply(email_addr, subject, html)
        logger.warning(f"Клиент {email_addr} найден в БД, но не найден в 3x-ui при запросе статуса.")

def handle_help(email_addr: str):
    """Отправка справочной информации."""
    xui = XuiClient()
    client_info = xui.get_client_data(email_addr)
    client = client_info.get("client", {})

    sub_url = None
    if client:
        sub_url = f"{config.XUI_SUBSCRIPTION_BASE_URL}/{client.get("subId")}"
    
    subject = "Инструкция и команды VPN"
    html = templates.get_help_email(email_addr, sub_url)
    send_email_reply(email_addr, subject, html)

def handle_unknown(email_addr: str, subject_received: str):
    """Ответ на неизвестную команду или письмо без кодового слова."""
    subject = "Неизвестная команда / Справка VPN"
    html = templates.get_base_html(
        subject,
        f"""
        <p>Мы получили ваше письмо с темой <b>"{subject_received}"</b>, но не смогли распознать команду.</p>
        <p><b>Доступные действия:</b></p>
        <ul>
            <li>Отправьте кодовое слово <b>{config.CODEWORD}</b> для автоматической регистрации подписки.</li>
            <li>Отправьте команду <b>/status</b> для проверки остатка трафика и срока действия.</li>
            <li>Отправьте команду <b>/help</b> для получения подробной инструкции по настройке приложений.</li>
        </ul>
        """
    )
    send_email_reply(email_addr, subject, html)


def get_all_active_emails_from_xui(xui_client) -> list:
    """
    Запрашивает всех клиентов из XUI и фильтрует только активные email.
    """
    clients = xui_client.get_all_clients()
    if not clients:
        logger.warning("Не удалось получить список клиентов из XUI или список пуст.")
        return []

    active_emails = []

    for client_obj in clients:
        emailObj = client_obj.get("email")
        if emailObj and client_obj.get("enable") is True:
            active_emails.append(emailObj)

    return active_emails

def handle_broadcast(broadcast_body: str):
    """Рассылка сообщения всем активным пользователям из XUI."""
    xui_instance = XuiClient()
    emails = get_all_active_emails_from_xui(xui_instance)

    if not emails:
        logger.info("Нет активных пользователей для рассылки.")
        return 0

    subject = "Важное уведомление от VPN-сервиса"
    html = templates.get_broadcast_email("Новости сервиса", broadcast_body)

    logger.info(f"Запуск email-рассылки для {len(emails)} пользователей...")
    success_count = 0
    for to_email in emails:
        try:
            time.sleep(0.5)
            send_email_reply(to_email, subject, html)
            success_count += 1
        except Exception as e:
            logger.error(f"Не удалось отправить рассылку на {to_email}: {e}")

    logger.info(f"Рассылка завершена. Успешно отправлено: {success_count}/{len(emails)}.")
    return success_count

def process_message(msg_num, from_email: str, subject: str, body: str, mail_conn):
    """Анализирует письмо и выполняет соответствующее действие."""
    mail_conn.store(msg_num, '+FLAGS', '\\Seen')
    
    subject_clean = subject.strip()
    body_clean = body.strip()

    logger.info(f"Обработка письма от {from_email}. Тема: '{subject_clean}'")

    is_admin = (from_email == config.ADMIN_EMAIL)

    is_broadcast_cmd = subject_clean.lower().startswith("/broadcast") or body_clean.lower().startswith("/broadcast")
    
    if is_admin and is_broadcast_cmd:
        broadcast_content = ""
        if subject_clean.lower().startswith("/broadcast"):
            broadcast_content = subject_clean[10:].strip()
        
        if not broadcast_content:
            if body_clean.lower().startswith("/broadcast"):
                broadcast_content = body_clean[10:].strip()
            else:
                broadcast_content = body_clean
                
        if broadcast_content:
            sent_count = handle_broadcast(broadcast_content)
            reply_subject = "Рассылка завершена"
            reply_html = templates.get_base_html(
                reply_subject,
                f"<p>Рассылка успешно отправлена {sent_count} пользователям.</p><p><b>Текст рассылки:</b><br>{broadcast_content}</p>"
            )
            send_email_reply(from_email, reply_subject, reply_html)
        else:
            reply_subject = "Ошибка рассылки"
            reply_html = templates.get_base_html(
                reply_subject,
                "<p>Текст рассылки пуст. Напишите текст сообщения после команды <code>/broadcast</code>.</p>"
            )
            send_email_reply(from_email, reply_subject, reply_html)
        return

    full_text = f"{subject_clean} {body_clean}".lower()
    codeword_lower = config.CODEWORD.lower()

    if codeword_lower in full_text or "/start" in full_text:
        handle_registration(from_email)
    elif "/status" in full_text:
        handle_status(from_email)
    elif "/help" in full_text:
        handle_help(from_email)
    else:
        handle_unknown(from_email, subject_clean)

def check_mail():
    """Подключается к IMAP, ищет непрочитанные письма и обрабатывает их."""
    if not config.IMAP_USER or not config.IMAP_PASSWORD:
        logger.error("Учетные данные IMAP не настроены. Пропуск проверки почты.")
        return

    mail = None
    try:
        mail = imaplib.IMAP4_SSL(config.IMAP_SERVER, config.IMAP_PORT, timeout=15)
        mail.login(config.IMAP_USER, config.IMAP_PASSWORD)
        mail.select("inbox")

        status, response = mail.search(None, "UNSEEN")
        if status != "OK":
            logger.error(f"Не удалось выполнить поиск писем в ящике: {status}")
            return
            
        messages = response[0].split()
        if not messages:
            logger.info("Нет новых непрочитанных писем.")
            return

        logger.info(f"Найдено новых писем для обработки: {len(messages)}")
        for num in messages:
            try:
                status, data = mail.fetch(num, "(RFC822)")
                if status != "OK" or not data:
                    logger.error(f"Не удалось получить письмо №{num}")
                    continue
                
                raw_email = data[0][1]
                msg = email.message_from_bytes(raw_email)

                _, from_email = parseaddr(msg.get("From"))
                from_email = from_email.strip().lower()
                if not from_email:
                    logger.warning(f"Не удалось извлечь адрес отправителя для письма №{num}")
                    continue

                subject_parts = []
                subject_header = msg.get("Subject", "")
                for decoded_str, charset in decode_header(subject_header):
                    if isinstance(decoded_str, bytes):
                        subject_parts.append(decoded_str.decode(charset or "utf-8", errors="ignore"))
                    else:
                        subject_parts.append(str(decoded_str))
                subject = " ".join(subject_parts).strip()

                body = get_email_body(msg)

                process_message(num, from_email, subject, body, mail)
                
            except Exception as e:
                logger.error(f"Ошибка при обработке отдельного письма №{num}: {e}", exc_info=True)
                
    except Exception as e:
        logger.error(f"Исключение при работе с IMAP-сервером: {e}")
    finally:
        if mail:
            try:
                mail.close()
            except Exception:
                pass
            try:
                mail.logout()
            except Exception:
                pass

def main():
    logger.info("Проверка соединения с 3x-ui...")
    xui = XuiClient()
    if xui.login():
        logger.info("Проверка связи с 3x-ui: УСПЕШНО.")
    else:
        logger.error("Проверка связи с 3x-ui: ОШИБКА. Бот запущен, но запросы к панели могут завершаться ошибкой.")

    logger.info(f"Бот запущен. Интервал опроса почты: {config.POLL_INTERVAL_SECONDS} секунд.")
    logger.info(f"Кодовое слово для регистрации: {config.CODEWORD}")

    while True:
        try:
            check_mail()
        except Exception as e:
            logger.error(f"Ошибка в цикле работы бота: {e}", exc_info=True)
        time.sleep(config.POLL_INTERVAL_SECONDS)

if __name__ == "__main__":
    main()
