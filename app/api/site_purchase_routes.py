from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.admin_auth import verify_admin_access
from app.auth.email_service import email_is_configured
from app.auth.dependencies import get_current_site_user
from app.auth.exceptions import AuthServiceError
from app.auth.schemas import SiteUserPublic
from app.database.connection import get_db
from app.site_orders.email_service import send_purchase_created_email, send_purchase_fulfilled_email
from app.site_orders.schemas import (
    AdminFulfillPurchaseRequest,
    AdminPurchaseListResponse,
    PurchaseCheckoutRequest,
    PurchaseListResponse,
    PurchaseOrderResponse,
)
from app.site_orders.service import get_site_purchase_service

router = APIRouter(prefix="/site/purchases", tags=["Site Orders"])


def _raise_http_auth_error(error: AuthServiceError) -> None:
    detail = {"message": error.message}
    detail.update(error.extra)
    raise HTTPException(status_code=error.status_code, detail=detail)


@router.post("/checkout", response_model=PurchaseOrderResponse, summary="Создать заказ и получить ссылку на оплату")
async def create_site_checkout(
    payload: PurchaseCheckoutRequest,
    background_tasks: BackgroundTasks,
    current_user: SiteUserPublic = Depends(get_current_site_user),
    db: Session = Depends(get_db),
):
    service = get_site_purchase_service()

    try:
        order = await service.create_checkout(
            db,
            site_user_id=current_user.id,
            product_id=payload.product_id,
            region=payload.region,
            use_ps_plus=payload.use_ps_plus,
            purchase_email=payload.purchase_email,
            platform=payload.platform,
            psn_email=payload.psn_email,
            psn_password=payload.psn_password,
            backup_code=payload.backup_code,
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    if current_user.email and email_is_configured():
        background_tasks.add_task(
            send_purchase_created_email,
            email=current_user.email,
            order_payload=order.model_dump(),
        )

    return order


@router.get("", response_model=PurchaseListResponse, summary="История покупок текущего пользователя")
async def list_site_purchases(
    days: int | None = Query(None, ge=1, le=365),
    current_user: SiteUserPublic = Depends(get_current_site_user),
    db: Session = Depends(get_db),
):
    service = get_site_purchase_service()

    try:
        orders = service.list_user_orders(db, site_user_id=current_user.id, days=days)
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    return PurchaseListResponse(orders=orders)


@router.post("/{order_number}/confirm-payment", response_model=PurchaseOrderResponse, summary="Подтвердить, что оплата выполнена")
async def confirm_site_purchase_payment(
    order_number: str,
    current_user: SiteUserPublic = Depends(get_current_site_user),
    db: Session = Depends(get_db),
):
    service = get_site_purchase_service()

    try:
        return service.confirm_payment(db, site_user_id=current_user.id, order_number=order_number)
    except AuthServiceError as error:
        _raise_http_auth_error(error)


@router.get("/admin/list", response_model=AdminPurchaseListResponse, summary="Список заказов сайта для администратора")
async def admin_list_site_purchases(
    request: Request,
    limit: int = Query(100, ge=1, le=300),
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access),
):
    service = get_site_purchase_service()

    try:
        orders = service.list_all_orders(db, limit=limit)
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    return AdminPurchaseListResponse(orders=orders, total=len(orders))


@router.post("/admin/{order_number}/fulfill", response_model=PurchaseOrderResponse, summary="Выдать заказ и отправить данные на email")
async def admin_fulfill_site_purchase(
    order_number: str,
    payload: AdminFulfillPurchaseRequest,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    admin_id: int = Depends(verify_admin_access),
):
    service = get_site_purchase_service()

    try:
        order = service.fulfill_order(
            db,
            order_number=order_number,
            delivery_title=payload.delivery_title,
            delivery_message=payload.delivery_message,
            delivery_items=[item.model_dump() for item in payload.delivery_items],
            status_note=payload.status_note,
        )
    except AuthServiceError as error:
        _raise_http_auth_error(error)

    if payload.send_email and order.payment_email and email_is_configured():
        background_tasks.add_task(
            send_purchase_fulfilled_email,
            email=order.payment_email,
            order_payload=order.model_dump(),
        )

    return order
