from django.core.mail import EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from django.db import transaction
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def send_dashboard_email(user, reconnect_contacts, upcoming_events, today):
    """
    Send dashboard reminder email to user.
    Allows multiple sends per day by tracking send count instead of just date.
    Returns True if email was sent, False otherwise.
    """
    try:
        # Quick validation checks
        if not user.email:
            return False

        # Check if already sent maximum times today (2 times)
        last_sent = getattr(user, "last_dashboard_email_sent", None)
        send_count_today = getattr(user, "dashboard_email_count_today", 0)
        
        # Reset count if it's a new day
        if last_sent and last_sent != today:
            send_count_today = 0
        
        # Maximum 2 emails per day
        if send_count_today >= 2:
            logger.info(f"Already sent {send_count_today} times today for {user.email}, skipping")
            return False

        # Only prepare data if we're actually sending
        has_reconnect = reconnect_contacts.exists()
        has_events = upcoming_events.exists()
        
        if not has_reconnect and not has_events:
            logger.info(f"No content for {user.email}, skipping")
            return False

        # Get user's name
        user_name = getattr(user, 'full_name', None) or getattr(user, 'first_name', '') or user.email.split('@')[0]

        # Determine which reminder this is (morning or evening)
        current_hour = datetime.now().hour
        greeting = "Good morning" if current_hour < 12 else "Good afternoon" if current_hour < 17 else "Good evening"
        reminder_type = "Morning" if current_hour < 12 else "Evening"

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

        # Plain text version
        text_message = f"""
{greeting} {user_name},

Here is your {reminder_type.lower()} reminder for {today.strftime('%B %d, %Y')}:

{f"🔔 Contacts to Reconnect ({len(reconnect_list)}):" if reconnect_list else ""}
{chr(10).join([f'- {c["name"]} ({c["days_since"]})' for c in reconnect_list]) if reconnect_list else "None"}

{f"📅 Upcoming Events ({len(event_list)}):" if event_list else ""}
{chr(10).join([f'- {e["title"]} on {e["date"]} ({e["days_until"]})' + (f' with {e["contact_name"]}' if e["contact_name"] else '') for e in event_list]) if event_list else "None"}

{f"View your dashboard: {settings.FRONTEND_URL}/dashboard" if hasattr(settings, 'FRONTEND_URL') else "Login to view your dashboard"}

Best regards,
Circo Team
"""
        
        # Try HTML email
        try:
            html_message = render_to_string('account/emails/dashboard_reminder.html', {
                'user_name': user_name,
                'greeting': greeting,
                'reminder_type': reminder_type,
                'reconnect_list': reconnect_list,
                'event_list': event_list,
                'has_reconnect': has_reconnect,
                'has_events': has_events,
                'today': today,
                'dashboard_url': f"{settings.FRONTEND_URL}/dashboard" if hasattr(settings, 'FRONTEND_URL') else None,
            })
            
            email = EmailMultiAlternatives(
                subject=f"🌅 {reminder_type} Circo Reminder - {today.strftime('%B %d')}",
                body=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_message, "text/html")
            email.send(fail_silently=False)
            
        except Exception as template_error:
            # Fallback to simple email
            logger.warning(f"HTML template failed for {user.email}, sending plain text")
            from django.core.mail import send_mail
            
            send_mail(
                subject=f"{reminder_type} Circo Reminder - {today.strftime('%B %d')}",
                message=text_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user.email],
                fail_silently=True
            )

        # Update tracking fields
        if hasattr(user, "last_dashboard_email_sent"):
            try:
                with transaction.atomic():
                    User = type(user)
                    update_fields = {
                        'last_dashboard_email_sent': today,
                        'dashboard_email_count_today': send_count_today + 1
                    }
                    User.objects.filter(pk=user.pk).update(**update_fields)
                    
            except Exception as db_error:
                logger.error(f"Failed to update tracking for {user.email}: {str(db_error)}")

        logger.info(f"Dashboard email #{send_count_today + 1} sent to {user.email}")
        return True

    except Exception as e:
        logger.error(f"Failed to send email to {user.email}: {str(e)}", exc_info=True)
        return False