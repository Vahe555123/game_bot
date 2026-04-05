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
    AdminProductCreateRequest,
    AdminProductListResponse,
    AdminProductRecord,
    AdminProductUpdateRequest,
    AdminPurchaseFulfillRequest,
    AdminPurchaseListResponse,
    AdminPurchaseRecord,
    AdminPurchaseUpdateRequest,
    AdminUserCreateRequest,
    AdminUserListResponse,
    AdminUserRecord,
)
from app.site_admin.service import get_site_admin_service
from app.site_orders.email_service import send_purchase_fulfilled_email

router = APIRouter(prefix="/site/admin", tags=["Site Admin"])


def _raise_http_auth_error(error: AuthServiceError) -> None:
    detail = {"message": error.message}
    detail.update(error.extra)
    raise HTTPException(status_code=error.status_code, detail=detail)


@router.get("/dashboard", response_model=AdminDashboardResponse, summary="Дашборд админки сайта")
def get_site_admin_dashboard(
    db: Session = Depends(get_db),
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.get_dashboard(db)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/users", response_model=AdminUserListResponse, summary="Список пользователей сайта")
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


@router.post("/users", response_model=AdminUserRecord, summary="Создать пользователя сайта")
def create_site_admin_user(
    payload: AdminUserCreateRequest,
    current_admin: SiteUserPublic = Depends(get_current_admin_site_user),
):
    service = get_site_admin_service()
    try:
        return service.create_user(payload)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.put("/users/{user_id}", response_model=AdminUserRecord, summary="Обновить пользователя сайта")
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


@router.delete("/users/{user_id}", response_model=AdminActionResponse, summary="Удалить пользователя сайта")
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


@router.get("/products", response_model=AdminProductListResponse, summary="Список товаров для админки")
def list_site_admin_products(
    page: int = Query(1, ge=1),
    limit: int = Query(24, ge=1, le=100),
    search: str | None = Query(None),
    region: str | None = Query(None),
    category: str | None = Query(None),
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
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/products/{product_id}", response_model=AdminProductRecord, summary="Карточка товара для админки")
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


@router.post("/products", response_model=AdminProductRecord, summary="Создать товар")
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


@router.put("/products/{product_id}", response_model=AdminProductRecord, summary="Обновить товар")
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


@router.delete("/products/{product_id}", response_model=AdminActionResponse, summary="Удалить товар")
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


@router.get("/purchases", response_model=AdminPurchaseListResponse, summary="Все покупки сайта")
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


@router.get("/purchases/{order_number}", response_model=AdminPurchaseRecord, summary="Детали покупки")
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


@router.patch("/purchases/{order_number}", response_model=AdminPurchaseRecord, summary="Обновить статус покупки")
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


@router.post("/purchases/{order_number}/fulfill", response_model=AdminPurchaseRecord, summary="Выдать заказ")
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


@router.delete("/purchases/{order_number}", response_model=AdminActionResponse, summary="Удалить заказ")
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
