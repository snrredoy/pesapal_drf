from django.urls import path
from .views import CreatePesapalOrderView, PesapalIPNView, ManualCheckView, RegisterIPNView

urlpatterns = [
    path("pesapal/create/", CreatePesapalOrderView.as_view(), name="pesapal-create"),
    path("pesapal/ipn/", PesapalIPNView.as_view(), name="pesapal-ipn"),
    path("pesapal/check/", ManualCheckView.as_view(), name="pesapal-check"),
    path("pesapal/register-ipn/", RegisterIPNView.as_view(), name="pesapal-register-ipn"),
]
