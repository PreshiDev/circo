from django.core.mail import send_mail
from django.conf import settings

def send_dashboard_email(user, reconnect_contacts, upcoming_events, today):
    try:
        last_sent = getattr(user, "last_dashboard_email_sent", None)

        should_send_email = (
            user.email and
            (reconnect_contacts.exists() or upcoming_events.exists()) and
            last_sent != today
        )

        if not should_send_email:
            return

        reconnect_list = "\n".join([
            f"- {c.name}" for c in reconnect_contacts[:5]
        ]) or "None"

        event_list = "\n".join([
            f"- {e.title} on {e.date}" for e in upcoming_events[:5]
        ]) or "None"

        message = f"""
Hello {getattr(user, 'full_name', '') or user.email},

Here are your reminders for today:

🔔 Contacts to reconnect:
{reconnect_list}

📅 Upcoming events:
{event_list}

Login to your dashboard to see more details.

- Circo App
"""

        send_mail(
            subject="Your Dashboard Reminders",
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=True
        )

        # ✅ Only save if field exists
        if hasattr(user, "last_dashboard_email_sent"):
            user.last_dashboard_email_sent = today
            user.save(update_fields=["last_dashboard_email_sent"])

    except Exception as e:
        print("Email error:", str(e))