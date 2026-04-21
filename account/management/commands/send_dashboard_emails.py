from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.contrib.auth import get_user_model

from account.models import Contact, Event
from account.utils import send_dashboard_email


class Command(BaseCommand):
    help = "Send daily dashboard reminder emails to users"

    def handle(self, *args, **kwargs):
        User = get_user_model()
        today = timezone.now().date()
        cutoff = today - timedelta(days=90)

        users = User.objects.all()

        sent_count = 0

        for user in users:
            if not user.email:
                continue

            # 🔔 Reconnect contacts
            reconnect_contacts = Contact.objects.filter(
                user=user
            ).filter(
                Q(last_interaction__lt=cutoff) | Q(last_interaction__isnull=True)
            ).order_by('last_interaction')

            # 📅 Upcoming events
            upcoming_events = Event.objects.filter(
                user=user,
                date__gte=today
            ).select_related('contact').order_by('date')

            # ✅ Send email (uses your shared logic)
            send_dashboard_email(
                user,
                reconnect_contacts,
                upcoming_events,
                today
            )

            sent_count += 1

        self.stdout.write(
            self.style.SUCCESS(f"Emails processed for {sent_count} users")
        )