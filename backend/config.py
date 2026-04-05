import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:
    client_id: str
    client_secret: str
    port: int
    db_path: str
    token_path: str

    def __init__(self):
        self.client_id = os.environ['GOOGLE_CLIENT_ID']
        self.client_secret = os.environ['GOOGLE_CLIENT_SECRET']
        self.port = int(os.environ.get('PORT', '8080'))
        self.db_path = os.environ.get(
            'DB_PATH',
            str(Path.home() / '.gmail-cleanup' / 'gmail_cleanup.db'),
        )
        self.token_path = str(Path.home() / '.gmail-cleanup' / 'token.json')


settings = Settings()
