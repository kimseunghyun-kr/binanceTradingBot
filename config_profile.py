import os

# this is only for dev convenience. make sure to change for prod or use REAL ENV VARIABLES
PROFILE = os.getenv("PROFILE", "development")
DOTENV_FILE = f".env.{PROFILE}" if os.path.exists(f".env.{PROFILE}") else ".env"
