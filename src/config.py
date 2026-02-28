from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Azure OpenAI
    prompt_generation_endpoint: str
    api_version: str
    prompt_subscription_key: str

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
