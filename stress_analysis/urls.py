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
    path('api/stress-chart/', views.api_stress_chart, name='api_stress_chart'),
    path('api/heart-rate-chart/', views.api_heart_rate_chart, name='api_heart_rate_chart'),
    path('api/sleep-chart/', views.api_sleep_chart, name='api_sleep_chart'),
    path('api/steps-chart/', views.api_steps_chart, name='api_steps_chart'),
    path('api/calories-chart/', views.api_calories_chart, name='api_calories_chart'),
    path('api/correlation-chart/', views.api_correlation_chart, name='api_correlation_chart'),
    path('api/pattern-chart/', views.api_pattern_chart, name='api_pattern_chart'),
    
]