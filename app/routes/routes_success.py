from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["success"])


@router.get("/success", response_class=HTMLResponse)
async def success():
    return HTMLResponse(
        """
        <html>
            <head><title>Success</title></head>
            <body>
                <h1>Success</h1>
                <p>Demo success page</p>
                <p><a href="/">Back to home</a></p>
            </body>
        </html>
        """
    )
