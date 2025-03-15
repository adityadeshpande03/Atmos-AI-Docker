#!/bin/bash
cd /app/frontend && python -m http.server 8080 &
cd /app && uvicorn src.app:app --host 0.0.0.0 --port 8000 --reload
