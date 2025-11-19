import os
import requests
import time
from django.conf import settings

BASE_LIVE = "https://pay.pesapal.com/v3"
BASE_TEST = "https://cybqa.pesapal.com/pesapalv3"
BASE_URL = BASE_TEST if settings.PESAPAL_TEST_MODE else BASE_LIVE

# Simple in-memory token cache (for demo). Replace with DB/cache in production.
_token_cache = {"token": None, "expires_at": 0}

def get_access_token():
    now = int(time.time())
    if _token_cache["token"] and _token_cache["expires_at"] > now + 30:
        return _token_cache["token"]

    url = f"{BASE_URL}/api/Auth/RequestToken"
    payload = {
        "consumer_key": settings.PESAPAL_CONSUMER_KEY,
        "consumer_secret": settings.PESAPAL_CONSUMER_SECRET
    }
    resp = requests.post(url, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    token = data.get("token")
    # Pesapal may return token expiry info; if not, set short TTL
    _token_cache["token"] = token
    _token_cache["expires_at"] = now + 60 * 50
    return token

def register_ipn(callback_url):
    """
    Register IPN URL and return notification_id.
    Only need to do once (store PESAPAL_IPN_ID in env or DB).
    """
    token = get_access_token()
    url = f"{BASE_URL}/api/URLSetup/RegisterIPN"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"url": callback_url, "ipn_notification_type": "POST"}
    r = requests.post(url, json=payload, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()  # should contain notification_id

def submit_order(merchant_reference, amount, email, phone, description, notification_id):
    token = get_access_token()
    url = f"{BASE_URL}/api/Transactions/SubmitOrderRequest"
    headers = {"Authorization": f"Bearer {token}"}
    payload = {
        "id": merchant_reference,
        "amount": float(amount),
        "currency": "KES",
        "description": description,
        "callback_url": settings.PESAPAL_CALLBACK_URL,
        "notification_id": notification_id,
        "billing_address": {
            "email_address": email,
            "phone_number": phone,
            "country_code": "KE",
            "first_name": "Customer",
            "last_name": "User"
        }
    }
    r = requests.post(url, json=payload, headers=headers, timeout=20)
    r.raise_for_status()
    return r.json()

def get_transaction_status(order_tracking_id):
    token = get_access_token()
    url = f"{BASE_URL}/api/Transactions/GetTransactionStatus?orderTrackingId={order_tracking_id}"
    headers = {"Authorization": f"Bearer {token}"}
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    return r.json()
