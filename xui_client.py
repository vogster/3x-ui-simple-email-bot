import json
import logging
import requests
import uuid
from datetime import datetime, timedelta
import config

logger = logging.getLogger(__name__)

class XuiClient:
    def __init__(self):
        self.base_url = config.XUI_URL
        self.username = config.XUI_USERNAME
        self.password = config.XUI_PASSWORD
        self.api_token = config.XUI_API_TOKEN
        self.session = requests.Session()
        if self.api_token:
            self.session.headers.update({"Authorization": f"Bearer {self.api_token}"})
            self.is_logged_in = True
        else:
            self.is_logged_in = False

    def login(self):
        """Авторизуется в панели 3x-ui и сохраняет сессионные куки."""
        if self.api_token:
            self.is_logged_in = True
            return True
        url = f"{self.base_url}/login"
        payload = {
            "username": self.username,
            "password": self.password
        }
        try:
            response = self.session.post(url, data=payload, timeout=10)
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get("success"):
                    self.is_logged_in = True
                    logger.info("Успешная авторизация в 3x-ui.")
                    return True
                else:
                    logger.error(f"Ошибка входа в 3x-ui: {resp_json.get('msg')}")
            else:
                logger.error(f"Не удалось войти в 3x-ui. Статус: {response.status_code}, Ответ: {response.text}")
        except Exception as e:
            logger.error(f"Исключение при авторизации в 3x-ui: {e}")
        
        self.is_logged_in = False
        return False

    def _request(self, method, endpoint, **kwargs):
        """Обертка над requests с авто-логином при истечении сессии."""
        if not self.is_logged_in:
            if not self.login():
                raise Exception("Нет подключения к 3x-ui API (ошибка авторизации)")

        url = f"{self.base_url}{endpoint}"
        try:
            response = self.session.request(method, url, timeout=10, **kwargs)
            if response.status_code in (401, 403) or (response.status_code == 200 and "login" in response.url):
                if self.api_token:
                    raise Exception(f"Доступ запрещен (status={response.status_code}) при использовании API токена. Проверьте XUI_API_TOKEN.")
                
                logger.info("Сессия 3x-ui устарела. Повторный вход...")
                self.is_logged_in = False
                if self.login():
                    url = f"{self.base_url}{endpoint}"
                    response = self.session.request(method, url, timeout=10, **kwargs)
                else:
                    raise Exception("Повторная авторизация в 3x-ui не удалась.")
            
            return response
        except requests.RequestException as e:
            logger.error(f"Ошибка сети при запросе к 3x-ui ({endpoint}): {e}")
            raise

    def add_client(self, email: str, client_uuid: str = None, limit_gb: int = None, expire_days: int = None, inbound_ids: list = None):
        """
        Добавляет нового клиента во все указанные входящие соединения (inbounds).
        :param email: уникальный email/идентификатор клиента
        :param client_uuid: UUID клиента (если не передан, генерируется новый)
        :param limit_gb: лимит трафика в ГБ (если не передан, берется из конфига)
        :param expire_days: срок действия подписки в днях (если не передан, берется из конфига)
        :param inbound_ids: список ID входящих соединений (если не передан, берется из конфига)
        :return: (client_uuid, list_of_success_inbound_ids) или (None, []) в случае ошибки
        """
        if client_uuid is None:
            client_uuid = str(uuid.uuid4())
        
        if limit_gb is None:
            limit_gb = config.LIMIT_GB
            
        if expire_days is None:
            expire_days = config.EXPIRE_DAYS
            
        if inbound_ids is None:
            raw_ids = config.XUI_INBOUND_IDS
            if isinstance(raw_ids, str):
                inbound_ids = [int(x.strip()) for x in raw_ids.split(",") if x.strip().isdigit()]
            elif isinstance(raw_ids, list):
                inbound_ids = [int(x) for x in raw_ids]
            else:
                inbound_ids = []

        total_bytes = limit_gb * 1024 * 1024 * 1024 if limit_gb > 0 else 0

        if expire_days > 0:
            expire_time_ms = int((datetime.now() + timedelta(days=expire_days)).timestamp() * 1000)
        else:
            expire_time_ms = 0

        flow = config.XUI_FLOW

        payload = {
            "client": {
                "id": client_uuid,
                "email": email,
                "totalGB": total_bytes,
                "expiryTime": expire_time_ms,
                "tgId": 0,
                "subId": "",
                "limitIp": 0,
                "enable": True,
                "flow": flow
            },
            "inboundIds": inbound_ids
        }
        
        try:
            response = self._request("POST", "/panel/api/clients/add", json=payload)
            
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get("success"):
                    logger.info(f"Клиент {email} успешно добавлен в inbounds {inbound_ids} с UUID: {client_uuid}")
                    return client_uuid, inbound_ids
                else:
                    logger.error(f"Не удалось добавить клиента {email}: {resp_json.get('msg')}")
            else:
                logger.error(f"Неожиданный статус 3x-ui при добавлении клиента: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Исключение при добавлении клиента {email}: {e}")
        
        return None, []
    
    def get_client_data(self, email: str) -> dict or None:
        """
        Получает полные данные клиента по его email.
        :param email: email клиента для поиска
        :return: Словарь с данными клиента (из 'obj') или None, если клиент не найден/ошибка
        """
        try:
            endpoint = f"/panel/api/clients/get/{email}"
            response = self._request("GET", endpoint)
            
            if response.status_code == 200:
                resp_json = response.json()
                
                if resp_json.get("success"):
                    return resp_json.get("obj")
                else:
                    logger.error(f"Панель вернула ошибку при получении данных {email}: {resp_json.get('msg')}")
            else:
                logger.error(f"Неожиданный статус 3x-ui при получении данных {email}: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Исключение при получении данных клиента {email}: {e}")
            
        return None

    def get_all_clients(self) -> list or None:
        """
        Получает список всех клиентов из панели 3x-ui.
        :return: Список словарей с данными клиентов или None в случае ошибки.
        """
        try:
            endpoint = "/panel/api/clients/list"
            response = self._request("GET", endpoint)

            if response.status_code == 200:
                resp_json = response.json()

                if resp_json.get("success"):
                    return resp_json.get("obj", [])
                else:
                    logger.error(f"Панель вернула ошибку при получении списка клиентов: {resp_json.get('msg')}")
            else:
                logger.error(f"Неожиданный статус 3x-ui при получении списка клиентов: {response.status_code}")

        except Exception as e:
            logger.error(f"Исключение при получении списка клиентов: {e}")

        return None

    def get_client_traffic(self, email: str):
        """
        Возвращает данные о трафике для указанного клиента.
        """
        try:
            response = self._request("GET", f"/panel/api/clients/traffic/{email}")
            if response.status_code == 200:
                resp_json = response.json()
                if resp_json.get("success"):
                    data = resp_json.get("obj")
                    if data:
                        if isinstance(data, list):
                            return data[0] if len(data) > 0 else None
                        return data
                else:
                    logger.warning(f"Не удалось получить трафик для {email}: {resp_json.get('msg')}")
            else:
                logger.error(f"Неожиданный ответ 3x-ui при получении трафика. Статус: {response.status_code}")
        except Exception as e:
            logger.error(f"Исключение при получении трафика клиента из 3x-ui: {e}")
        
        return None