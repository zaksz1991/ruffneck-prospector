"""
Celery Beat schedule for RuffNeck automation.
Start with: celery -A app.tasks beat --loglevel=info
(or use docker-compose beat service)
"""
from celery.schedules import crontab

# Import app from tasks module path used in project
beat_schedule = {
    # Process due sequence emails every 30 minutes
    "process-sequences-every-30-min": {
        "task": "process_due_sequences",
        "schedule": 30 * 60,  # seconds
    },
    # Check Gmail inbox for replies every 20 minutes
    "check-replies-every-20-min": {
        "task": "check_replies",
        "schedule": 20 * 60,
        "kwargs": {"since_hours": 48},
    },
    # Optional: daily discovery at 8:00 AM UTC – enable by uncommenting
    # "daily-discovery-morning": {
    #     "task": "run_daily_discovery",
    #     "schedule": crontab(hour=8, minute=0),
    #     "kwargs": {"location": "", "services": None},
    # },
}

timezone = "UTC"
