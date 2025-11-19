from rest_framework import serializers
from .models import PesapalOrder, SubscriptionPlan, Subscription

class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = "__all__"

class CreateOrderSerializer(serializers.Serializer):
    plan_id = serializers.IntegerField()

class PesapalOrderSerializer(serializers.ModelSerializer):
    class Meta:
        model = PesapalOrder
        fields = "__all__"
