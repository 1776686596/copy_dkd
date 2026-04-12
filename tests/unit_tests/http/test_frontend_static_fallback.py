from types import SimpleNamespace

import pytest

from langbot.pkg.api.http.controller.main import HTTPController
from langbot.pkg.api.http.controller import group


@pytest.mark.asyncio
async def test_missing_asset_does_not_fallback_to_spa_index(tmp_path, monkeypatch):
    frontend_dir = tmp_path / "web" / "dist"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("<html>index</html>", encoding="utf-8")
    (frontend_dir / "404.html").write_text("<html>missing</html>", encoding="utf-8")

    monkeypatch.setattr(group, "preregistered_groups", [])

    from langbot.pkg.utils import paths

    monkeypatch.setattr(paths, "get_frontend_path", lambda: str(frontend_dir))

    controller = HTTPController(SimpleNamespace())
    await controller.register_routes()

    client = controller.quart_app.test_client()
    response = await client.get("/assets/page-k3_NU236.js")

    assert response.status_code == 404
    assert "text/html" in response.content_type
    assert await response.get_data(as_text=True) == "<html>missing</html>"


@pytest.mark.asyncio
async def test_spa_route_still_falls_back_to_index(tmp_path, monkeypatch):
    frontend_dir = tmp_path / "web" / "dist"
    frontend_dir.mkdir(parents=True)
    (frontend_dir / "index.html").write_text("<html>index</html>", encoding="utf-8")
    (frontend_dir / "404.html").write_text("<html>missing</html>", encoding="utf-8")

    monkeypatch.setattr(group, "preregistered_groups", [])

    from langbot.pkg.utils import paths

    monkeypatch.setattr(paths, "get_frontend_path", lambda: str(frontend_dir))

    controller = HTTPController(SimpleNamespace())
    await controller.register_routes()

    client = controller.quart_app.test_client()
    response = await client.get("/home/bots")

    assert response.status_code == 200
    assert "text/html" in response.content_type
    assert await response.get_data(as_text=True) == "<html>index</html>"
