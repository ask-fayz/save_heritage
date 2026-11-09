"""Prepare cached editions of existing records using this experiment's configuration."""
from app.config import Settings
from app.db import init_db,session
from app.services.editions import prepare
from app import repo
class Context:
    def __init__(self,settings):self.settings=settings
    def step(self,label):print(label,flush=True)
settings=Settings()
init_db(settings.db_path)
with session(settings.db_path) as conn:
    sites=repo.list_sites(conn)
for site in sites:
    print('Preparing '+site['slug'],flush=True)
    prepare(Context(settings),site['id'],'ru')
    print('Saved '+site['slug'],flush=True)
