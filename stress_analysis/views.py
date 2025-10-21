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
# views.py - Add these new API endpoints

@login_required(login_url='/accounts/sign_in_patient')
def api_stress_chart(request):
    """API endpoint for stress chart data only"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            return get_demo_stress_data()
        
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
        sleep_data = fit_service.get_sleep_data(start_time, end_time)
        step_data = fit_service.get_step_count(start_time, end_time)
        calories_data = fit_service.get_calories_data(start_time, end_time)
        
        processed_data = process_health_data(heart_rate_data, sleep_data, step_data, calories_data)
        
        if not processed_data:
            return get_demo_stress_data()
        
        timestamps = [data['date'].strftime('%Y-%m-%d') if hasattr(data['date'], 'strftime') else str(data['date']) for data in processed_data]
        stress_levels = [data['stress_level'] for data in processed_data]
        
        return JsonResponse({
            'timestamps': timestamps,
            'stress_levels': stress_levels,
            'has_real_data': any(item.get('has_real_data', False) for item in processed_data),
            'data_points': len(processed_data)
        })
        
    except Exception as e:
        print(f"Error in api_stress_chart: {e}")
        return get_demo_stress_data()

@login_required(login_url='/accounts/sign_in_patient')
def api_heart_rate_chart(request):
    """API endpoint for heart rate chart data only"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            return get_demo_heart_rate_data()
        
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
        
        # If no real heart rate data, use demo
        if not heart_rate_data:
            return get_demo_heart_rate_data()
        
        # Process heart rate data into daily averages
        daily_heart_rates = {}
        for hr_point in heart_rate_data:
            date = hr_point['timestamp'].date()
            if date not in daily_heart_rates:
                daily_heart_rates[date] = []
            daily_heart_rates[date].append(hr_point['value'])
        
        timestamps = []
        heart_rates = []
        
        for i in range(7):
            date = (timezone.now() - timedelta(days=6-i)).date()
            timestamps.append(date.strftime('%Y-%m-%d'))
            if date in daily_heart_rates:
                heart_rates.append(round(sum(daily_heart_rates[date]) / len(daily_heart_rates[date])))
            else:
                # Default heart rate if no data
                heart_rates.append(72)
        
        return JsonResponse({
            'timestamps': timestamps,
            'heart_rates': heart_rates,
            'has_real_data': len(heart_rate_data) > 0,
            'data_points': len(heart_rate_data)
        })
        
    except Exception as e:
        print(f"Error in api_heart_rate_chart: {e}")
        return get_demo_heart_rate_data()

@login_required(login_url='/accounts/sign_in_patient')
def api_sleep_chart(request):
    """API endpoint for sleep chart data only"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            return get_demo_sleep_data()
        
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        sleep_data = fit_service.get_sleep_data(start_time, end_time)
        
        if not sleep_data:
            return get_demo_sleep_data()
        
        # Process sleep data into daily totals
        daily_sleep = {}
        for sleep_session in sleep_data:
            date = sleep_session['start_time'].date()
            duration_hours = sleep_session['duration_minutes'] / 60.0
            if date not in daily_sleep:
                daily_sleep[date] = 0
            daily_sleep[date] += duration_hours
        
        timestamps = []
        sleep_durations = []
        
        for i in range(7):
            date = (timezone.now() - timedelta(days=6-i)).date()
            timestamps.append(date.strftime('%Y-%m-%d'))
            if date in daily_sleep:
                sleep_durations.append(round(daily_sleep[date], 1))
            else:
                # Default sleep if no data
                sleep_durations.append(7.0)
        
        return JsonResponse({
            'timestamps': timestamps,
            'sleep_durations': sleep_durations,
            'has_real_data': len(sleep_data) > 0,
            'data_points': len(sleep_data)
        })
        
    except Exception as e:
        print(f"Error in api_sleep_chart: {e}")
        return get_demo_sleep_data()

@login_required(login_url='/accounts/sign_in_patient')
def api_steps_chart(request):
    """API endpoint for steps chart data only"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            return get_demo_steps_data()
        
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        step_data = fit_service.get_step_count(start_time, end_time)
        
        if not step_data:
            return get_demo_steps_data()
        
        # Process step data
        daily_steps = {}
        for step_point in step_data:
            date = step_point['timestamp'].date()
            if date not in daily_steps:
                daily_steps[date] = 0
            daily_steps[date] += step_point['value']
        
        timestamps = []
        steps_data = []
        
        for i in range(7):
            date = (timezone.now() - timedelta(days=6-i)).date()
            timestamps.append(date.strftime('%Y-%m-%d'))
            if date in daily_steps:
                steps_data.append(daily_steps[date])
            else:
                # Default steps if no data
                steps_data.append(8000)
        
        return JsonResponse({
            'timestamps': timestamps,
            'steps_data': steps_data,
            'has_real_data': len(step_data) > 0,
            'data_points': len(step_data)
        })
        
    except Exception as e:
        print(f"Error in api_steps_chart: {e}")
        return get_demo_steps_data()

@login_required(login_url='/accounts/sign_in_patient')
def api_calories_chart(request):
    """API endpoint for calories chart data only"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            return get_demo_calories_data()
        
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        calories_data = fit_service.get_calories_data(start_time, end_time)
        
        if not calories_data:
            # Estimate from steps if no calorie data
            step_data = fit_service.get_step_count(start_time, end_time)
            if step_data:
                daily_steps = {}
                for step_point in step_data:
                    date = step_point['timestamp'].date()
                    if date not in daily_steps:
                        daily_steps[date] = 0
                    daily_steps[date] += step_point['value']
                
                timestamps = []
                calories_data_points = []
                
                for i in range(7):
                    date = (timezone.now() - timedelta(days=6-i)).date()
                    timestamps.append(date.strftime('%Y-%m-%d'))
                    if date in daily_steps:
                        calories_data_points.append(round(daily_steps[date] * 0.04))
                    else:
                        calories_data_points.append(320)  # Default based on 8000 steps
                
                return JsonResponse({
                    'timestamps': timestamps,
                    'calories_data': calories_data_points,
                    'has_real_data': False,  # Estimated data
                    'data_points': len(step_data),
                    'data_source': 'estimated_from_steps'
                })
            else:
                return get_demo_calories_data()
        
        # Process real calorie data
        daily_calories = {}
        for calorie_point in calories_data:
            date = calorie_point['timestamp'].date()
            if date not in daily_calories:
                daily_calories[date] = 0
            daily_calories[date] += calorie_point['value']
        
        timestamps = []
        calories_data_points = []
        
        for i in range(7):
            date = (timezone.now() - timedelta(days=6-i)).date()
            timestamps.append(date.strftime('%Y-%m-%d'))
            if date in daily_calories:
                calories_data_points.append(round(daily_calories[date]))
            else:
                calories_data_points.append(320)  # Default
        
        return JsonResponse({
            'timestamps': timestamps,
            'calories_data': calories_data_points,
            'has_real_data': len(calories_data) > 0,
            'data_points': len(calories_data)
        })
        
    except Exception as e:
        print(f"Error in api_calories_chart: {e}")
        return get_demo_calories_data()

@login_required(login_url='/accounts/sign_in_patient')
def api_correlation_chart(request):
    """API endpoint for correlation chart data only"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            return get_demo_correlation_data()
        
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        
        # Get all data needed for correlations
        heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
        sleep_data = fit_service.get_sleep_data(start_time, end_time)
        step_data = fit_service.get_step_count(start_time, end_time)
        
        processed_data = process_health_data(heart_rate_data, sleep_data, step_data, [])
        
        if not processed_data:
            return get_demo_correlation_data()
        
        stress_levels = [data['stress_level'] for data in processed_data]
        heart_rates = [data['heart_rate'] for data in processed_data]
        sleep_durations = [data['sleep_duration'] for data in processed_data]
        steps_data = [data['steps'] for data in processed_data]
        
        # Calculate correlations
        stress_vs_sleep = calculate_correlation(stress_levels, sleep_durations)
        stress_vs_activity = calculate_correlation(stress_levels, steps_data)
        stress_vs_heart_rate = calculate_correlation(stress_levels, heart_rates)
        
        return JsonResponse({
            'correlations': {
                'stress_vs_sleep': stress_vs_sleep,
                'stress_vs_activity': stress_vs_activity,
                'stress_vs_heart_rate': stress_vs_heart_rate
            },
            'has_real_data': any(item.get('has_real_data', False) for item in processed_data),
            'data_points': len(processed_data)
        })
        
    except Exception as e:
        print(f"Error in api_correlation_chart: {e}")
        return get_demo_correlation_data()

@login_required(login_url='/accounts/sign_in_patient')
def api_pattern_chart(request):
    """API endpoint for stress pattern chart data only"""
    try:
        credentials = get_google_fit_credentials(request)
        
        if not credentials:
            return get_demo_pattern_data()
        
        end_time = timezone.now()
        start_time = end_time - timedelta(days=7)
        
        fit_service = GoogleFitService(credentials)
        heart_rate_data = fit_service.get_heart_rate_data(start_time, end_time)
        sleep_data = fit_service.get_sleep_data(start_time, end_time)
        step_data = fit_service.get_step_count(start_time, end_time)
        calories_data = fit_service.get_calories_data(start_time, end_time)
        
        processed_data = process_health_data(heart_rate_data, sleep_data, step_data, calories_data)
        
        if not processed_data:
            return get_demo_pattern_data()
        
        stress_levels = [data['stress_level'] for data in processed_data]
        
        # Categorize stress levels
        stress_categories = {
            'Low': 0,
            'Moderate': 0,
            'High': 0,
            'Very High': 0
        }
        
        for stress_level in stress_levels:
            if stress_level < 25:
                stress_categories['Low'] += 1
            elif stress_level < 50:
                stress_categories['Moderate'] += 1
            elif stress_level < 75:
                stress_categories['High'] += 1
            else:
                stress_categories['Very High'] += 1
        
        return JsonResponse({
            'stress_categories': stress_categories,
            'has_real_data': any(item.get('has_real_data', False) for item in processed_data),
            'data_points': len(processed_data)
        })
        
    except Exception as e:
        print(f"Error in api_pattern_chart: {e}")
        return get_demo_pattern_data()

# Demo data functions for each chart
def get_demo_stress_data():
    import random
    timestamps = [(timezone.now() - timedelta(days=6-i)).strftime('%Y-%m-%d') for i in range(7)]
    stress_levels = [round(random.uniform(30, 70), 1) for _ in range(7)]
    
    return JsonResponse({
        'timestamps': timestamps,
        'stress_levels': stress_levels,
        'has_real_data': False,
        'data_points': 7
    })

def get_demo_heart_rate_data():
    import random
    timestamps = [(timezone.now() - timedelta(days=6-i)).strftime('%Y-%m-%d') for i in range(7)]
    heart_rates = [random.randint(65, 85) for _ in range(7)]
    
    return JsonResponse({
        'timestamps': timestamps,
        'heart_rates': heart_rates,
        'has_real_data': False,
        'data_points': 7
    })

def get_demo_sleep_data():
    import random
    timestamps = [(timezone.now() - timedelta(days=6-i)).strftime('%Y-%m-%d') for i in range(7)]
    sleep_durations = [round(random.uniform(5, 9), 1) for _ in range(7)]
    
    return JsonResponse({
        'timestamps': timestamps,
        'sleep_durations': sleep_durations,
        'has_real_data': False,
        'data_points': 7
    })

def get_demo_steps_data():
    import random
    timestamps = [(timezone.now() - timedelta(days=6-i)).strftime('%Y-%m-%d') for i in range(7)]
    steps_data = [random.randint(5000, 12000) for _ in range(7)]
    
    return JsonResponse({
        'timestamps': timestamps,
        'steps_data': steps_data,
        'has_real_data': False,
        'data_points': 7
    })

def get_demo_calories_data():
    import random
    timestamps = [(timezone.now() - timedelta(days=6-i)).strftime('%Y-%m-%d') for i in range(7)]
    calories_data = [random.randint(200, 500) for _ in range(7)]
    
    return JsonResponse({
        'timestamps': timestamps,
        'calories_data': calories_data,
        'has_real_data': False,
        'data_points': 7
    })

def get_demo_correlation_data():
    import random
    return JsonResponse({
        'correlations': {
            'stress_vs_sleep': round(random.uniform(-0.8, 0.8), 2),
            'stress_vs_activity': round(random.uniform(-0.8, 0.8), 2),
            'stress_vs_heart_rate': round(random.uniform(-0.8, 0.8), 2)
        },
        'has_real_data': False,
        'data_points': 7
    })

def get_demo_pattern_data():
    import random
    return JsonResponse({
        'stress_categories': {
            'Low': random.randint(1, 3),
            'Moderate': random.randint(1, 3),
            'High': random.randint(1, 2),
            'Very High': random.randint(0, 1)
        },
        'has_real_data': False,
        'data_points': 7
    })

def calculate_correlation(array1, array2):
    """Helper function to calculate correlation between two arrays"""
    n = len(array1)
    if n != len(array2) or n == 0:
        return 0
    
    sum1 = sum(array1)
    sum2 = sum(array2)
    sum1_sq = sum(x*x for x in array1)
    sum2_sq = sum(x*x for x in array2)
    p_sum = sum(array1[i] * array2[i] for i in range(n))
    
    num = p_sum - (sum1 * sum2 / n)
    den = ((sum1_sq - sum1*sum1/n) * (sum2_sq - sum2*sum2/n)) ** 0.5
    
    return round(num / den, 2) if den != 0 else 0