from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", include("main_app.urls")),
    path("accounts/", include("accounts.urls")),
    path('stress-analysis/', include('stress_analysis.urls')),
    path("", include("chats.urls")),
    
    # Add fallback URLs for common patterns
    path('accounts/sign_in_patient/', RedirectView.as_view(url='/accounts/sign_in_patient', permanent=False)),
    path('accounts/sign_in_doctor/', RedirectView.as_view(url='/accounts/sign_in_doctor', permanent=False)),
    path('accounts/signup_patient/', RedirectView.as_view(url='/accounts/signup_patient', permanent=False)),
    path('accounts/signup_doctor/', RedirectView.as_view(url='/accounts/signup_doctor', permanent=False)),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)