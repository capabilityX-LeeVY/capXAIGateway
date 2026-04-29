import os

LLM_PROXY_URL = "https://llm-proxy.us-east-2.int.infra.intelligence.capx.com/azure/v1"

WRS_ENV = os.environ.get("WRS_ENV", "capx")

if WRS_ENV == "capx-dev":
    CHAT_WEB_URL = "capx-dev.capx.com"
    AI_GATEWAY_URL = "http://capx-dev.capx.com:9901/secret_service/get_client_secret/?client_id=2da4bbc8-5520-4c39-bd9a-404206511e0d&client_secret=PGxy7HnEdedhmGQOfDkGgc6T8DR3sg-shjp1GnzC1i4&agent_type=openai"
    SECRETSERVICE_URL = "capx-dev.capx.com"
else:
    CHAT_WEB_URL = "capx.capx.com"
    AI_GATEWAY_URL = "http://capx.capx.com:9901/secret_service/get_client_secret/?client_id=2da4bbc8-5520-4c39-bd9a-404206511e0d&client_secret=PGxy7HnEdedhmGQOfDkGgc6T8DR3sg-shjp1GnzC1i4&agent_type=openai"
    SECRETSERVICE_URL = "capx.capx.com"
