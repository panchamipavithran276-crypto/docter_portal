from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from main_app import views as main_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("main_app.urls")),
    path("accounts/", include("accounts.urls")),
    path('stress-analysis/', include('stress_analysis.urls')),
    path("", include("chats.urls")),
    
    # Temporary login URL fix
    path('accounts/login/', main_views.patient_ui, name='login_fallback'),
]