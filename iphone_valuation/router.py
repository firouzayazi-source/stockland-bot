"""روتر نازک FastAPI — فقط auth + اعتبارسنجی سطحی + صدا زدن service. منطق این‌جا نیست."""
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from . import service as ivservice
from . import db as ivdb

router = APIRouter(prefix="/api/v1/iphone")


def _auth_optional_uid(request: Request) -> int | None:
    try:
        from api import _auth_optional
        return _auth_optional(request)
    except Exception:
        return None


@router.get("/models")
async def iphone_models():
    return JSONResponse({"ok": True, "models": ivservice.list_models_with_capacities()})


@router.get("/prices")
async def iphone_prices(model_id: int | None = None):
    caps = ivdb.list_capacities(model_id=model_id, active_only=True)
    return JSONResponse({"ok": True, "prices": caps})


@router.get("/options")
async def iphone_options():
    """گزینه‌های قابل‌انتخاب هر دستهٔ ضریب (باتری/تعمیرات/رجیستری/پک/ظاهر/کابل/وضعیت کلی)."""
    return JSONResponse({"ok": True, "options": ivservice.list_selectable_coefficients()})


@router.post("/valuate")
async def iphone_valuate(request: Request):
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="بدنهٔ درخواست نامعتبر است")

    uid = _auth_optional_uid(request)
    if uid:
        payload["user_id"] = uid

    try:
        result = ivservice.valuate(payload)
    except ivservice.ValuationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse({"ok": True, "result": result})
