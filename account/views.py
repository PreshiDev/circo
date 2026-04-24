import os
from django.shortcuts import render
from rest_framework import generics, status
from rest_framework.response import Response
from .serializers import RegisterSerializer, LoginSerializer
from django.contrib.auth import login
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import status
from .models import Contact, Event, User, Interaction
from django.db.models import Q
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from datetime import timedelta
from django.http import HttpResponseRedirect
from django.contrib.auth import logout
from .serializers import ProfileUpdateSerializer, PasswordChangeSerializer
from .utils import send_dashboard_email  # ✅ reuse shared logic
from .alumni_detector import detect_alumni, extract_school_name
from .alumni_detector import detect_alumni

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


# ✅ API REGISTER
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request, *args, **kwargs):
        print(f"[DEBUG] RegisterView.create called")
        print(f"[DEBUG] Request method: {request.method}")
        print(f"[DEBUG] Request path: {request.path}")
        print(f"[DEBUG] Request data: {request.data}")
        print(f"[DEBUG] Request headers: {dict(request.headers)}")
        
        serializer = self.get_serializer(data=request.data)
        print(f"[DEBUG] Serializer initialized: {serializer.__class__.__name__}")
        
        try:
            serializer.is_valid(raise_exception=True)
            print(f"[DEBUG] Serializer validation passed")
            print(f"[DEBUG] Validated data: {serializer.validated_data}")
            
            user = serializer.save()
            print(f"[DEBUG] User created - ID: {user.id}, Email: {user.email}, Name: {user.full_name}")
            
            # Generate profile picture URL if exists
            profile_picture_url = None
            if user.profile_picture:
                profile_picture_url = request.build_absolute_uri(user.profile_picture.url)

            response_data = {
                "message": "User registered successfully",
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "phone_number": user.phone_number,
                    "school_attended": user.school_attended,
                    "profession": user.profession,
                    "profile_picture": profile_picture_url
                }
            }
            print(f"[DEBUG] Returning response: {response_data}")
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            print(f"[DEBUG] Validation failed: {e}")
            print(f"[DEBUG] Serializer errors: {serializer.errors}")
            raise



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

        # 🎂 UPCOMING EVENTS - Ordered by closest date
        upcoming_events = Event.objects.filter(
            user=user,
            date__gte=today
        ).select_related('contact').order_by('date')[:10]

        # 📍 RECENT CONTACTS
        recent_contacts = Contact.objects.filter(
            user=user
        ).order_by('-created_at')[:10]

        # 🎓 ALUMNI - Auto-discover users with same school
        user_school = user.school_attended
        auto_alumni = []
        
        if user_school:
            # Find all users with the same school (excluding the current user)
            same_school_users = User.objects.filter(
                school_attended__iexact=user_school
            ).exclude(
                id=user.id
            ).values('id', 'full_name', 'email', 'phone_number', 'profession', 'profile_picture')
            
            for alumni_user in same_school_users:
                # Check if already saved as a contact
                existing_contact = Contact.objects.filter(
                    user=user,
                    email=alumni_user['email']
                ).first()
                
                alumni_entry = {
                    "id": alumni_user['id'],
                    "name": alumni_user['full_name'],
                    "email": alumni_user['email'],
                    "phone_number": alumni_user.get('phone_number', ''),
                    "profession": alumni_user.get('profession', ''),
                    "school": user_school,
                    "type": "Auto-discovered Alumni",
                    "is_contact": existing_contact is not None,
                    "contact_id": existing_contact.id if existing_contact else None,
                    "profile_picture": alumni_user.get('profile_picture'),
                    "has_interacted": existing_contact.has_interacted_before() if existing_contact else False,
                    "needs_reconnect": existing_contact.needs_reconnect() if existing_contact else False,
                    "last_interaction": existing_contact.last_interaction if existing_contact else None,
                    "interaction_count": existing_contact.interaction_count if existing_contact else 0
                }
                auto_alumni.append(alumni_entry)

        # 🎓 MANUAL ALUMNI CONTACTS
        manual_alumni = Contact.objects.filter(
            user=user,
            is_alumni=True
        ).order_by('name')

        manual_alumni_data = []
        for contact in manual_alumni:
            manual_alumni_data.append({
                "id": contact.id,
                "name": contact.name,
                "email": contact.email,
                "phone_number": contact.phone_number,
                "type": contact.alumni_type or "Alumni",
                "school": contact.school or user_school,
                "is_auto": False,
                "has_interacted": contact.has_interacted_before(),
                "needs_reconnect": contact.needs_reconnect(),
                "last_interaction": contact.last_interaction,
                "interaction_count": contact.interaction_count
            })

        # 👥 CONTACTS BY MEETING CONTEXT
        all_contacts = Contact.objects.filter(user=user)
        
        # Categorize by meeting context
        context_categories = {
            "wedding": [],
            "birthday": [],
            "conference": [],
            "coffee": [],
            "party": [],
            "work": [],
            "school": [],
            "networking": [],
            "other": []
        }
        
        for contact in all_contacts:
            context = (contact.meeting_context or "").lower()
            contact_data = {
                "id": contact.id,
                "name": contact.name,
                "email": contact.email,
                "phone_number": contact.phone_number,
                "meeting_context": contact.meeting_context,
                "school": contact.school,
                "created_at": contact.created_at,
                "last_interaction": contact.last_interaction,
                "interaction_count": contact.interaction_count
            }
            
            # Categorize based on keywords
            categorized = False
            for category in context_categories.keys():
                if category in context:
                    context_categories[category].append(contact_data)
                    categorized = True
                    break
            
            if not categorized:
                context_categories["other"].append(contact_data)
        
        # Remove empty categories
        context_categories = {k: v for k, v in context_categories.items() if v}

        # ✅ SEND EMAIL
        send_dashboard_email(user, reconnect_contacts, upcoming_events, today)

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
            "auto_alumni": auto_alumni,
            "manual_alumni": manual_alumni_data,
            "context_categories": context_categories,
            "user_school": user_school
        })


# =========================
# 🧠 TEMPLATE DASHBOARD VIEW
# =========================
# views.py - Updated dashboard_view
@login_required
def dashboard_view(request):
    user = request.user
    today = timezone.now().date()
    cutoff = today - timedelta(days=90)

    # Reconnect contacts
    reconnect_contacts = Contact.objects.filter(
        user=user
    ).filter(
        Q(last_interaction__lt=cutoff) | Q(last_interaction__isnull=True)
    ).order_by('last_interaction')

    # Upcoming events
    upcoming_events = Event.objects.filter(
        user=user,
        date__gte=today
    ).select_related('contact').order_by('date')[:5]

    # Recent contacts
    recent_contacts = Contact.objects.filter(
        user=user
    ).order_by('-created_at')[:10]

    # Auto-discovered alumni (same school as user)
    user_school = user.school_attended
    auto_alumni = []
    
    if user_school:
        same_school_users = User.objects.filter(
            school_attended__iexact=user_school
        ).exclude(id=user.id)
        
        for alumni_user in same_school_users[:3]:  # Show only 3 on main page
            existing_contact = Contact.objects.filter(
                user=user,
                email=alumni_user.email
            ).first()
            
            auto_alumni.append({
                'user': alumni_user,
                'is_contact': existing_contact is not None,
                'contact': existing_contact
            })

    # Manual alumni contacts - Group by school
    manual_alumni_contacts = Contact.objects.filter(
        user=user,
        is_alumni=True
    ).order_by('school', 'name')

    # Simple dict: key=school_name, value=list of contacts
    alumni_by_school = {}
    for contact in manual_alumni_contacts:
        school_name = contact.school or "Other Schools"
        if school_name not in alumni_by_school:
            alumni_by_school[school_name] = []
        alumni_by_school[school_name].append(contact)

    # All contacts for event form
    all_contacts = Contact.objects.filter(user=user).order_by('name')

    # Categorize contacts by meeting context (excluding alumni contacts)
    all_user_contacts = Contact.objects.filter(user=user)
    
    context_categories = {}
    for contact in all_user_contacts:
        if contact.is_alumni:
            continue
            
        context = (contact.meeting_context or "Other").strip()
        context_lower = context.lower()
        
        if any(word in context_lower for word in ['wedding', 'marriage', 'bride', 'groom']):
            category = '💒 Weddings'
        elif any(word in context_lower for word in ['birthday', 'bday', 'born day']):
            category = '🎂 Birthdays'
        elif any(word in context_lower for word in ['conference', 'summit', 'meetup', 'tech']):
            category = '🏢 Conferences'
        elif any(word in context_lower for word in ['coffee', 'cafe', 'tea', 'lunch', 'dinner', 'restaurant']):
            category = '☕ Coffee & Dining'
        elif any(word in context_lower for word in ['party', 'celebration', 'club', 'bar', 'night']):
            category = '🎉 Parties & Social'
        elif any(word in context_lower for word in ['work', 'office', 'colleague', 'coworker']):
            category = '💼 Work'
        elif any(word in context_lower for word in ['networking', 'business', 'professional']):
            category = '🤝 Networking'
        elif any(word in context_lower for word in ['gym', 'fitness', 'sport', 'game', 'match']):
            category = '⚽ Sports & Fitness'
        elif any(word in context_lower for word in ['travel', 'trip', 'vacation', 'holiday']):
            category = '✈️ Travel'
        elif any(word in context_lower for word in ['church', 'mosque', 'temple', 'religious', 'worship']):
            category = '⛪ Religious'
        else:
            category = '📍 Other Places'
        
        if category not in context_categories:
            context_categories[category] = []
        context_categories[category].append(contact)

    send_dashboard_email(user, reconnect_contacts, upcoming_events, today)

    return render(request, "account/dashboard.html", {
        "user": user,
        "reconnect_contacts": reconnect_contacts,
        "upcoming_events": upcoming_events,
        "recent_contacts": recent_contacts,
        "auto_alumni": auto_alumni,
        "alumni_by_school": alumni_by_school,  # Simple dict: {school_name: [contact_list]}
        "all_contacts": all_contacts,
        "context_categories": context_categories,
        "user_school": user_school,
        "today": today,
    })



class CreateContactAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        
        name = request.data.get('name')
        phone_number = request.data.get('phone_number')
        email = request.data.get('email', '')
        notes = request.data.get('notes', '')
        meeting_context = request.data.get('meeting_context', '')
        
        if not name or not phone_number:
            return Response(
                {"error": "Name and phone number are required"}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # ✅ SAFETY: Use try/except and unpack safely
        try:
            result = detect_alumni(meeting_context)
            if len(result) == 3:
                is_alumni, alumni_type, detected_school = result
            elif len(result) == 2:
                is_alumni, alumni_type = result
                detected_school = None
            else:
                is_alumni, alumni_type, detected_school = False, None, None
        except Exception as e:
            print(f"[ERROR] detect_alumni failed: {e}")
            is_alumni, alumni_type, detected_school = False, None, None
        
        # Use detected school name, or keep the meeting context as school if no specific name found
        school_name = detected_school or (meeting_context if is_alumni else '')
        
        contact = Contact.objects.create(
            user=user,
            name=name,
            phone_number=phone_number,
            email=email,
            notes=notes,
            school=school_name,
            meeting_context=meeting_context,
            is_alumni=is_alumni,
            alumni_type=alumni_type
        )
        
        return Response({
            "message": "Contact created successfully",
            "contact": {
                "id": contact.id,
                "name": contact.name,
                "phone_number": contact.phone_number,
                "email": contact.email,
                "school": contact.school,
                "meeting_context": contact.meeting_context,
                "is_alumni": contact.is_alumni,
                "alumni_type": contact.alumni_type
            }
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
            
            # Auto-detect alumni from meeting context
            is_alumni, alumni_type, detected_school = detect_alumni(meeting_context)
            school_name = detected_school or (meeting_context if is_alumni else '')
            
            try:
                contact = Contact.objects.create(
                    user=user,
                    name=name,
                    phone_number=phone_number,
                    email=email,
                    notes=notes,
                    school=school_name,
                    meeting_context=meeting_context,
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
        """Record a new interaction"""
        user = request.user

        try:
            contact = Contact.objects.get(id=contact_id, user=user)
        except Contact.DoesNotExist:
            return Response({"error": "Contact not found"}, status=404)

        # Get interaction details from request
        interaction_type = request.data.get('interaction_type', 'physical_meetup')
        discussion_summary = request.data.get('discussion_summary', '')
        action_items = request.data.get('action_items', '')
        location = request.data.get('location', '')
        duration_minutes = request.data.get('duration_minutes')
        notes = request.data.get('notes', '')

        # Validate interaction type
        valid_types = [choice[0] for choice in Interaction.INTERACTION_TYPES]
        if interaction_type not in valid_types:
            return Response(
                {"error": f"Invalid interaction type. Must be one of: {', '.join(valid_types)}"}, 
                status=400
            )

        # Create interaction record
        interaction = Interaction.objects.create(
            user=user,
            contact=contact,
            interaction_type=interaction_type,
            discussion_summary=discussion_summary,
            action_items=action_items,
            location=location,
            duration_minutes=duration_minutes if duration_minutes else None,
            notes=notes
        )

        # Update contact's last interaction date
        contact.last_interaction = timezone.now().date()
        contact.save()

        return Response({
            "message": "Interaction recorded successfully",
            "last_interaction": contact.last_interaction.strftime("%Y-%m-%d"),
            "interaction_id": interaction.id,
            "interaction_type": interaction.get_interaction_type_display(),
            "interaction_data": {
                'id': interaction.id,
                'interaction_type': interaction.interaction_type,
                'interaction_type_display': interaction.get_interaction_type_display(),
                'interaction_type_emoji': interaction.interaction_type_display_emoji,
                'discussion_summary': interaction.discussion_summary,
                'action_items': interaction.action_items,
                'location': interaction.location,
                'duration_minutes': interaction.duration_minutes,
                'notes': interaction.notes,
                'interaction_date': interaction.interaction_date.strftime("%Y-%m-%d %H:%M"),
                'interaction_date_formatted': interaction.interaction_date.strftime("%B %d, %Y at %I:%M %p"),
            }
        }, status=201)

    def get(self, request, contact_id):
        """Get interaction history for a contact"""
        user = request.user

        try:
            contact = Contact.objects.get(id=contact_id, user=user)
        except Contact.DoesNotExist:
            return Response({"error": "Contact not found"}, status=404)

        # Get pagination parameters
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 10))
        
        interactions = Interaction.objects.filter(
            user=user, 
            contact=contact
        ).order_by('-interaction_date')

        # Calculate pagination
        total_interactions = interactions.count()
        total_pages = (total_interactions + per_page - 1) // per_page
        start = (page - 1) * per_page
        end = start + per_page
        
        paginated_interactions = interactions[start:end]
        
        interaction_data = []
        for interaction in paginated_interactions:
            interaction_data.append({
                'id': interaction.id,
                'interaction_type': interaction.interaction_type,
                'interaction_type_display': interaction.get_interaction_type_display(),
                'interaction_type_emoji': interaction.interaction_type_display_emoji,
                'discussion_summary': interaction.discussion_summary,
                'action_items': interaction.action_items,
                'location': interaction.location,
                'duration_minutes': interaction.duration_minutes,
                'notes': interaction.notes,
                'interaction_date': interaction.interaction_date.strftime("%Y-%m-%d %H:%M"),
                'interaction_date_formatted': interaction.interaction_date.strftime("%B %d, %Y at %I:%M %p"),
                'interaction_date_relative': self.get_relative_time(interaction.interaction_date),
            })

        return Response({
            'contact_id': contact_id,
            'contact_name': contact.name,
            'interactions': interaction_data,
            'total_interactions': total_interactions,
            'page': page,
            'per_page': per_page,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_previous': page > 1
        })
    
    def get_relative_time(self, date):
        """Return relative time string"""
        now = timezone.now()
        diff = now - date
        
        if diff.days > 365:
            years = diff.days // 365
            return f"{years} year{'s' if years > 1 else ''} ago"
        elif diff.days > 30:
            months = diff.days // 30
            return f"{months} month{'s' if months > 1 else ''} ago"
        elif diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif diff.seconds > 60:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"




class InteractionDetailAPIView(APIView):
    """Get, update, or delete a specific interaction"""
    permission_classes = [IsAuthenticated]

    def get(self, request, interaction_id):
        """Get single interaction details"""
        try:
            interaction = Interaction.objects.get(id=interaction_id, user=request.user)
        except Interaction.DoesNotExist:
            return Response({"error": "Interaction not found"}, status=404)

        return Response({
            'id': interaction.id,
            'contact_id': interaction.contact.id,
            'contact_name': interaction.contact.name,
            'interaction_type': interaction.interaction_type,
            'interaction_type_display': interaction.get_interaction_type_display(),
            'interaction_type_emoji': interaction.interaction_type_display_emoji,
            'discussion_summary': interaction.discussion_summary,
            'action_items': interaction.action_items,
            'location': interaction.location,
            'duration_minutes': interaction.duration_minutes,
            'notes': interaction.notes,
            'interaction_date': interaction.interaction_date.strftime("%Y-%m-%d %H:%M"),
            'interaction_date_formatted': interaction.interaction_date.strftime("%B %d, %Y at %I:%M %p"),
        })

    def put(self, request, interaction_id):
        """Update an interaction"""
        try:
            interaction = Interaction.objects.get(id=interaction_id, user=request.user)
        except Interaction.DoesNotExist:
            return Response({"error": "Interaction not found"}, status=404)

        # Update fields if provided
        if 'interaction_type' in request.data:
            valid_types = [choice[0] for choice in Interaction.INTERACTION_TYPES]
            if request.data['interaction_type'] not in valid_types:
                return Response(
                    {"error": f"Invalid interaction type"}, 
                    status=400
                )
            interaction.interaction_type = request.data['interaction_type']
        
        if 'discussion_summary' in request.data:
            interaction.discussion_summary = request.data['discussion_summary']
        
        if 'action_items' in request.data:
            interaction.action_items = request.data['action_items']
        
        if 'location' in request.data:
            interaction.location = request.data['location']
        
        if 'duration_minutes' in request.data:
            interaction.duration_minutes = request.data['duration_minutes']
        
        if 'notes' in request.data:
            interaction.notes = request.data['notes']
        
        interaction.save()

        return Response({
            "message": "Interaction updated successfully",
            "interaction": {
                'id': interaction.id,
                'interaction_type': interaction.interaction_type,
                'interaction_type_display': interaction.get_interaction_type_display(),
                'interaction_type_emoji': interaction.interaction_type_display_emoji,
                'discussion_summary': interaction.discussion_summary,
                'action_items': interaction.action_items,
                'location': interaction.location,
                'duration_minutes': interaction.duration_minutes,
                'notes': interaction.notes,
                'interaction_date': interaction.interaction_date.strftime("%Y-%m-%d %H:%M"),
            }
        })

    def delete(self, request, interaction_id):
        """Delete an interaction"""
        try:
            interaction = Interaction.objects.get(id=interaction_id, user=request.user)
        except Interaction.DoesNotExist:
            return Response({"error": "Interaction not found"}, status=404)

        interaction.delete()
        return Response({"message": "Interaction deleted successfully"}, status=200)




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
        """Handle profile picture upload"""
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
    
    def put(self, request):
        """Handle profile info update (name, email, phone, school, profession)"""
        user = request.user
        
        # Get fields from request
        full_name = request.data.get('full_name', user.full_name)
        email = request.data.get('email', user.email)
        phone_number = request.data.get('phone_number', user.phone_number)
        school_attended = request.data.get('school_attended', user.school_attended)
        profession = request.data.get('profession', user.profession)
        
        # Update user fields
        user.full_name = full_name
        user.email = email
        user.phone_number = phone_number
        user.school_attended = school_attended
        user.profession = profession
        user.save()
        
        return Response({
            "message": "Profile updated successfully",
            "user": {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "phone_number": user.phone_number,
                "school_attended": user.school_attended,
                "profession": user.profession
            }
        }, status=status.HTTP_200_OK)
    
    def patch(self, request):
        """Handle partial profile updates (same as PUT)"""
        return self.put(request)



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
        
        try:
            # First, check if contact exists at all (for debugging)
            all_contacts = Contact.objects.filter(user=user)
            
            # Get the specific contact
            contact = Contact.objects.get(id=contact_id, user=user)
            
        except Contact.DoesNotExist:
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
        
        
        return Response(response_data)
