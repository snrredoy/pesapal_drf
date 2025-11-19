import uuid
from django.conf import settings
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from .models import SubscriptionPlan, PesapalOrder, Subscription, IPNLog
from .serializers import CreateOrderSerializer, PesapalOrderSerializer
from .pesapal_service import submit_order, get_transaction_status, register_ipn

# Helper to compute dates
def now():
    return timezone.now()

class RegisterIPNView(APIView):
    """
    Optional admin-only: register your IPN and save notification id to env/DB.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        data = request.data
        callback_url = data.get("callback_url", settings.PESAPAL_CALLBACK_URL)
        result = register_ipn(callback_url)
        return Response(result)

class CreatePesapalOrderView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = CreateOrderSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        plan_id = serializer.validated_data["plan_id"]

        plan = SubscriptionPlan.objects.get(pk=plan_id)
        user = request.user

        merchant_reference = f"sub_{user.id}_{uuid.uuid4().hex[:12]}"
        # Use notification id from settings or environment. MUST be present.
        notification_id = getattr(settings, "PESAPAL_IPN_ID", None)
        if not notification_id:
            return Response({"error": "Pesapal notification_id (IPN) not configured. Register IPN first."},
                            status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        description = f"Subscription {plan.name} for user {user.id}"
        resp = submit_order(
            merchant_reference=merchant_reference,
            amount=plan.price,
            email=user.email or "",
            phone="",
            description=description,
            notification_id=notification_id
        )
        # resp should include a checkout_url and possibly order_tracking_id
        checkout_url = resp.get("checkout_url") or resp.get("payment_url") or resp.get("url")
        order_tracking_id = resp.get("order_tracking_id") or resp.get("orderTrackingId")  # sometimes present

        order = PesapalOrder.objects.create(
            user=user,
            plan=plan,
            merchant_reference=merchant_reference,
            order_tracking_id=order_tracking_id,
            amount=plan.price,
            status="PENDING",
            checkout_url=checkout_url
        )
        return Response({"checkout_url": checkout_url, "merchant_reference": merchant_reference})

class PesapalIPNView(APIView):
    """
    This is the IPN (webhook) endpoint that Pesapal will POST to.
    We persist the payload, then verify via GetTransactionStatus using order_tracking_id
    Then activate/renew subscription if completed.
    """
    permission_classes = [permissions.AllowAny]  # Pesapal will POST

    def post(self, request):
        payload = request.data
        # Save IPN raw payload for audit
        ipn = IPNLog.objects.create(payload=payload)

        # Try to extract order_tracking_id and merchant_reference
        order_tracking_id = payload.get("order_tracking_id") or payload.get("orderTrackingId")
        merchant_ref = payload.get("merchant_reference") or payload.get("merchantReference") or payload.get("merchant_reference")

        if not order_tracking_id:
            ipn.note = "No order_tracking_id in payload"
            ipn.save()
            return Response({"error": "Missing order_tracking_id"}, status=400)

        # Verify with Pesapal
        try:
            status_resp = get_transaction_status(order_tracking_id)
        except Exception as e:
            ipn.note = f"Failed to fetch transaction status: {str(e)}"
            ipn.save()
            return Response({"error": "Failed to verify transaction"}, status=500)

        # Example of status_resp structure: {'status': 'COMPLETED', 'order_tracking_id': '...', 'merchant_reference': '...'}
        tx_status = status_resp.get("status") or status_resp.get("transaction_status") or None
        merchant_ref = merchant_ref or status_resp.get("merchant_reference") or status_resp.get("merchantReference")
        ipn.note = f"Verified status: {tx_status}"
        ipn.processed = True
        ipn.save()

        if tx_status and tx_status.upper() == "COMPLETED":
            # find our order
            try:
                order = PesapalOrder.objects.get(merchant_reference=merchant_ref)
            except PesapalOrder.DoesNotExist:
                # maybe pesapal returned merchant_ref differently - try matching by order_tracking_id
                try:
                    order = PesapalOrder.objects.get(order_tracking_id=order_tracking_id)
                except PesapalOrder.DoesNotExist:
                    return Response({"error":"Order not found"}, status=404)

            order.status = "COMPLETED"
            order.order_tracking_id = order_tracking_id
            order.save()

            # Activate or extend subscription
            plan = order.plan
            now_dt = now()
            existing = Subscription.objects.filter(user=order.user, active=True, end_at__gt=now_dt).order_by("-end_at").first()
            if existing:
                start_at = existing.end_at
            else:
                start_at = now_dt
            end_at = start_at + timezone.timedelta(days=plan.duration_days)
            Subscription.objects.create(user=order.user, plan=plan, start_at=start_at, end_at=end_at, active=True)
            return Response({"message":"Subscription activated"}, status=200)

        else:
            # payment not completed
            return Response({"message":"Payment not completed"}, status=200)

class ManualCheckView(APIView):
    """
    Optional: Admin or user can call to manually check status using merchant_reference.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        mr = request.data.get("merchant_reference")
        try:
            order = PesapalOrder.objects.get(merchant_reference=mr)
        except PesapalOrder.DoesNotExist:
            return Response({"error":"Order not found"}, status=404)
        if not order.order_tracking_id:
            return Response({"error":"No order_tracking_id for this order"}, status=400)
        status_resp = get_transaction_status(order.order_tracking_id)
        return Response(status_resp)
