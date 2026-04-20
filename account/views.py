import os
from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.response import Response
from .serializers import RegisterSerializer, LoginSerializer
from django.contrib.auth import login
from django.utils import timezone
from rest_framework.views import APIView


def home_view(request):
    return render(request, "account/index.html")

def register_page(request):
    return render(request, "account/register.html")

def login_page(request):
    return render(request, "account/login.html")


ALUMNI_KEYWORDS = [
    "university",
    "polytechnic",
    "college of education",
    "college",
    "secondary school",
    "high school",
    "school",
    "academy",
    "institute"
]


def detect_alumni(text):
    if not text:
        return False, None

    text = text.lower()

    universities = ["university", "polytechnic", "college of education", "college", "school"]

    for uni in universities:
        if uni in text:
            return True, uni.title()

    return False, None



class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        return Response({
            "message": "User registered successfully",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name
            }
        }, status=status.HTTP_201_CREATED)
    



# ✅ API LOGIN
class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data

        user.last_seen = timezone.now()
        user.save()

        login(request, user)

        return Response({
            "message": "Login successful",
            "user": {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name
            }
        }, status=status.HTTP_200_OK)

    

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db.models import Q
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta

from .models import Contact, Event


# =========================
# 🔥 API DASHBOARD VIEW
# =========================
# views.py - Updated DashboardAPIView

class DashboardAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()
        cutoff = today - timedelta(days=90)

        # 🔔 RECONNECT - No interaction for 90+ days
        reconnect_contacts = Contact.objects.filter(
            user=user
        ).filter(
            Q(last_interaction__lt=cutoff) | Q(last_interaction__isnull=True)
        ).order_by('last_interaction')

        # 🎂 UPCOMING EVENTS - Fixed to show events by date proximity
        next_week = today + timedelta(days=7)
        next_month = today + timedelta(days=30)  # Extended range for better visibility
        
        upcoming_events = Event.objects.filter(
            user=user,
            date__gte=today  # Only future events
        ).select_related('contact').order_by('date')[:10]  # Order by closest date

        # 📍 RECENT CONTACTS
        recent_contacts = Contact.objects.filter(
            user=user
        ).order_by('-created_at')[:10]

        # 🎓 ALUMNI with interaction status
        alumni_contacts = Contact.objects.filter(
            user=user, 
            is_alumni=True
        ).order_by('name')

        # Format alumni data with interaction status
        alumni_data = []
        for contact in alumni_contacts:
            alumni_data.append({
                "id": contact.id,
                "name": contact.name,
                "type": contact.alumni_type or "Alumni",
                "has_interacted": contact.has_interacted_before(),
                "needs_reconnect": contact.needs_reconnect(),
                "last_interaction": contact.last_interaction,
                "interaction_count": contact.interaction_count
            })

        return Response({
            "reconnect": [
                {
                    "id": c.id,
                    "name": c.name,
                    "last_interaction": c.last_interaction,
                    "days_since_interaction": (
                        (today - c.last_interaction).days if c.last_interaction else None
                    )
                } for c in reconnect_contacts
            ],

            "upcoming_events": [
                {
                    "id": e.id,
                    "contact_id": e.contact.id,
                    "contact": e.contact.name,
                    "title": e.title,
                    "date": e.date,
                    "days_until": (e.date - today).days,
                    "event_type": e.event_type
                } for e in upcoming_events
            ],

            "recent_contacts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "last_interaction": c.last_interaction,
                    "created_at": c.created_at
                } for c in recent_contacts
            ],

            "alumni": alumni_data
        })

# =========================
# 🧠 TEMPLATE DASHBOARD VIEW
# =========================
# views.py - Updated dashboard_view

# views.py - Updated dashboard_view

@login_required
def dashboard_view(request):
    user = request.user
    today = timezone.now().date()
    cutoff = today - timedelta(days=90)

    # Reconnect contacts (90+ days no interaction)
    reconnect_contacts = Contact.objects.filter(
        user=user
    ).filter(
        Q(last_interaction__lt=cutoff) | Q(last_interaction__isnull=True)
    ).order_by('last_interaction')

    # Upcoming events - ALL future events ordered by date
    upcoming_events = Event.objects.filter(
        user=user,
        date__gte=today
    ).select_related('contact').order_by('date')[:5]  # Show closest 5 events

    # Recent contacts
    recent_contacts = Contact.objects.filter(
        user=user
    ).order_by('-created_at')[:10]

    # Alumni contacts
    alumni_contacts = Contact.objects.filter(
        user=user, 
        is_alumni=True
    ).order_by('name')
    
    # All contacts for event creation dropdown
    all_contacts = Contact.objects.filter(
        user=user
    ).order_by('name')

    return render(request, "account/dashboard.html", {
        "user": user,
        "reconnect_contacts": reconnect_contacts,
        "upcoming_events": upcoming_events,
        "recent_contacts": recent_contacts,
        "alumni_contacts": alumni_contacts,
        "all_contacts": all_contacts,  # For event creation
        "today": today,
    })


from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from rest_framework import status

from .models import Contact, Event


class CreateContactAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        name = request.data.get("name")
        phone_number = request.data.get("phone_number")
        email = request.data.get("email")
        notes = request.data.get("notes")
        meeting_context = request.data.get("meeting_context")

        # Validation
        if not name or not phone_number:
            return Response(
                {"error": "Name and phone number are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Alumni detection
        is_alumni, alumni_type = detect_alumni(meeting_context)

        # Create contact only - NO automatic event creation
        contact = Contact.objects.create(
            user=user,
            name=name,
            phone_number=phone_number,
            email=email,
            notes=notes,
            is_alumni=is_alumni,
            alumni_type=alumni_type
        )

        # Optional: Store meeting context in notes if provided
        if meeting_context and notes:
            contact.notes = f"{notes}\n\nInitial meeting context: {meeting_context}"
            contact.save()
        elif meeting_context:
            contact.notes = f"Initial meeting context: {meeting_context}"
            contact.save()

        return Response({
            "message": "Contact added successfully",
            "contact": {
                "id": contact.id, 
                "name": contact.name,
                "phone_number": contact.phone_number,
                "email": contact.email
            },
            "alumni_detected": is_alumni,
            "alumni_type": alumni_type
        }, status=status.HTTP_201_CREATED)
    


# Bulk Contact API View
class BulkImportContactsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        contacts_data = request.data.get("contacts", [])
        
        if not contacts_data:
            return Response(
                {"error": "No contacts provided"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        imported_count = 0
        skipped_count = 0
        errors = []
        
        for contact_data in contacts_data:
            name = contact_data.get("name")
            phone_number = contact_data.get("phone_number")
            email = contact_data.get("email", "")
            notes = contact_data.get("notes", "")
            meeting_context = contact_data.get("meeting_context", "")
            
            if not name or not phone_number:
                skipped_count += 1
                continue
            
            # Check if contact already exists
            existing = Contact.objects.filter(
                user=user, 
                phone_number=phone_number
            ).first()
            
            if existing:
                skipped_count += 1
                continue
            
            # Alumni detection
            is_alumni, alumni_type = detect_alumni(meeting_context)
            
            try:
                contact = Contact.objects.create(
                    user=user,
                    name=name,
                    phone_number=phone_number,
                    email=email,
                    notes=f"{notes}\n\nInitial meeting context: {meeting_context}" if meeting_context else notes,
                    is_alumni=is_alumni,
                    alumni_type=alumni_type
                )
                imported_count += 1
            except Exception as e:
                errors.append(str(e))
        
        return Response({
            "message": f"Imported {imported_count} contacts",
            "imported_count": imported_count,
            "skipped_count": skipped_count,
            "errors": errors
        }, status=status.HTTP_201_CREATED)
    
    

# event creation API

class CreateEventAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        contact_id = request.data.get('contact_id')
        title = request.data.get('title')
        event_type = request.data.get('event_type', 'custom')
        date = request.data.get('date')
        reminder_days = request.data.get('reminder_days_before', 1)

        # Validation
        if not all([contact_id, title, date]):
            return Response(
                {"error": "Contact, title, and date are required"}, 
                status=400
            )

        try:
            contact = Contact.objects.get(id=contact_id, user=user)
        except Contact.DoesNotExist:
            return Response(
                {"error": "Contact not found"}, 
                status=404
            )

        # Create event
        event = Event.objects.create(
            user=user,
            contact=contact,
            title=title,
            event_type=event_type,
            date=date,
            reminder_days_before=reminder_days
        )

        return Response({
            "message": "Event created successfully",
            "event": {
                "id": event.id,
                "title": event.title,
                "date": event.date,
                "contact_name": contact.name
            }
        }, status=201)


class RecordInteractionAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, contact_id):
        user = request.user

        try:
            contact = Contact.objects.get(id=contact_id, user=user)
        except Contact.DoesNotExist:
            return Response({"error": "Contact not found"}, status=404)

        contact.last_interaction = timezone.now().date()
        contact.save()

        return Response({
            "message": "Interaction recorded",
            "last_interaction": contact.last_interaction.strftime("%Y-%m-%d")
        })
    

# views.py
from rest_framework import generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.contrib.auth import logout
from django.utils import timezone
from .serializers import ProfileUpdateSerializer, PasswordChangeSerializer


class ProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user profile"""
        user = request.user
        return Response({
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "phone_number": user.phone_number,
            "date_joined": user.date_joined,
            "last_seen": user.last_seen,
            "profile_picture": user.profile_picture.url if user.profile_picture else None
        }, status=status.HTTP_200_OK)
    
    def put(self, request):
        """Update user profile"""
        serializer = ProfileUpdateSerializer(
            instance=request.user, 
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                "message": "Profile updated successfully",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "phone_number": user.phone_number
                }
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request):
        """Partially update user profile"""
        return self.put(request)


# updated profile api view
class UpdateProfileView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        
        if 'profile_picture' not in request.FILES:
            return Response(
                {"error": "No profile picture provided"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        profile_picture = request.FILES['profile_picture']
        
        # Validate file type
        allowed_types = ['image/jpeg', 'image/png', 'image/gif', 'image/webp']
        if profile_picture.content_type not in allowed_types:
            return Response(
                {"error": "Invalid file type. Please upload JPEG, PNG, GIF, or WebP."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate file size (5MB max)
        if profile_picture.size > 5 * 1024 * 1024:
            return Response(
                {"error": "File size too large. Maximum size is 5MB."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Delete old profile picture if exists
        if user.profile_picture:
            try:
                if os.path.isfile(user.profile_picture.path):
                    os.remove(user.profile_picture.path)
            except Exception as e:
                print(f"Error deleting old profile picture: {e}")
        
        # Save new profile picture
        user.profile_picture = profile_picture
        user.save()
        
        return Response({
            "message": "Profile picture updated successfully",
            "profile_picture": user.profile_picture.url
        }, status=status.HTTP_200_OK)



class ChangePasswordView(APIView):
    """Change user password"""
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        serializer = PasswordChangeSerializer(
            data=request.data,
            context={'request': request}
        )
        
        if serializer.is_valid():
            serializer.save()
            return Response({
                "message": "Password changed successfully"
            }, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# views.py
from django.shortcuts import redirect
from django.http import HttpResponseRedirect


class LogoutView(APIView):
    """Logout that handles both API and browser requests"""
    permission_classes = [AllowAny]
    
    def post(self, request):
        # Check if it's an API request (accepts JSON or has format=api in URL)
        is_api_request = (
            request.GET.get('format') == 'api' or
            request.headers.get('Accept') == 'application/json' or
            request.content_type == 'application/json'
        )
        
        if request.user.is_authenticated:
            user = request.user
            user.last_seen = timezone.now()
            user.save()
            logout(request)
            message = "Logged out successfully"
        else:
            message = "Already logged out"
        
        # Return JSON for API requests, redirect for browser requests
        if is_api_request:
            return Response({"message": message}, status=status.HTTP_200_OK)
        else:
            # Browser request - redirect to home page
            return redirect('/')  # or redirect('home')
    
    def get(self, request):
        """Handle GET requests (like from browser address bar)"""
        return self.post(request)
    

# views.py - Add these API views

class PaginatedReconnectAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()
        cutoff = today - timedelta(days=90)
        
        page = int(request.GET.get('page', 1))
        page_size = 10
        
        contacts = Contact.objects.filter(
            user=user
        ).filter(
            Q(last_interaction__lt=cutoff) | Q(last_interaction__isnull=True)
        ).order_by('last_interaction')
        
        total = contacts.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_contacts = contacts[start:end]
        
        return Response({
            "contacts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "last_interaction": c.last_interaction,
                    "days_since": (today - c.last_interaction).days if c.last_interaction else None,
                    "phone_number": c.phone_number,
                    "email": c.email
                } for c in paginated_contacts
            ],
            "total": total,
            "page": page,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": end < total,
            "has_previous": page > 1
        })


class PaginatedEventsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        page = int(request.GET.get('page', 1))
        page_size = 10
        filter_type = request.GET.get('filter', 'upcoming')  # upcoming, past, all
        
        events = Event.objects.filter(user=user).select_related('contact')
        
        if filter_type == 'upcoming':
            events = events.filter(date__gte=today)
        elif filter_type == 'past':
            events = events.filter(date__lt=today)
        
        events = events.order_by('date' if filter_type == 'upcoming' else '-date')
        
        total = events.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_events = events[start:end]
        
        return Response({
            "events": [
                {
                    "id": e.id,
                    "contact_id": e.contact.id,
                    "contact_name": e.contact.name,
                    "title": e.title,
                    "date": e.date,
                    "event_type": e.event_type,
                    "days_until": (e.date - today).days if e.date >= today else None,
                    "is_past": e.date < today
                } for e in paginated_events
            ],
            "total": total,
            "page": page,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": end < total,
            "has_previous": page > 1
        })


class PaginatedRecentContactsAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        
        page = int(request.GET.get('page', 1))
        page_size = 10
        
        contacts = Contact.objects.filter(user=user).order_by('-created_at')
        
        total = contacts.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_contacts = contacts[start:end]
        
        return Response({
            "contacts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "created_at": c.created_at,
                    "last_interaction": c.last_interaction,
                    "phone_number": c.phone_number,
                    "email": c.email,
                    "has_interacted": c.has_interacted_before()
                } for c in paginated_contacts
            ],
            "total": total,
            "page": page,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": end < total,
            "has_previous": page > 1
        })


class PaginatedAlumniAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        today = timezone.now().date()
        
        page = int(request.GET.get('page', 1))
        page_size = 10
        
        contacts = Contact.objects.filter(
            user=user, 
            is_alumni=True
        ).order_by('name')
        
        total = contacts.count()
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated_contacts = contacts[start:end]
        
        return Response({
            "contacts": [
                {
                    "id": c.id,
                    "name": c.name,
                    "alumni_type": c.alumni_type or "Alumni",
                    "has_interacted": c.has_interacted_before(),
                    "needs_reconnect": c.needs_reconnect(),
                    "last_interaction": c.last_interaction,
                    "interaction_count": c.interaction_count,
                    "phone_number": c.phone_number,
                    "email": c.email
                } for c in paginated_contacts
            ],
            "total": total,
            "page": page,
            "total_pages": (total + page_size - 1) // page_size,
            "has_next": end < total,
            "has_previous": page > 1
        })
    

# contact detail API view
# views.py - Debug version with print statements

class ContactDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, contact_id):
        user = request.user
        
        print(f"\n{'='*50}")
        print(f"DEBUG: Contact Detail API Called")
        print(f"User ID: {user.id}")
        print(f"User Email: {user.email}")
        print(f"Requested Contact ID: {contact_id}")
        print(f"{'='*50}\n")
        
        try:
            # First, check if contact exists at all (for debugging)
            all_contacts = Contact.objects.filter(user=user)
            print(f"Total contacts for user: {all_contacts.count()}")
            print(f"Available contact IDs: {list(all_contacts.values_list('id', flat=True))}")
            
            # Get the specific contact
            contact = Contact.objects.get(id=contact_id, user=user)
            print(f"\n✓ Found contact:")
            print(f"  - ID: {contact.id}")
            print(f"  - Name: {contact.name}")
            print(f"  - Phone: {contact.phone_number}")
            print(f"  - Email: {contact.email}")
            print(f"  - Is Alumni: {contact.is_alumni}")
            print(f"  - Created: {contact.created_at}")
            
        except Contact.DoesNotExist:
            print(f"\n✗ Contact {contact_id} NOT FOUND for user {user.id}")
            print(f"Make sure the contact belongs to this user!")
            return Response({"error": "Contact not found"}, status=404)
        
        # Get contact's events
        events = Event.objects.filter(
            user=user, 
            contact=contact
        ).order_by('-date')
        
        print(f"\n✓ Found {events.count()} events for this contact")
        for event in events:
            print(f"  - {event.title} on {event.date}")
        
        # Check if contact has interaction count
        interaction_count = getattr(contact, 'interaction_count', 0)
        print(f"\n✓ Interaction count: {interaction_count}")
        
        # Build response
        response_data = {
            "contact": {
                "id": contact.id,
                "name": contact.name,
                "phone_number": contact.phone_number,
                "email": contact.email or "",
                "notes": contact.notes or "",
                "last_interaction": contact.last_interaction,
                "is_alumni": contact.is_alumni,
                "alumni_type": contact.alumni_type or "",
                "created_at": contact.created_at,
                "has_interacted": contact.has_interacted_before(),
                "needs_reconnect": contact.needs_reconnect(),
                "interaction_count": interaction_count
            },
            "events": [
                {
                    "id": e.id,
                    "title": e.title,
                    "event_type": e.event_type,
                    "date": e.date,
                    "is_past": e.date < timezone.now().date()
                } for e in events
            ]
        }
        
        print(f"\n✓ Sending response data:")
        print(f"  Contact Name in response: {response_data['contact']['name']}")
        print(f"  Contact ID in response: {response_data['contact']['id']}")
        print(f"{'='*50}\n")
        
        return Response(response_data)