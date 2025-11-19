from django.conf import settings
from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class SubscriptionPlan(models.Model):
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    duration_days = models.IntegerField(help_text="Duration in days (e.g., 30 for monthly)")

    def __str__(self):
        return f"{self.name} - {self.price}"

class Subscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="subscriptions")
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    start_at = models.DateTimeField()
    end_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    pesapal_correlation_id = models.CharField(max_length=255, blank=True, null=True)  # new
    frequency = models.CharField(max_length=20, blank=True, null=True)  # DAILY, WEEKLY, MONTHLY
    next_payment_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def is_active(self):
        return self.active and self.end_at > timezone.now()

    def __str__(self):
        return f"{self.user} - {self.plan.name} ({self.start_at.date()} → {self.end_at.date()})"

class PesapalOrder(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.CASCADE)
    merchant_reference = models.CharField(max_length=255, unique=True)
    order_tracking_id = models.CharField(max_length=255, blank=True, null=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=50, default="PENDING")  # PENDING, COMPLETED, FAILED
    checkout_url = models.URLField(blank=True, null=True)
    is_recurring = models.BooleanField(default=False)  # new
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class IPNLog(models.Model):
    payload = models.JSONField()
    received_at = models.DateTimeField(auto_now_add=True)
    processed = models.BooleanField(default=False)
    note = models.TextField(blank=True, null=True)
