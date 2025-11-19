from django.contrib import admin
from .models import SubscriptionPlan, Subscription, PesapalOrder, IPNLog
# Register your models here.
admin.site.register(SubscriptionPlan)
admin.site.register(Subscription)
admin.site.register(PesapalOrder)
admin.site.register(IPNLog)