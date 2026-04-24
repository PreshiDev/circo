from django.urls import path
from .views import (
    RegisterView, LoginView, register_page, login_page, 
    DashboardAPIView, dashboard_view, CreateContactAPIView, 
    RecordInteractionAPIView, ProfileView, UpdateProfileView, 
    ChangePasswordView, LogoutView, CreateEventAPIView, PaginatedReconnectAPIView,
    PaginatedEventsAPIView, PaginatedRecentContactsAPIView, PaginatedAlumniAPIView,
    ContactDetailAPIView, BulkImportContactsAPIView, InteractionDetailAPIView
)

app_name = "account"

urlpatterns = [
    # API endpoints (under /api/auth/)
    path('auth/register/', RegisterView.as_view(), name='api_register'),
    path('auth/login/', LoginView.as_view(), name='api_login'),
    path('auth/profile/', ProfileView.as_view(), name='api_profile'),
    path('auth/profile/update/', UpdateProfileView.as_view(), name='api_update_profile'),
    path('auth/profile/change-password/', ChangePasswordView.as_view(), name='api_change_password'),
    path('auth/logout/', LogoutView.as_view(), name='api_logout'),
    path('auth/dashboard/', DashboardAPIView.as_view(), name='api_dashboard'),
    path('auth/contacts/create/', CreateContactAPIView.as_view(), name='api_create_contact'),
    path('api/contacts/bulk-import/', BulkImportContactsAPIView.as_view(), name='api_bulk_import_contacts'),
    path('api/create-event/', CreateEventAPIView.as_view(), name='api_create_event'),
    # Interaction endpoints
    path('api/contact/<int:contact_id>/interaction/', 
         RecordInteractionAPIView.as_view(), 
         name='api_record_interaction'),
    
    path('api/contact/<int:contact_id>/interactions/', 
         RecordInteractionAPIView.as_view(), 
         name='api_contact_interactions'),
    
    path('api/interaction/<int:interaction_id>/', 
         InteractionDetailAPIView.as_view(), 
         name='api_interaction_detail'),
    path('api/paginated/reconnect/', PaginatedReconnectAPIView.as_view(), name='api_paginated_reconnect'),
    path('api/paginated/events/', PaginatedEventsAPIView.as_view(), name='api_paginated_events'),
    path('api/paginated/recent-contacts/', PaginatedRecentContactsAPIView.as_view(), name='api_paginated_recent_contacts'),
    path('api/paginated/alumni/', PaginatedAlumniAPIView.as_view(), name='api_paginated_alumni'),
    path('api/contact/<int:contact_id>/', ContactDetailAPIView.as_view(), name='api_contact_detail'),
    
    # Template pages (at root level)
    path('register/', register_page, name='register'),
    path('login/', login_page, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('logout/', LogoutView.as_view(), name='logout'),
]