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


@login_required(login_url='/accounts/sign_in_patient')
def stress_dashboard(request):
    """Main stress analysis dashboard"""
    # Check if we have credentials in session
    credentials = get_google_fit_credentials(request)
    google_fit_connected = credentials is not None
    
    stress_data = []
    latest_report = None
    debug_info = {}
    
    # Data status tracking
    has_sufficient_data = False
    show_demo_warning = False
    real_data_days = 0
    total_days = 7
    data_status = {
        'heart_rate': 'missing',
        'sleep': 'missing', 
        'activity': 'missing',
        'steps_count': 0
    }

    if google_fit_connected:
        try:
            # Get data for the last 30 days to increase chances of finding data
            end_time = timezone.now()
            start_time = end_time - timedelta(days=30)
            
            fit_service = GoogleFitService(credentials)
            
            # Fetch real data from Google Fit
            print("=== FETCHING GOOGLE FIT DATA ===")
            heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
            sleep_data = fit_service.get_sleep_data(start_time, end_time)
            step_data = fit_service.get_step_count(start_time, end_time)
            calories_data = fit_service.get_calories_data(start_time, end_time)
            
            debug_info = {
                'heart_rate_points': len(heart_rate_data),
                'sleep_sessions': len(sleep_data),
                'step_points': len(step_data),
                'calories_points': len(calories_data),
                'time_range': f"{start_time.date()} to {end_time.date()}"
            }
            
            # Update data status
            data_status['heart_rate'] = 'available' if len(heart_rate_data) > 10 else 'missing'
            data_status['sleep'] = 'available' if len(sleep_data) > 2 else 'missing'
            data_status['activity'] = 'available' if len(step_data) >= 5 else 'partial' if len(step_data) > 0 else 'missing'
            data_status['steps_count'] = len(step_data)
            
            # Process the data
            stress_data = process_health_data(heart_rate_data, sleep_data, step_data, calories_data)
            
            # Calculate real data metrics
            if stress_data:
                real_data_days = sum(1 for item in stress_data if item.get('has_real_data', False))
                total_days = len(stress_data)
                
                # Check if we have sufficient data for analysis
                has_real_hr = len(heart_rate_data) > 10
                has_real_sleep = len(sleep_data) > 2  
                has_real_activity = len(step_data) >= 5
                
                has_sufficient_data = (has_real_hr and has_real_sleep and has_real_activity) or real_data_days >= 3
                show_demo_warning = real_data_days > 0 and real_data_days < total_days
                
                if real_data_days > 0:
                    stress_levels = [data['stress_level'] for data in stress_data if data.get('has_real_data', False)]
                    
                    if stress_levels:
                        latest_report = {
                            'average_stress': round(sum(stress_levels) / len(stress_levels), 1),
                            'max_stress': max(stress_levels),
                            'min_stress': min(stress_levels),
                            'data_points': len(stress_levels)
                        }
                    
                    if real_data_days == 0:
                        messages.info(request, 
                            "Connected to Google Fit but no health data found for the last 30 days. "
                            "Make sure you have Google Fit data in your account from a connected device."
                        )
                else:
                    messages.info(request, 
                        "Connected to Google Fit but insufficient health data found. "
                        "We need heart rate, sleep, and activity data for meaningful analysis."
                    )
                
        except Exception as e:
            print(f"Error fetching Google Fit data: {str(e)}")
            messages.error(request, f"Error fetching Google Fit data: {str(e)}")
    
    context = {
        'stress_data': stress_data,
        'latest_report': latest_report,
        'google_fit_connected': google_fit_connected,
        'has_sufficient_data': has_sufficient_data,
        'show_demo_warning': show_demo_warning,
        'real_data_days': real_data_days,
        'total_days': total_days,
        'heart_rate_status': data_status['heart_rate'],
        'sleep_status': data_status['sleep'],
        'activity_status': data_status['activity'],
        'steps_count': data_status['steps_count'],
        'debug_info': debug_info,
    }
    
    return render(request, 'stress_analysis/dashboard.html', context)


@login_required(login_url='/accounts/sign_in_patient')
def connect_google_fit(request):
    """Initiate Google Fit OAuth connection"""
    try:
        auth_url = get_google_fit_auth_url(request)
        print(f"Redirecting to: {auth_url}")
        return redirect(auth_url)
    except Exception as e:
        print(f"Error in connect_google_fit: {e}")
        messages.error(request, f"Error connecting to Google Fit: {str(e)}")
        return redirect('stress_analysis:dashboard')


def google_fit_callback(request):
    """Handle Google Fit OAuth callback"""
    try:
        print("Google Fit callback received")
        print(f"GET params: {request.GET}")
        
        # Validate state first
        from .utils import validate_state
        if not validate_state(request):
            messages.error(request, "Security validation failed. Please try connecting again.")
            return redirect('stress_analysis:dashboard')
        
        if 'error' in request.GET:
            error_msg = request.GET.get('error', 'Unknown error')
            messages.error(request, f"Google Fit authorization failed: {error_msg}")
            return redirect('stress_analysis:dashboard')
        
        if 'code' not in request.GET:
            messages.error(request, "No authorization code received")
            return redirect('stress_analysis:dashboard')
        
        # Check if user is authenticated
        if not request.user.is_authenticated:
            # Store the callback data in session and redirect to login
            request.session['google_fit_callback_data'] = request.GET.urlencode()
            request.session['google_fit_redirect_after_login'] = request.build_absolute_uri()
            return redirect('/accounts/sign_in_patient')
        
        # Exchange authorization code for tokens
        authorization_response = request.build_absolute_uri()
        print(f"Authorization response: {authorization_response}")
        
        credentials = exchange_code_for_token(request, authorization_response)
        
        # Save credentials to session
        save_credentials_to_session(request, credentials)
        
        messages.success(request, "Successfully connected to Google Fit! You can now sync your health data.")
        return redirect('stress_analysis:dashboard')
        
    except Exception as e:
        print(f"Error in google_fit_callback: {e}")
        messages.error(request, f"Error during Google Fit callback: {str(e)}")
        return redirect('stress_analysis:dashboard')


@login_required(login_url='/accounts/sign_in_patient')
def disconnect_google_fit(request):
    """Disconnect Google Fit"""
    if 'google_fit_credentials' in request.session:
        del request.session['google_fit_credentials']
        messages.success(request, "Disconnected from Google Fit")
    else:
        messages.info(request, "Not connected to Google Fit")
    
    return redirect('stress_analysis:dashboard')


@login_required(login_url='/accounts/sign_in_patient')
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
            
            print(f"Data fetched - HR: {len(heart_rate_data)}, Sleep: {len(sleep_data)}, Steps: {len(step_data)}, Calories: {len(calories_data)}")
            
            # Process data
            processed_data = process_health_data(heart_rate_data, sleep_data, step_data, calories_data)
            
            # Calculate data metrics
            real_data_days = sum(1 for item in processed_data if item.get('has_real_data', False))
            has_sufficient_data = real_data_days >= 3
            
            return JsonResponse({
                'success': True,
                'processed_records': len(processed_data),
                'real_data_days': real_data_days,
                'has_sufficient_data': has_sufficient_data,
                'message': f'Successfully synced {len(processed_data)} days of data ({real_data_days} with real data)',
                'data_available': {
                    'heart_rate': len(heart_rate_data) > 0,
                    'sleep': len(sleep_data) > 0,
                    'steps': len(step_data) > 0,
                    'calories': len(calories_data) > 0
                }
            })
            
        except Exception as e:
            print(f"Error in sync_google_fit_data: {e}")
            return JsonResponse({'success': False, 'error': str(e)}, status=500)
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)


@login_required(login_url='/accounts/sign_in_patient')
def get_stress_insights(request):
    """API endpoint for stress insights"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            # Return demo data if not connected
            return get_demo_insights()
        
        # Get real data for last 7 days
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        
        heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
        sleep_data = fit_service.get_sleep_data(start_time, end_time)
        step_data = fit_service.get_step_count(start_time, end_time)
        calories_data = fit_service.get_calories_data(start_time, end_time)
        
        processed_data = process_health_data(heart_rate_data, sleep_data, step_data, calories_data)
        
        # Calculate data metrics
        real_data_days = sum(1 for item in processed_data if item.get('has_real_data', False))
        total_days = len(processed_data)
        
        has_real_hr = len(heart_rate_data) > 10
        has_real_sleep = len(sleep_data) > 2
        has_real_activity = len(step_data) >= 5
        has_sufficient_data = (has_real_hr and has_real_sleep and has_real_activity) or real_data_days >= 3
        
        if not processed_data or real_data_days == 0:
            return get_demo_insights()
        
        # Prepare data for charts
        timestamps = [data['date'].strftime('%Y-%m-%d') if hasattr(data['date'], 'strftime') else str(data['date']) for data in processed_data]
        stress_levels = [data['stress_level'] for data in processed_data]
        heart_rates = [data['heart_rate'] for data in processed_data]
        sleep_durations = [data['sleep_duration'] for data in processed_data]
        steps_data = [data['steps'] for data in processed_data]
        
        # Get data sources for each day
        data_sources = []
        for data in processed_data:
            sources = {}
            if data.get('has_real_data', False):
                sources['heart_rate'] = 'google_fit' if data.get('heart_rate_source') == 'google_fit' else 'demo'
                sources['sleep'] = 'google_fit' if data.get('sleep_source') == 'google_fit' else 'demo'
                sources['steps'] = 'google_fit' if data.get('steps_source') == 'google_fit' else 'demo'
                sources['calories'] = 'google_fit' if data.get('calories_source') == 'google_fit' else 'demo'
            else:
                sources = {metric: 'demo' for metric in ['heart_rate', 'sleep', 'steps', 'calories']}
            data_sources.append(sources)
        
        return JsonResponse({
            'timestamps': timestamps,
            'stress_levels': stress_levels,
            'heart_rates': heart_rates,
            'sleep_durations': sleep_durations,
            'steps_data': steps_data,
            'calories_data': [data.get('calories', 0) for data in processed_data],
            'processed_data': [
                {
                    'date': timestamps[i],
                    'stress_level': stress_levels[i],
                    'heart_rate': heart_rates[i],
                    'sleep_duration': sleep_durations[i],
                    'steps': steps_data[i],
                    'data_sources': data_sources[i]
                }
                for i in range(len(processed_data))
            ],
            'statistics': {
                'average_stress': round(sum(stress_levels) / len(stress_levels), 1),
                'max_stress': max(stress_levels),
                'min_stress': min(stress_levels),
                'data_points': len(processed_data)
            },
            'data_metrics': {
                'real_data_days': real_data_days,
                'total_days': total_days,
                'has_sufficient_data': has_sufficient_data,
                'has_real_data': real_data_days > 0,
                'heart_rate_points': len(heart_rate_data),
                'sleep_sessions': len(sleep_data),
                'step_points': len(step_data),
                'calories_points': len(calories_data)
            }
        })
        
    except Exception as e:
        print(f"Error in get_stress_insights: {e}")
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
        'calories_data': [steps * 0.04 for steps in steps_data],  # Estimate calories from steps
        'processed_data': [
            {
                'date': timestamps[i],
                'stress_level': stress_levels[i],
                'heart_rate': heart_rates[i],
                'sleep_duration': sleep_durations[i],
                'steps': steps_data[i],
                'calories': steps_data[i] * 0.04,
                'data_sources': {metric: 'demo' for metric in ['heart_rate', 'sleep', 'steps', 'calories']},
                'has_real_data': False
            }
            for i in range(7)
        ],
        'statistics': {
            'average_stress': round(sum(stress_levels) / len(stress_levels), 1),
            'max_stress': max(stress_levels),
            'min_stress': min(stress_levels),
            'data_points': len(stress_levels)
        },
        'data_metrics': {
            'real_data_days': 0,
            'total_days': 7,
            'has_sufficient_data': False,
            'has_real_data': False,
            'heart_rate_points': 0,
            'sleep_sessions': 0,
            'step_points': 0,
            'calories_points': 0
        }
    })


@login_required(login_url='/accounts/sign_in_patient')
def stress_analysis_api(request):
    """Comprehensive API endpoint for frontend dashboard"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            return get_demo_analysis_data()
        
        # Get real data
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        
        heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
        sleep_data = fit_service.get_sleep_data(start_time, end_time)
        step_data = fit_service.get_step_count(start_time, end_time)
        calories_data = fit_service.get_calories_data(start_time, end_time)
        
        processed_data = process_health_data(heart_rate_data, sleep_data, step_data, calories_data)
        
        # Calculate data sufficiency
        real_data_days = sum(1 for item in processed_data if item.get('has_real_data', False))
        total_days = len(processed_data)
        
        has_real_hr = len(heart_rate_data) > 10
        has_real_sleep = len(sleep_data) > 2
        has_real_activity = len(step_data) >= 5
        has_sufficient_data = (has_real_hr and has_real_sleep and has_real_activity) or real_data_days >= 3
        
        if not processed_data or real_data_days == 0:
            return get_demo_analysis_data()
        
        # Prepare response data
        timestamps = [data['date'].strftime('%Y-%m-%d') if hasattr(data['date'], 'strftime') else str(data['date']) for data in processed_data]
        
        response_data = {
            'timestamps': timestamps,
            'stress_levels': [data['stress_level'] for data in processed_data],
            'heart_rates': [data['heart_rate'] for data in processed_data],
            'sleep_durations': [data['sleep_duration'] for data in processed_data],
            'steps_data': [data['steps'] for data in processed_data],
            'calories_data': [data.get('calories', 0) for data in processed_data],
            'processed_data': processed_data,
            'statistics': {
                'average_stress': round(sum([data['stress_level'] for data in processed_data]) / len(processed_data), 1),
                'max_stress': max([data['stress_level'] for data in processed_data]),
                'min_stress': min([data['stress_level'] for data in processed_data]),
                'data_points': len(processed_data)
            },
            'has_sufficient_data': has_sufficient_data,
            'has_real_data': real_data_days > 0,
            'real_data_days': real_data_days,
            'total_days': total_days,
            'data_metrics': {
                'heart_rate_points': len(heart_rate_data),
                'sleep_sessions': len(sleep_data),
                'step_points': len(step_data),
                'calories_points': len(calories_data)
            }
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        print(f"Error in stress_analysis_api: {e}")
        return JsonResponse({'error': str(e)}, status=500)


def get_demo_analysis_data():
    """Return demo analysis data"""
    import random
    from datetime import datetime, timedelta
    
    timestamps = []
    for i in range(7):
        date = datetime.now() - timedelta(days=6-i)
        timestamps.append(date.strftime('%Y-%m-%d'))
    
    stress_levels = [round(random.uniform(30, 70), 1) for _ in range(7)]
    heart_rates = [random.randint(65, 85) for _ in range(7)]
    sleep_durations = [round(random.uniform(5, 9), 1) for _ in range(7)]
    steps_data = [random.randint(5000, 12000) for _ in range(7)]
    
    return JsonResponse({
        'timestamps': timestamps,
        'stress_levels': stress_levels,
        'heart_rates': heart_rates,
        'sleep_durations': sleep_durations,
        'steps_data': steps_data,
        'calories_data': [steps * 0.04 for steps in steps_data],
        'processed_data': [
            {
                'date': timestamps[i],
                'stress_level': stress_levels[i],
                'heart_rate': heart_rates[i],
                'sleep_duration': sleep_durations[i],
                'steps': steps_data[i],
                'calories': steps_data[i] * 0.04,
                'data_sources': {metric: 'demo' for metric in ['heart_rate', 'sleep', 'steps', 'calories']},
                'has_real_data': False
            }
            for i in range(7)
        ],
        'statistics': {
            'average_stress': round(sum(stress_levels) / len(stress_levels), 1),
            'max_stress': max(stress_levels),
            'min_stress': min(stress_levels),
            'data_points': len(stress_levels)
        },
        'has_sufficient_data': False,
        'has_real_data': False,
        'real_data_days': 0,
        'total_days': 7,
        'data_metrics': {
            'heart_rate_points': 0,
            'sleep_sessions': 0,
            'step_points': 0,
            'calories_points': 0
        }
    })