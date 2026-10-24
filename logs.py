def get_recent_system_events() -> list[dict]:
    return [
        {
            "timestamp": "02:15 UTC",
            "type": "deploy",
            "service": "billing-worker",
            "message": "Routine database migration finished without errors.",
        },
        {
            "timestamp": "02:45 UTC",
            "type": "deploy",
            "service": "checkout-service-v2.14",
            "message": "Pushed release v2.14.0: Migrated EU payment gateway to SEPA v3 endpoint.",
        },
        {
            "timestamp": "02:50 UTC",
            "type": "error_trace",
            "service": "checkout-service-v2.14",
            "message": "HTTP 502 Bad Gateway: Upstream validation error on field 'iban_prefix'. 1,420 dropped checkout requests.",
        },
        {
            "timestamp": "03:10 UTC",
            "type": "alert",
            "service": "stripe-webhook",
            "message": "Automated refund trigger initiated for failed pending sessions.",
        },
    ]