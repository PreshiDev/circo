from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from django.db.models import Q
from django.contrib.auth import get_user_model
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging
import time

from account.models import Contact, Event
from account.utils import send_dashboard_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Send daily dashboard reminder emails to users with concurrent processing"

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=50,
            help='Number of users per batch'
        )
        parser.add_argument(
            '--max-workers',
            type=int,
            default=5,
            help='Max concurrent threads'
        )
        parser.add_argument(
            '--user-ids',
            nargs='+',
            type=int,
            help='Specific user IDs to send to (for testing)'
        )

    def handle(self, *args, **options):
        User = get_user_model()
        today = timezone.now().date()
        cutoff = today - timedelta(days=90)
        
        batch_size = options['batch_size']
        max_workers = options['max_workers']
        user_ids = options.get('user_ids')

        # Get users
        if user_ids:
            users = User.objects.filter(id__in=user_ids, email__isnull=False)
            self.stdout.write(f"Sending to {len(user_ids)} specific users...")
        else:
            users = User.objects.filter(email__isnull=False).exclude(email='').exclude(
                last_dashboard_email_sent=today  # Skip users already sent today
            )
            self.stdout.write(f"Sending to all eligible users...")

        total_users = users.count()
        sent_count = 0
        skipped_count = 0
        error_count = 0
        start_time = time.time()

        # Process in batches
        for i in range(0, total_users, batch_size):
            batch = list(users[i:i + batch_size])
            
            with ThreadPoolExecutor(max_workers=min(max_workers, len(batch))) as executor:
                futures = {}
                for user in batch:
                    # Get user-specific data
                    reconnect_contacts = Contact.objects.filter(
                        user=user
                    ).filter(
                        Q(last_interaction__lt=cutoff) | Q(last_interaction__isnull=True)
                    ).order_by('last_interaction')

                    upcoming_events = Event.objects.filter(
                        user=user,
                        date__gte=today
                    ).select_related('contact').order_by('date')

                    future = executor.submit(
                        send_dashboard_email,
                        user,
                        reconnect_contacts,
                        upcoming_events,
                        today
                    )
                    futures[future] = user

                for future in as_completed(futures):
                    user = futures[future]
                    try:
                        result = future.result(timeout=30)  # 30 second timeout
                        if result:
                            sent_count += 1
                        else:
                            skipped_count += 1
                    except Exception as e:
                        error_count += 1
                        logger.error(f"Error for {user.email}: {str(e)}")

            self.stdout.write(
                f"Batch {i//batch_size + 1}: "
                f"Sent: {sent_count}, "
                f"Skipped: {skipped_count}, "
                f"Errors: {error_count}"
            )

            if i + batch_size < total_users:
                time.sleep(0.5)  # Brief pause between batches

        elapsed = time.time() - start_time
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Complete! "
                f"Sent: {sent_count}, "
                f"Skipped: {skipped_count}, "
                f"Errors: {error_count}, "
                f"Time: {elapsed:.1f}s"
            )
        )