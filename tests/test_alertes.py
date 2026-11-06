from fuelwatch import alertes


def test_sans_webhook_ne_fait_rien(monkeypatch):
    monkeypatch.delenv("ALERTE_WEBHOOK_URL", raising=False)
    assert alertes.envoyer_alerte("test") is False


def test_discord_utilise_la_cle_content(monkeypatch):
    envois = []

    class FausseReponse:
        def raise_for_status(self):
            pass

    def faux_post(url, json, timeout):
        envois.append((url, json))
        return FausseReponse()

    url = "https://discord.com/api/webhooks/123/abc"
    monkeypatch.setenv("ALERTE_WEBHOOK_URL", url)
    monkeypatch.setattr(alertes.requests, "post", faux_post)

    assert alertes.envoyer_alerte("échec") is True
    assert envois == [(url, {"content": "échec"})]


def test_slack_utilise_la_cle_text(monkeypatch):
    envois = []

    class FausseReponse:
        def raise_for_status(self):
            pass

    monkeypatch.setenv("ALERTE_WEBHOOK_URL", "https://hooks.slack.com/services/x")
    monkeypatch.setattr(
        alertes.requests,
        "post",
        lambda url, json, timeout: envois.append(json) or FausseReponse(),
    )

    alertes.envoyer_alerte("échec")
    assert envois == [{"text": "échec"}]
