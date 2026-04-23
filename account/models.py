from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin

# Custom User Manager
class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")

        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        return self.create_user(email, password, **extra_fields)


# Custom User Model
class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    school_attended = models.CharField(max_length=255, blank=True, null=True)
    profession = models.CharField(max_length=255, blank=True, null=True)

    # Optional but useful
    date_joined = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # App-specific fields
    profile_picture = models.ImageField(upload_to='profiles/', blank=True, null=True)
    last_seen = models.DateTimeField(blank=True, null=True)
    last_dashboard_email_sent = models.DateField(null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['full_name']

    def __str__(self):
        return self.email


# Updated Contact model with new fields
class Contact(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='contacts')
    name = models.CharField(max_length=255)
    phone_number = models.CharField(max_length=15)
    email = models.EmailField(blank=True, null=True)
    
    # New fields
    school = models.CharField(max_length=255, blank=True, null=True)
    meeting_context = models.CharField(max_length=255, blank=True, null=True)

    last_interaction = models.DateField(blank=True, null=True)
    interaction_count = models.IntegerField(default=0)
    notes = models.TextField(blank=True, null=True)

    # Alumni fields
    is_alumni = models.BooleanField(default=False)
    alumni_type = models.CharField(max_length=100, blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
    
    def needs_reconnect(self):
        """Check if contact needs reconnection (>90 days since last interaction)"""
        if not self.last_interaction:
            return True
        from datetime import date, timedelta
        return self.last_interaction < date.today() - timedelta(days=90)
    
    def has_interacted_before(self):
        """Check if user has ever interacted with this contact"""
        return self.interaction_count > 0
    

    

class Event(models.Model):
    EVENT_TYPE_CHOICES = (
        ('birthday', 'Birthday'),
        ('wedding', 'Wedding'),
        ('anniversary', 'Anniversary'),
        ('custom', 'Custom'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='events')

    title = models.CharField(max_length=255)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPE_CHOICES, default='custom')
    date = models.DateField()

    reminder_days_before = models.IntegerField(default=1)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.contact.name}"
    

# to track interaction history

class Interaction(models.Model):
    """Track interaction history between user and contacts"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    contact = models.ForeignKey(Contact, on_delete=models.CASCADE, related_name='interactions')
    interaction_date = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        ordering = ['-interaction_date']
    
    def __str__(self):
        return f"{self.user.email} - {self.contact.name} - {self.interaction_date.date()}"