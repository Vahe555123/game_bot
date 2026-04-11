from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from app.api.payment_utils import resolve_fail_page_url
from config.settings import settings

router = APIRouter(prefix="/payment", tags=["Payment Return"])


@router.get("/return", response_class=HTMLResponse, summary="Return from external payment page")
async def payment_return(
    status: str = Query("cancelled"),
    next_path: str = Query("/", alias="next"),
):
    site_url = resolve_fail_page_url(settings.PUBLIC_APP_URL, settings.DIGISELLER_FAILPAGE_URL)
    normalized_next = next_path if next_path.startswith("/") and not next_path.startswith("//") else "/"
    target_url = f"{site_url.rstrip('/')}{normalized_next}"
    separator = "&" if "?" in target_url else "?"
    target_url = f"{target_url}{separator}payment={quote(status or 'cancelled')}"

    html = f"""<!doctype html>
<html lang="ru">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="refresh" content="0; url={target_url}" />
    <title>Возврат на сайт</title>
    <script>
      window.location.replace({target_url!r});
    </script>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        background: #020617;
        color: #e2e8f0;
        font-family: sans-serif;
      }}
      a {{
        color: #38bdf8;
        font-weight: 700;
      }}
    </style>
  </head>
  <body>
    <main>
      <p>Возвращаем Вас на сайт...</p>
      <p><a href="{target_url}">Вернуться вручную</a></p>
    </main>
  </body>
</html>"""
    return HTMLResponse(html)
