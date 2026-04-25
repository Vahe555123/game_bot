from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_admin_site_user
from app.auth.email_service import email_is_configured
from app.auth.exceptions import AuthServiceError
from app.auth.schemas import SiteUserPublic
from app.database.connection import get_db
from app.site_admin.schemas import (
    AdminActionResponse,
    AdminDashboardResponse,
    AdminHelpContentResponse,
    AdminHelpContentUpdateRequest,
    AdminProductCreateRequest,
    AdminProductDetailsResponse,
    AdminProductListResponse,
    AdminProductManualParseRequest,
    AdminProductManualParseStartResponse,
    AdminProductManualParseStatusResponse,
    AdminProductRecord,
    AdminProductUpdateRequest,
    AdminPurchaseFulfillRequest,
    AdminPurchaseListResponse,
    AdminPurchaseRecord,
    AdminPurchaseUpdateRequest,
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserRecord,
    AdminUserUpdateRequest,
)
from app.site_admin.service import get_site_admin_service
from app.site_orders.email_service import send_purchase_fulfilled_email

router = APIRouter(prefix="/site/admin", tags=["Site Admin"])


def _raise_http_auth_error(error: AuthServiceError) -> None:
    detail = {"message": error.message}
    detail.update(error.extra)
    raise HTTPException(status_code=error.status_code, detail=detail)


@router.get("/dashboard", response_model=AdminDashboardResponse, summary="Site admin dashboard")
def get_site_admin_dashboard(
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.get_dashboard(db)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/content/help", response_model=AdminHelpContentResponse, summary="Help page content")
def get_site_admin_help_content(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.get_help_content()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.put("/content/help", response_model=AdminHelpContentResponse, summary="Update help page content")
def update_site_admin_help_content(
    payload: AdminHelpContentUpdateRequest,
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.update_help_content(payload)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/users", response_model=AdminUserListResponse, summary="List site users")
def list_site_admin_users(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    role: str | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.list_users(
            db,
            page=page,
            limit=limit,
            search=search,
            role=role,
            is_active=is_active,
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/users", response_model=AdminUserRecord, summary="Create site user")
def create_site_admin_user(
    payload: AdminUserCreateRequest,
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.create_user(payload)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.put("/users/{user_id}", response_model=AdminUserRecord, summary="Update site user")
def update_site_admin_user(
    user_id: str,
    payload: AdminUserUpdateRequest,
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.update_user(user_id, payload, current_admin=current_admin)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.delete("/users/{user_id}", response_model=AdminActionResponse, summary="Delete site user")
def delete_site_admin_user(
    user_id: str,
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        service.delete_user(user_id, current_admin=current_admin)
    except AuthServiceError as error:
        _raise_http_auth_error(error)
    return AdminActionResponse(message="Пользователь удалён.")


@router.get("/products", response_model=AdminProductListResponse, summary="List products")
def list_site_admin_products(
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    search: str | None = Query(None),
    region: str | None = Query(None),
    category: str | None = Query(None),
    sort: str | None = Query("popular"),
    missing_region: str | None = Query(None),
    missing_localization: bool | None = Query(None),
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.list_products(
            db,
            page=page,
            limit=limit,
            search=search,
            region=region,
            category=category,
            sort=sort,
            missing_region=missing_region,
            missing_localization=missing_localization,
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/discounts/products", response_model=AdminProductListResponse, summary="List discounted products")
def list_site_admin_discount_products(
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    search: str | None = Query(None),
    region: str | None = Query(None),
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.list_discount_products(
            db,
            page=page,
            limit=limit,
            search=search,
            region=region,
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/discounts/update", summary="Start discount update parser")
async def start_site_admin_discount_update(
    test: bool = Query(False),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.start_discount_update(test=test)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/discounts/update/status", summary="Discount update parser status")
async def get_site_admin_discount_update_status(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.get_discount_update_status()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/discounts/update/pause", summary="Pause discount update parser")
async def pause_site_admin_discount_update(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.pause_discount_update()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/discounts/update/resume", summary="Resume discount update parser")
async def resume_site_admin_discount_update(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.resume_discount_update()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/discounts/update/cancel", summary="Cancel discount update parser")
async def cancel_site_admin_discount_update(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.cancel_discount_update()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


# ── Обновление цен (по products.pkl) ──────────────────────────────────────────
@router.post("/prices/update", summary="Start price update parser")
async def start_site_admin_price_update(
    test: bool = Query(False),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.start_price_update(test=test)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/prices/update/status", summary="Price update parser status")
async def get_site_admin_price_update_status(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.get_price_update_status()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/prices/update/pause", summary="Pause price update parser")
async def pause_site_admin_price_update(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.pause_price_update()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/prices/update/resume", summary="Resume price update parser")
async def resume_site_admin_price_update(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.resume_price_update()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/prices/update/cancel", summary="Cancel price update parser")
async def cancel_site_admin_price_update(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.cancel_price_update()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/products/{product_id}", response_model=AdminProductDetailsResponse, summary="Product details")
def get_site_admin_product(
    product_id: str,
    region: str = Query(...),
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.get_product(db, product_id=product_id, region=region)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/products", response_model=AdminProductDetailsResponse, summary="Create product")
def create_site_admin_product(
    payload: AdminProductCreateRequest,
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.create_product(db, payload)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/products/manual-parse", response_model=AdminProductManualParseStartResponse, summary="Manual product parse")
async def manual_parse_site_admin_product(
    payload: AdminProductManualParseRequest,
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.manual_parse_product(payload)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get(
    "/products/manual-parse/{task_id}",
    response_model=AdminProductManualParseStatusResponse,
    summary="Manual product parse status",
)
async def manual_parse_site_admin_product_status(
    task_id: str,
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.get_manual_parse_product_status(task_id)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.put("/products/{product_id}", response_model=AdminProductDetailsResponse, summary="Update product")
def update_site_admin_product(
    product_id: str,
    region: str = Query(...),
    payload: AdminProductUpdateRequest = ...,
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.update_product(db, product_id=product_id, region=region, payload=payload)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.delete("/products/{product_id}", response_model=AdminActionResponse, summary="Delete product")
def delete_site_admin_product(
    product_id: str,
    region: str = Query(...),
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        service.delete_product(db, product_id=product_id, region=region)
    except AuthServiceError as error:
        _raise_http_auth_error(error)
    return AdminActionResponse(message="Товар удалён.")


@router.delete("/products/{product_id}/all", response_model=AdminActionResponse, summary="Delete product in all regions")
def delete_site_admin_product_group(
    product_id: str,
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        deleted_count = service.delete_product_group(db, product_id=product_id)
    except AuthServiceError as error:
        _raise_http_auth_error(error)
    return AdminActionResponse(message=f"Удалено строк товара: {deleted_count}.")


@router.get("/unparsed-urls", summary="URLs из products.pkl, отсутствующие в БД")
def get_site_admin_unparsed_urls(
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    mode: str = Query("missing_any"),
    locale: str | None = Query(None),
    search: str | None = Query(None),
    region_count: int | None = Query(None, ge=0, le=3),
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.list_unparsed_urls(
            db,
            page=page,
            limit=limit,
            mode=mode,
            locale=locale,
            search=search,
            region_count=region_count,
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/unparsed-urls/collect", summary="Start collecting product URLs into products.pkl")
async def collect_site_admin_unparsed_urls(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.start_product_url_collection()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/unparsed-urls/collect/status", summary="Product URL collection status")
async def get_site_admin_unparsed_urls_collection_status(
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return await service.get_product_url_collection_status()
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.delete("/products/{product_id}/favorites/{favorite_id}", response_model=AdminActionResponse, summary="Delete product favorite")
def delete_site_admin_product_favorite(
    product_id: str,
    favorite_id: int,
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        service.delete_product_favorite(db, product_id=product_id, favorite_id=favorite_id)
    except AuthServiceError as error:
        _raise_http_auth_error(error)
    return AdminActionResponse(message="Товар удалён из избранного пользователя.")


@router.get("/purchases", response_model=AdminPurchaseListResponse, summary="List site purchases")
def list_site_admin_purchases(
    page: int = Query(1, ge=1),
    limit: int = Query(30, ge=1, le=100),
    status: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.list_purchases(db, page=page, limit=limit, status=status, search=search)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/purchases/{order_number}", response_model=AdminPurchaseRecord, summary="Purchase details")
def get_site_admin_purchase(
    order_number: str,
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.get_purchase(db, order_number=order_number)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.patch("/purchases/{order_number}", response_model=AdminPurchaseRecord, summary="Update purchase")
def update_site_admin_purchase(
    order_number: str,
    payload: AdminPurchaseUpdateRequest,
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.update_purchase(db, order_number=order_number, payload=payload)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.post("/purchases/{order_number}/fulfill", response_model=AdminPurchaseRecord, summary="Fulfill purchase")
def fulfill_site_admin_purchase(
    order_number: str,
    payload: AdminPurchaseFulfillRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        order = service.fulfill_purchase(db, order_number=order_number, payload=payload)
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    if payload.send_email and order.payment_email and email_is_configured():
        background_tasks.add_task(
            send_purchase_fulfilled_email,
            email=order.payment_email,
            order_payload=order.model_dump(),
        )

    return order


@router.delete("/purchases/{order_number}", response_model=AdminActionResponse, summary="Delete purchase")
def delete_site_admin_purchase(
    order_number: str,
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        service.delete_purchase(db, order_number=order_number)
    except AuthServiceError as error:
        _raise_http_auth_error(error)
    return AdminActionResponse(message="Заказ удалён.")
