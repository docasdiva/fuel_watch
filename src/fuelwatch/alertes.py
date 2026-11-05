"""Envoi d'alertes vers un webhook Discord ou Slack (URL dans ALERTE_WEBHOOK_URL)."""
import logging
import os

import requests
from dotenv import load_dotenv

load_dotenv()
log = logging.getLogger(__name__)


def envoyer_alerte(message: str) -> bool:
    """Envoie `message` au webhook configuré. Renvoie False s'il n'y en a pas."""
    url = os.environ.get("ALERTE_WEBHOOK_URL")
    if not url:
        log.warning("ALERTE (aucun webhook configuré) : %s", message)
        return False
    # Discord attend la clé « content », Slack la clé « text ».
    payload = {"content": message} if "discord.com" in url else {"text": message}
    response = requests.post(url, json=payload, timeout=10)
    response.raise_for_status()
    return True