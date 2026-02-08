"""Bot configuration using Pydantic Settings"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class BotSettings(BaseSettings):
    """Bot configuration from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Telegram Bot
    bot_token: str = ""
    admin_ids: str = ""  # Comma-separated list of admin IDs
    
    # Supabase
    supabase_url: str = ""
    supabase_key: str = ""  # Anon/public key for client-side operations
    supabase_service_key: str = ""  # Service role key for server-side operations (bypasses RLS)
    
    # Wildberries
    wb_phone: str = ""
    wb_headless: bool = True
    wb_state_file: str = "storage/state.json"
    wb_downloads_path: str = "storage/downloads"
    wb_state_save_interval: int = 300  # Save browser state every N seconds (default: 5 minutes)
    wb_browser_restart_interval: int = 86400  # Restart browser every N seconds (default: 24 hours)
    
    # Admin for auth codes
    admin_telegram_id: int = 0
    
    # Payment (legacy Telegram Payments - deprecated)
    payment_token: str = ""  # Payment provider token (no longer used)
    
    # YooKassa Payment Integration
    # OAuth 2.0 (recommended) - token starts with 'y0_'
    yookassa_oauth_token: str = ""
    # Basic Auth (fallback) - shop_id + secret_key
    yookassa_shop_id: str = ""
    yookassa_secret_key: str = ""
    yookassa_return_url: str = "https://t.me/your_bot"
    
    # Webhook Server
    webhook_host: str = "0.0.0.0"
    webhook_port: int = 8080
    webhook_path: str = "/api/payment/yookassa"
    
    # App
    debug: bool = False
    log_level: str = "INFO"
    
    # Logging
    log_dir: str = "logs"
    log_file_max_bytes: int = 10 * 1024 * 1024  # 10MB
    log_file_backup_count: int = 5  # Keep 5 backup files
    log_rotation_type: str = "size"  # "size" or "time" (daily)
    
    @property
    def admin_id_list(self) -> list[int]:
        """Parse admin IDs from comma-separated string"""
        if not self.admin_ids:
            return []
        return [int(id_.strip()) for id_ in self.admin_ids.split(",") if id_.strip()]


# Global settings instance
settings = BotSettings()
