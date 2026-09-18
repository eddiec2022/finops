from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://finops:finops@db:5432/finops"

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_subscription_id: str = ""

    idle_cpu_threshold_percent: float = 10.0
    idle_lookback_days: int = 14
    cost_lookback_days: int = 90
    forecast_trailing_window_days: int = 30
    # Non-peak-scheduling candidate: flag when off-peak average CPU is at most
    # this fraction of peak average CPU (e.g. 0.5 = off-peak usage is half of
    # peak or less).
    off_peak_usage_ratio_threshold: float = 0.5


settings = Settings()
