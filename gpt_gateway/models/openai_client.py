import os
import sys
import time
import threading
import requests

# Import directly from the config module in the project root
from config.config import *
from openai import AzureOpenAI
from apscheduler.schedulers.background import BackgroundScheduler

class OpenAIClientManager:
    def __init__(self):
        self.api_base = LLM_PROXY_URL
        self.deployment_name = "gpt-4.1"
        self.api_version = "2024-10-21"

        self.api_key = None  
        self.token_refresh_url = AI_GATEWAY_URL
        self.token_refresh_interval = 8 * 60 * 60  

        self.client = None
        self.refresh_token() 
        self.initialize_client()
        self.start_token_refresh_scheduler()

    def refresh_token(self):
        try:
            response = requests.get(self.token_refresh_url)
            if response.status_code == 200:
                data = response.json()
                self.api_key = data["access_token"]
                print(f"✅ Token refreshed successfully at {time.strftime('%Y-%m-%d %H:%M:%S')},[{self.token_refresh_url}][{self.api_key}]")
                self.initialize_client()  # Re-initialize client with new token
            else:
                print(f"⚠️ Failed to refresh token: {response.status_code}, {response.text}")
        except Exception as e:
            print(f"❌ Error refreshing token: {e}")

    def initialize_client(self):
        if not self.api_key:
            print("⚠️ API key not available, will retry on next token refresh")
            return

        try:
            print(f"✅ Initializing OpenAI Client... {self.api_key}, {self.api_version}, {self.deployment_name}, {self.api_base}")
            self.client = AzureOpenAI(
                api_key=self.api_key,
                api_version=self.api_version,
                azure_deployment=self.deployment_name,
                azure_endpoint=self.api_base,
            )
            print(f"✅ OpenAI Client initialized for deployment: {self.deployment_name}")
        except Exception as e:
            print(f"❌ Failed to initialize OpenAI Client: {e}")

    def get_client(self):
        if not self.client:
            self.initialize_client()
        print(f"✅ Returning OpenAI Client: {self.client}")
        return self.client
    
    def get_access_token(self):
        return self.api_key

    def start_token_refresh_scheduler(self):
        scheduler = BackgroundScheduler()
        scheduler.add_job(self.refresh_and_initialize_client, 'interval', seconds=self.token_refresh_interval)
        scheduler.start()
        print("🔄 Token refresh scheduler started.")

    def refresh_and_initialize_client(self):
        self.refresh_token()
        # Client is already initialized in refresh_token method 
