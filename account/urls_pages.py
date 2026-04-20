from django.urls import path
from .views import register_page, login_page, dashboard_view, LogoutView

app_name = "account_pages"

urlpatterns = [
    path('register/', register_page, name='register'),
    path('login/', login_page, name='login'),
    path('dashboard/', dashboard_view, name='dashboard'),
    path('logout/', LogoutView.as_view(), name='logout'),
]