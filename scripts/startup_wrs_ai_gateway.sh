#!/bin/bash
cd "$(dirname "$0")/.."
PYTHONPATH=src WRS_ENV=capx-dev nohup python3 -u manage.py runserver 0.0.0.0:9912 > logs/capx_ai_gateway.log 2>&1 &