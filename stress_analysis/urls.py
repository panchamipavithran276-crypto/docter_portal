from django.urls import path
from . import views

app_name = 'stress_analysis'

urlpatterns = [
    path('dashboard/', views.stress_dashboard, name='dashboard'),
    path('connect-google-fit/', views.connect_google_fit, name='connect_google_fit'),
    path('google-fit-callback/', views.google_fit_callback, name='google_fit_callback'),
    path('disconnect-google-fit/', views.disconnect_google_fit, name='disconnect_google_fit'),
    path('sync-data/', views.sync_google_fit_data, name='sync_data'),
    path('api/insights/', views.get_stress_insights, name='api_insights'),
    path('api/analysis/', views.stress_analysis_api, name='api_analysis'),
]