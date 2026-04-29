from django.apps import AppConfig
from gpt_gateway.models.openai_client import OpenAIClientManager


class gpt_gatewayAppConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "gpt_gateway"

    def ready(self):
        """
        Django automatically calls, and refreshes the access token every 8 hours.
        """
        print("✅ ChatAppConfig.ready() called!", flush=True)
        #global openai_client_manager
        OpenAIClientManager()
        print("✅ OpenAIClientManager initialized in Django AppConfig.")