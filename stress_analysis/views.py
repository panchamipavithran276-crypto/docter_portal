from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
import os
from django.conf import settings

from .utils import get_google_fit_auth_url, get_google_fit_credentials, exchange_code_for_token, save_credentials_to_session
from .services import GoogleFitService, process_health_data

@login_required
def stress_dashboard(request):
    """Main stress analysis dashboard"""
    # Check if we have credentials in session
    credentials = get_google_fit_credentials(request)
    google_fit_connected = credentials is not None
    
    stress_data = []
    latest_report = None
    data_available = False
    
    if google_fit_connected:
        try:
            # Try to get real data
            end_time = timezone.now()
            start_time = end_time - timedelta(days=7)
            
            fit_service = GoogleFitService(credentials)
            
            # Fetch real data from Google Fit
            heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
            sleep_data = fit_service.get_sleep_data(start_time, end_time)
            step_data = fit_service.get_step_count(start_time, end_time)
            calories_data = fit_service.get_calories_data(start_time, end_time)
            
            # Check if we have any data
            if any([heart_rate_data, sleep_data, step_data, calories_data]):
                data_available = True
                # Process the data
                stress_data = process_health_data(heart_rate_data, sleep_data, step_data, calories_data)
                
                if stress_data:
                    stress_levels = [data['stress_level'] for data in stress_data]
                    latest_report = {
                        'average_stress': round(sum(stress_levels) / len(stress_levels), 1),
                        'max_stress': max(stress_levels),
                        'min_stress': min(stress_levels),
                        'data_points': len(stress_data)
                    }
            else:
                messages.info(request, "Connected to Google Fit but no health data found. Make sure you have Google Fit data in your account.")
                
        except Exception as e:
            messages.error(request, f"Error fetching Google Fit data: {str(e)}")
    
    context = {
        'stress_data': stress_data,
        'latest_report': latest_report,
        'google_fit_connected': google_fit_connected,
        'data_available': data_available,
    }
    
    return render(request, 'stress_analysis/dashboard.html', context)

@login_required
def connect_google_fit(request):
    """Initiate Google Fit OAuth connection"""
    try:
        auth_url = get_google_fit_auth_url(request)
        print(f"Redirecting to: {auth_url}")  # Debug
        return redirect(auth_url)
    except Exception as e:
        print(f"Error in connect_google_fit: {e}")  # Debug
        messages.error(request, f"Error connecting to Google Fit: {str(e)}")
        return redirect('stress_analysis:dashboard')

@login_required
def google_fit_callback(request):
    """Handle Google Fit OAuth callback"""
    try:
        print("Google Fit callback received")  # Debug
        print(f"GET params: {request.GET}")  # Debug
        
        if 'error' in request.GET:
            error_msg = request.GET.get('error', 'Unknown error')
            messages.error(request, f"Google Fit authorization failed: {error_msg}")
            return redirect('stress_analysis:dashboard')
        
        if 'code' not in request.GET:
            messages.error(request, "No authorization code received")
            return redirect('stress_analysis:dashboard')
        
        # Exchange authorization code for tokens
        authorization_response = request.build_absolute_uri()
        print(f"Authorization response: {authorization_response}")  # Debug
        
        credentials = exchange_code_for_token(request, authorization_response)
        
        # Save credentials to session
        save_credentials_to_session(request, credentials)
        
        messages.success(request, "Successfully connected to Google Fit! You can now sync your health data.")
        return redirect('stress_analysis:dashboard')
        
    except Exception as e:
        print(f"Error in google_fit_callback: {e}")  # Debug
        messages.error(request, f"Error during Google Fit callback: {str(e)}")
        return redirect('stress_analysis:dashboard')

@login_required
def disconnect_google_fit(request):
    """Disconnect Google Fit"""
    if 'google_fit_credentials' in request.session:
        del request.session['google_fit_credentials']
        messages.success(request, "Disconnected from Google Fit")
    else:
        messages.info(request, "Not connected to Google Fit")
    
    return redirect('stress_analysis:dashboard')

@login_required
def sync_google_fit_data(request):
    """Sync data from Google Fit - AJAX endpoint"""
    if request.method == 'POST':
        try:
            credentials = get_google_fit_credentials(request)
            if not credentials:
                return JsonResponse({'success': False, 'error': 'Google Fit not connected'}, status=400)
            
            # Get data for the last 7 days
            end_time = timezone.now()
            start_time = end_time - timedelta(days=7)
            
            fit_service = GoogleFitService(credentials)
            
            # Fetch all data
            heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
            sleep_data = fit_service.get_sleep_data(start_time, end_time)
            step_data = fit_service.get_step_count(start_time, end_time)
            calories_data = fit_service.get_calories_data(start_time, end_time)
            
            print(f"Data fetched - HR: {len(heart_rate_data)}, Sleep: {len(sleep_data)}, Steps: {len(step_data)}, Calories: {len(calories_data)}")  # Debug
            
            # Process data
            processed_data = process_health_data(heart_rate_data, sleep_data, step_data, calories_data)
            
            return JsonResponse({
                'success': True,
                'processed_records': len(processed_data),
                'message': f'Successfully synced {len(processed_data)} days of data',
                'data_available': {
                    'heart_rate': len(heart_rate_data) > 0,
                    'sleep': len(sleep_data) > 0,
                    'steps': len(step_data) > 0,
                    'calories': len(calories_data) > 0
                }
            })
            
        except Exception as e:
            print(f"Error in sync_google_fit_data: {e}")  # Debug
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)

@login_required
def get_stress_insights(request):
    """API endpoint for stress insights"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            # Return demo data if not connected
            return get_demo_insights()
        
        # Get real data
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        
        heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
        sleep_data = fit_service.get_sleep_data(start_time, end_time)
        step_data = fit_service.get_step_count(start_time, end_time)
        calories_data = fit_service.get_calories_data(start_time, end_time)
        
        processed_data = process_health_data(heart_rate_data, sleep_data, step_data, calories_data)
        
        if not processed_data:
            return get_demo_insights()
        
        # Prepare data for charts
        timestamps = [data['date'] for data in processed_data]
        stress_levels = [data['stress_level'] for data in processed_data]
        heart_rates = [data['heart_rate'] for data in processed_data]
        sleep_durations = [data['sleep_duration'] for data in processed_data]
        steps_data = [data['steps'] for data in processed_data]
        
        return JsonResponse({
            'timestamps': timestamps,
            'stress_levels': stress_levels,
            'heart_rates': heart_rates,
            'sleep_durations': sleep_durations,
            'steps_data': steps_data,
            'statistics': {
                'average_stress': round(sum(stress_levels) / len(stress_levels), 1),
                'max_stress': max(stress_levels),
                'min_stress': min(stress_levels),
                'data_points': len(processed_data)
            },
            'data_source': 'Google Fit',
            'has_real_data': True
        })
        
    except Exception as e:
        print(f"Error in get_stress_insights: {e}")  # Debug
        return JsonResponse({'error': str(e)}, status=500)

def get_demo_insights():
    """Fallback to demo data"""
    import random
    from datetime import datetime, timedelta
    
    timestamps = []
    stress_levels = []
    heart_rates = []
    sleep_durations = []
    steps_data = []
    
    for i in range(7):
        date = datetime.now() - timedelta(days=6-i)
        timestamps.append(date.strftime('%Y-%m-%d'))
        stress_levels.append(round(random.uniform(30, 70), 1))
        heart_rates.append(random.randint(65, 85))
        sleep_durations.append(round(random.uniform(5, 9), 1))
        steps_data.append(random.randint(5000, 12000))
    
    return JsonResponse({
        'timestamps': timestamps,
        'stress_levels': stress_levels,
        'heart_rates': heart_rates,
        'sleep_durations': sleep_durations,
        'steps_data': steps_data,
        'statistics': {
            'average_stress': round(sum(stress_levels) / len(stress_levels), 1),
            'max_stress': max(stress_levels),
            'min_stress': min(stress_levels),
            'data_points': len(stress_levels)
        },
        'data_source': 'demo',
        'has_real_data': False
    })