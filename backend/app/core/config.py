from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://finops:finops@db:5432/finops"

    azure_tenant_id: str = ""
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_subscription_id: str = ""

    # Phase 2 (AWS) - optional/nullable: no real account exists yet (Task 19), and
    # the app must start and Azure-only functionality must keep working with these
    # unset, same as Azure's own empty-string defaults above.
    aws_account_id: str = ""
    aws_region: str = ""
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""

    idle_cpu_threshold_percent: float = 10.0
    idle_lookback_days: int = 14
    cost_lookback_days: int = 90
    forecast_trailing_window_days: int = 30
    # Non-peak-scheduling candidate: flag when off-peak average CPU is at most
    # this fraction of peak average CPU (e.g. 0.5 = off-peak usage is half of
    # peak or less).
    off_peak_usage_ratio_threshold: float = 0.5

    # The Vite dev server's own origin (docker-compose's frontend service, port
    # 5173) - browsers block cross-origin fetch() without this, even though the
    # backend is reachable fine outside a browser (curl, server-to-server).
    frontend_origin: str = "http://localhost:5173"

    @property
    def aws_configured(self) -> bool:
        """True once every AWS credential/setting is present.

        The sync endpoints use this to decide whether to also run the AWS
        connectors - see api/inventory.py and api/cost.py. Any partial
        configuration (e.g. region set but no keys yet) is treated as "not
        configured" rather than attempting a call that would just fail.
        """
        return bool(self.aws_account_id and self.aws_region and self.aws_access_key_id and self.aws_secret_access_key)


settings = Settings()
