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
    supabase_key: str = ""
    
    # Wildberries
    wb_phone: str = ""
    wb_headless: bool = True
    wb_state_file: str = "storage/state.json"
    wb_downloads_path: str = "storage/downloads"
    wb_state_save_interval: int = 300  # Save browser state every N seconds (default: 5 minutes)
    
    # Admin for auth codes
    admin_telegram_id: int = 0
    
    # Pricing
    report_price: int = 500  # Price per report in rubles
    payment_token: str = ""  # Payment provider token
    
    # App
    debug: bool = False
    log_level: str = "INFO"
    
    @property
    def admin_id_list(self) -> list[int]:
        """Parse admin IDs from comma-separated string"""
        if not self.admin_ids:
            return []
        return [int(id_.strip()) for id_ in self.admin_ids.split(",") if id_.strip()]


# Global settings instance
settings = BotSettings()
