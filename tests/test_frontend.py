from app.frontend import ASSETS


def test_fixed_browser_assets_are_public_but_api_stays_private(api):
    client, _ = api
    client.cookies.clear()
    for path in ASSETS:
        response = client.get(path)
        assert response.status_code == 200
        assert "script-src 'self'" in response.headers["content-security-policy"]
        assert "'unsafe-inline'" not in response.headers["content-security-policy"]
        assert response.headers["cache-control"].endswith("no-store")
    assert client.get("/api/items").status_code == 401
    assert client.get("/assets/../config.py").status_code == 401
    assert client.get("/assets/missing.js").status_code == 401
    assert client.post("/").status_code == 401


def test_shell_keeps_origin_and_host_protection(api):
    client, _ = api
    assert client.get("/", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 403
    assert client.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403
    assert client.head("/").status_code == 200
    response = client.get("/api/status")
    assert (
        response.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    )
