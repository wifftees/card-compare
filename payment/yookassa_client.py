"""YooKassa API client for payment processing"""
import base64
import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any
import aiohttp

from bot.config import settings

logger = logging.getLogger(__name__)


class YookassaClient:
    """Client for interacting with YooKassa API"""
    
    BASE_URL = "https://api.yookassa.ru/v3"
    
    def __init__(self, shop_id: str = None, secret_key: str = None):
        """
        Initialize YooKassa client
        
        Args:
            shop_id: YooKassa shop ID (from settings if not provided)
            secret_key: YooKassa secret key (from settings if not provided)
        """
        self.shop_id = shop_id or settings.yookassa_shop_id
        self.secret_key = secret_key or settings.yookassa_secret_key
        
        # Validate credentials
        if not self.shop_id or not self.secret_key:
            logger.error(
                f"❌ YooKassa credentials not configured! "
                f"shop_id={'SET' if self.shop_id else 'EMPTY'}, "
                f"secret_key={'SET' if self.secret_key else 'EMPTY'}"
            )
        else:
            # Log masked credentials for debugging
            masked_key = self.secret_key[:8] + "..." if len(self.secret_key) > 8 else "***"
            logger.info(f"🔑 YooKassa client initialized: shop_id={self.shop_id}, key={masked_key}")
        
        # Create Basic Auth credentials
        credentials = f"{self.shop_id}:{self.secret_key}"
        self.auth_header = base64.b64encode(credentials.encode()).decode()
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Generate request headers with Basic Auth and Idempotence-Key
        
        Returns:
            Dict with Authorization, Idempotence-Key, and Content-Type
        """
        idempotence_key = str(uuid.uuid4())
        logger.debug(f"Generated Idempotence-Key: {idempotence_key}")
        
        return {
            "Authorization": f"Basic {self.auth_header}",
            "Idempotence-Key": idempotence_key,
            "Content-Type": "application/json"
        }
    
    async def create_payment(
        self,
        amount: float,
        order_id: str,
        description: str
    ) -> Dict[str, Any]:
        """
        Create payment in YooKassa
        
        Args:
            amount: Payment amount in rubles (e.g., 300.00)
            order_id: Unique order ID (UUID) for metadata
            description: Payment description
            
        Returns:
            Dict with payment data including confirmation_url
            
        Raises:
            Exception: If payment creation fails
        """
        # Calculate expiration time: +12 hours
        expires_at = (datetime.utcnow() + timedelta(hours=12)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        
        # Build request payload (matching Kotlin implementation)
        payload = {
            "amount": {
                "value": f"{amount:.2f}",  # MUST be string!
                "currency": "RUB"
            },
            "description": description,
            "locale": "ru_RU",
            "expires_at": expires_at,
            "metadata": {
                "order_id": order_id  # Critical: used to identify payment in webhook
            },
            "confirmation": {
                "type": "redirect",
                "return_url": settings.yookassa_return_url
            },
            "capture": True,  # Automatically capture payment
            "receipt": {
                "customer": {
                    "email": "iliybugriy@gmail.com"  # TODO: use real user email if available
                },
                "items": [
                    {
                        "description": "Услуги ИП",
                        "amount": {
                            "value": f"{amount:.2f}",
                            "currency": "RUB"
                        },
                        "vat_code": 1,  # 1 = No VAT (for IP on simplified tax system - УСН)
                        "quantity": 1
                    }
                ]
            }
        }
        
        logger.debug(f"Creating payment with payload: {payload}")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.BASE_URL}/payments",
                    headers=self._get_headers(),
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    response_data = await response.json()
                    
                    logger.debug(f"YooKassa response: {response_data}")
                    
                    if response.status == 200:
                        status = response_data.get("status")
                        if status == "pending":
                            confirmation = response_data.get("confirmation", {})
                            confirmation_url = confirmation.get("confirmation_url")
                            
                            logger.info(
                                f"✅ Payment created successfully: "
                                f"order_id={order_id}, confirmation_url={confirmation_url}"
                            )
                            
                            return response_data
                        else:
                            raise Exception(f"Unexpected payment status: {status}")
                    else:
                        error_msg = response_data.get("description", "Unknown error")
                        raise Exception(
                            f"YooKassa API error: {response.status} - {error_msg}"
                        )
        
        except aiohttp.ClientError as e:
            logger.error(f"Network error creating payment: {e}", exc_info=True)
            raise Exception(f"Failed to connect to YooKassa: {e}")
        except Exception as e:
            logger.error(f"Error creating payment: {e}", exc_info=True)
            raise
