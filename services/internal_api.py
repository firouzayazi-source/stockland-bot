"""Legacy payment API entrypoint.

The old Flask internal API has been replaced by the FastAPI payment service.
Keep this module as a compatibility wrapper for deployments that still import
``services.internal_api:app``.
"""

import os

from payment_service import app


if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT") or os.getenv("INTERNAL_API_PORT") or "8000")
    uvicorn.run("payment_service:app", host="0.0.0.0", port=port)
