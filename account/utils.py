from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.utils import timezone
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


def send_dashboard_email(user, reconnect_contacts, upcoming_events, today):
    """
    Send dashboard reminder email to user with optimized queries and better formatting.
    Returns True if email was sent, False otherwise.
    """
    try:
        # Quick validation checks
        if not user.email:
            return False

        # Check if email was already sent today
        last_sent = getattr(user, "last_dashboard_email_sent", None)
        if last_sent == today:
            logger.info(f"Email already sent today for {user.email}")
            return False

        # Only prepare data if we're actually sending
        has_reconnect = reconnect_contacts.exists()
        has_events = upcoming_events.exists()
        
        if not has_reconnect and not has_events:
            logger.info(f"No content for {user.email}, skipping")
            return False

        # Get user's name
        user_name = getattr(user, 'full_name', None) or getattr(user, 'first_name', '') or user.email.split('@')[0]

        # Prepare content
        reconnect_list = []
        if has_reconnect:
            for contact in reconnect_contacts[:5]:
                days_since = "Never contacted" if not contact.last_interaction else \
                    f"{(today - contact.last_interaction.date()).days} days ago"
                reconnect_list.append({
                    'name': contact.name,
                    'days_since': days_since
                })

        event_list = []
        if has_events:
            for event in upcoming_events[:5]:
                days_until = (event.date - today).days
                event_list.append({
                    'title': event.title,
                    'date': event.date.strftime('%B %d, %Y'),
                    'days_until': f"{days_until} days" if days_until > 0 else "Today!",
                    'contact_name': event.contact.name if event.contact else None
                })

        # Try to send HTML email first, fall back to plain text
        try:
            # HTML version
            html_message = render_to_string('account/emails/dashboard_reminder.html', {
                'user_name': user_name,
                'reconnect_list': reconnect_list,
                'event_list': event_list,
                'has_reconnect': has_reconnect,
                'has_events': has_events,
                'today': today,
                'dashboard_url': f"{settings.FRONTEND_URL}/dashboard" if hasattr(settings, 'FRONTEND_URL') else None,
            })
            
            # Plain text fallback
            text_message = f"""
Hello {user_name},

Here are your reminders for today, {today.strftime('%B %d, %Y')}:

{f"🔔 Contacts to Reconnect ({len(reconnect_list)}):" if reconnect_list else ""}
{chr(10).join([f'- {c["name"]} ({c["days_since"]})' for c in reconnect_list]) if reconnect_list else "None"}

{f"📅 Upcoming Events ({len(event_list)}):" if event_list else ""}
{chr(10).join([f'- {e["title"]} on {e["date"]} ({e["days_until"]})' + (f' with {e["contact_name"]}' if e["contact_name"] else '') for e in event_list]) if event_list else "None"}

{f"View your dashboard: {settings.FRONTEND_URL}/dashboard" if hasattr(settings, 'FRONTEND_URL') else "Login to view your dashboard"}

Best regards,
Circo Team
"""
            
            email = EmailMultiAlternatives(
                subject=f"Your Circo Daily Reminders - {today.strftime('%B %d')}",
                body=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
            
        except Exception as template_error:
            # Fallback to simple email if template rendering fails
            logger.warning(f"Template rendering failed for {user.email}, sending plain text: {str(template_error)}")
            
            simple_message = f"""
Hello {user_name},

Here are your reminders for today:

{f"🔔 Contacts to Reconnect:" if reconnect_list else ""}
{chr(10).join([f'- {c["name"]}' for c in reconnect_list]) if reconnect_list else "None"}

{f"📅 Upcoming Events:" if event_list else ""}
{chr(10).join([f'- {e["title"]} on {e["date"]}' for e in event_list]) if event_list else "None"}

Login to your dashboard to see more details.

Best regards,
Circo Team
"""
            
            send_mail(
                subject="Your Dashboard Reminders",
                message=simple_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )

        # Update last sent timestamp atomically
        if hasattr(user, "last_dashboard_email_sent"):
            try:
                with transaction.atomic():
                    User = type(user)
                    User.objects.filter(pk=user.pk).update(
                        last_dashboard_email_sent=today
                    )
            except Exception as db_error:
                logger.error(f"Failed to update last_sent for {user.email}: {str(db_error)}")

        logger.info(f"Dashboard email sent to {user.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {user.email}: {str(e)}", exc_info=True)
        return False