import json
import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from django.utils import timezone
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
import joblib
import os
from django.conf import settings

class GoogleFitService:
    def __init__(self, credentials):
        self.credentials = credentials
        self.base_url = "https://www.googleapis.com/fitness/v1/users/me"
    
    def get_headers(self):
        """Get headers with access token"""
        if self.credentials.expired:
            self.credentials.refresh(Request())
        
        return {
            'Authorization': f'Bearer {self.credentials.token}',
            'Content-Type': 'application/json'
        }
    
    def get_heart_rate_data(self, start_time, end_time):
        """Fetch heart rate data with better error handling"""
        url = f"{self.base_url}/dataset:aggregate"
        
        # Convert to milliseconds since epoch
        start_time_millis = int(start_time.timestamp() * 1000)
        end_time_millis = int(end_time.timestamp() * 1000)
        
        body = {
            "aggregateBy": [{
                "dataTypeName": "com.google.heart_rate.bpm",
                "dataSourceId": "derived:com.google.heart_rate.bpm:com.google.android.gms:merge_heart_rate_bpm"
            }],
            "bucketByTime": {"durationMillis": 86400000},  # 1 day buckets
            "startTimeMillis": start_time_millis,
            "endTimeMillis": end_time_millis
        }
        
        try:
            print(f"Fetching heart rate data from {start_time} to {end_time}")
            response = requests.post(url, headers=self.get_headers(), json=body)
            
            if response.status_code == 403:
                print("⚠️ Heart rate access denied - may need additional permissions")
                # Try alternative data source
                return self._get_heart_rate_alternative(start_time, end_time)
                
            response.raise_for_status()
            data = response.json()
            
            print(f"Heart rate API response: {json.dumps(data, indent=2)[:500]}...")
            
            # Process the heart rate data
            heart_rate_data = []
            if 'bucket' in data:
                for bucket in data['bucket']:
                    if 'dataset' in bucket and bucket['dataset']:
                        for dataset in bucket['dataset']:
                            if 'point' in dataset:
                                for point in dataset['point']:
                                    try:
                                        timestamp = datetime.fromtimestamp(int(point['startTimeNanos']) / 1000000000)
                                        heart_rate = float(point['value'][0]['fpVal'])
                                        heart_rate_data.append({
                                            'timestamp': timestamp,
                                            'heart_rate': heart_rate,
                                            'source': 'google_fit'
                                        })
                                        print(f"✅ Heart rate: {timestamp} - {heart_rate} BPM")
                                    except (KeyError, ValueError, IndexError) as e:
                                        print(f"❌ Error processing heart rate point: {e}")
                                        continue
            
            print(f"✅ Total heart rate data points: {len(heart_rate_data)}")
            return heart_rate_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching heart rate data: {e}")
            return self._get_demo_heart_rate_data(start_time, end_time)
    
    def _get_heart_rate_alternative(self, start_time, end_time):
        """Alternative method to get heart rate data"""
        print("🔄 Trying alternative heart rate data source...")
        # For now, use demo data since we don't have heart rate permissions
        return self._get_demo_heart_rate_data(start_time, end_time)
    
    def get_sleep_data(self, start_time, end_time):
        """Fetch sleep data with fixed parameters"""
        url = f"{self.base_url}/sessions"
        
        # Format dates properly for sleep API
        start_time_str = start_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        end_time_str = end_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')
        
        params = {
            'startTime': start_time_str,
            'endTime': end_time_str,
            'activityType': 72  # Sleep activity type
        }
        
        try:
            print(f"Fetching sleep data from {start_time} to {end_time}")
            response = requests.get(url, headers=self.get_headers(), params=params)
            
            if response.status_code == 400:
                print("⚠️ Sleep API bad request - trying with simplified parameters")
                # Try without activityType
                params.pop('activityType', None)
                response = requests.get(url, headers=self.get_headers(), params=params)
                
            response.raise_for_status()
            data = response.json()
            
            print(f"Sleep API response: {json.dumps(data, indent=2)[:500]}...")
            
            sleep_data = []
            if 'session' in data:
                for session in data['session']:
                    try:
                        start_time_ms = int(session['startTimeMillis'])
                        end_time_ms = int(session['endTimeMillis'])
                        start_dt = datetime.fromtimestamp(start_time_ms / 1000)
                        end_dt = datetime.fromtimestamp(end_time_ms / 1000)
                        duration_hours = (end_dt - start_dt).total_seconds() / 3600
                        
                        sleep_data.append({
                            'start_time': start_dt,
                            'end_time': end_dt,
                            'duration_hours': duration_hours,
                            'type': session.get('name', 'Unknown'),
                            'source': 'google_fit'
                        })
                        print(f"✅ Sleep: {start_dt} to {end_dt} - {duration_hours:.1f}h")
                    except (KeyError, ValueError) as e:
                        print(f"❌ Error processing sleep session: {e}")
                        continue
            
            print(f"✅ Total sleep sessions: {len(sleep_data)}")
            return sleep_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching sleep data: {e}")
            return self._get_demo_sleep_data(start_time, end_time)
    
    def get_step_count(self, start_time, end_time):
        """Fetch step count data"""
        url = f"{self.base_url}/dataset:aggregate"
        
        start_time_millis = int(start_time.timestamp() * 1000)
        end_time_millis = int(end_time.timestamp() * 1000)
        
        body = {
            "aggregateBy": [{
                "dataTypeName": "com.google.step_count.delta",
                "dataSourceId": "derived:com.google.step_count.delta:com.google.android.gms:merge_step_deltas"
            }],
            "bucketByTime": {"durationMillis": 86400000},
            "startTimeMillis": start_time_millis,
            "endTimeMillis": end_time_millis
        }
        
        try:
            print(f"Fetching step data from {start_time} to {end_time}")
            response = requests.post(url, headers=self.get_headers(), json=body)
            response.raise_for_status()
            data = response.json()
            
            step_data = []
            if 'bucket' in data:
                for bucket in data['bucket']:
                    if 'dataset' in bucket and bucket['dataset']:
                        for dataset in bucket['dataset']:
                            if 'point' in dataset:
                                for point in dataset['point']:
                                    try:
                                        timestamp = datetime.fromtimestamp(int(point['startTimeNanos']) / 1000000000)
                                        steps = int(point['value'][0]['intVal'])
                                        step_data.append({
                                            'timestamp': timestamp,
                                            'steps': steps,
                                            'source': 'google_fit'
                                        })
                                        print(f"✅ Steps: {timestamp} - {steps} steps")
                                    except (KeyError, ValueError, IndexError) as e:
                                        print(f"❌ Error processing step point: {e}")
                                        continue
            
            print(f"✅ Total step data points: {len(step_data)}")
            return step_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching step data: {e}")
            return self._get_demo_step_count(start_time, end_time)
    
    def get_calories_data(self, start_time, end_time):
        """Fetch calories data"""
        url = f"{self.base_url}/dataset:aggregate"
        
        start_time_millis = int(start_time.timestamp() * 1000)
        end_time_millis = int(end_time.timestamp() * 1000)
        
        body = {
            "aggregateBy": [{
                "dataTypeName": "com.google.calories.expended",
                "dataSourceId": "derived:com.google.calories.expended:com.google.android.gms:merge_calories_expended"
            }],
            "bucketByTime": {"durationMillis": 86400000},
            "startTimeMillis": start_time_millis,
            "endTimeMillis": end_time_millis
        }
        
        try:
            print(f"Fetching calories data from {start_time} to {end_time}")
            response = requests.post(url, headers=self.get_headers(), json=body)
            response.raise_for_status()
            data = response.json()
            
            calories_data = []
            if 'bucket' in data:
                for bucket in data['bucket']:
                    if 'dataset' in bucket and bucket['dataset']:
                        for dataset in bucket['dataset']:
                            if 'point' in dataset:
                                for point in dataset['point']:
                                    try:
                                        timestamp = datetime.fromtimestamp(int(point['startTimeNanos']) / 1000000000)
                                        calories = float(point['value'][0]['fpVal'])
                                        calories_data.append({
                                            'timestamp': timestamp,
                                            'calories': calories,
                                            'source': 'google_fit'
                                        })
                                        print(f"✅ Calories: {timestamp} - {calories} cal")
                                    except (KeyError, ValueError, IndexError) as e:
                                        print(f"❌ Error processing calories point: {e}")
                                        continue
            
            print(f"✅ Total calories data points: {len(calories_data)}")
            return calories_data
            
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching calories data: {e}")
            return self._get_demo_calories_data(start_time, end_time)

    # Demo data methods (keep your existing demo methods)
    def _get_demo_heart_rate_data(self, start_time, end_time):
        """Generate realistic demo heart rate data"""
        print("🔄 Generating demo heart rate data...")
        heart_rate_data = []
        current = start_time
        while current <= end_time:
            hour = current.hour
            if 2 <= hour <= 6: base_hr = np.random.normal(58, 3)
            elif 7 <= hour <= 9: base_hr = np.random.normal(72, 5)
            elif 10 <= hour <= 18: base_hr = np.random.normal(78, 8)
            else: base_hr = np.random.normal(68, 4)
            
            heart_rate = max(50, min(120, base_hr + np.random.normal(0, 2)))
            heart_rate_data.append({
                'timestamp': current,
                'heart_rate': round(heart_rate, 1),
                'source': 'demo'
            })
            current += timedelta(hours=1)
        return heart_rate_data[:24*7]

    def _get_demo_sleep_data(self, start_time, end_time):
        """Generate realistic demo sleep data"""
        print("🔄 Generating demo sleep data...")
        sleep_data = []
        current = start_time.date()
        end_date = end_time.date()
        while current <= end_date:
            if np.random.random() > 0.2:
                sleep_duration = np.random.normal(7.5, 1.0)
                sleep_duration = max(4, min(10, sleep_duration))
                sleep_start_hour = np.random.normal(23, 1.5)
                sleep_start = datetime.combine(current, datetime.min.time()) + timedelta(hours=sleep_start_hour)
                sleep_end = sleep_start + timedelta(hours=sleep_duration)
                sleep_data.append({
                    'start_time': sleep_start,
                    'end_time': sleep_end,
                    'duration_hours': round(sleep_duration, 1),
                    'type': np.random.choice(['Deep', 'Light', 'REM', 'Awake']),
                    'source': 'demo'
                })
            current += timedelta(days=1)
        return sleep_data

    def _get_demo_step_count(self, start_time, end_time):
        """Generate realistic demo step data"""
        print("🔄 Generating demo step data...")
        step_data = []
        current = start_time.date()
        end_date = end_time.date()
        while current <= end_date:
            is_weekend = current.weekday() >= 5
            steps = np.random.normal(6000, 2000) if is_weekend else np.random.normal(8000, 1500)
            steps = max(1000, min(20000, steps))
            step_data.append({
                'timestamp': datetime.combine(current, datetime.min.time()),
                'steps': int(steps),
                'source': 'demo'
            })
            current += timedelta(days=1)
        return step_data

    def _get_demo_calories_data(self, start_time, end_time):
        """Generate realistic demo calories data"""
        print("🔄 Generating demo calories data...")
        calories_data = []
        current = start_time.date()
        end_date = end_time.date()
        while current <= end_date:
            steps_today = np.random.normal(8000, 2000)
            calories = steps_today * 0.04 + np.random.normal(1600, 200)
            calories = max(1200, min(3500, calories))
            calories_data.append({
                'timestamp': datetime.combine(current, datetime.min.time()),
                'calories': round(calories, 1),
                'source': 'demo'
            })
            current += timedelta(days=1)
        return calories_data

def process_health_data(heart_rate_data, sleep_data, step_data, calories_data):
    """Process and combine all health data - FIXED to use real data"""
    processed_data = []
    
    # Create a date range for the last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    print(f"🔄 Processing health data from {start_date} to {end_date}")
    print(f"📊 Input data - HR: {len(heart_rate_data)}, Sleep: {len(sleep_data)}, Steps: {len(step_data)}, Calories: {len(calories_data)}")
    
    current_date = start_date
    day_count = 0
    
    while current_date <= end_date and day_count < 7:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Find REAL heart rate data for this date
        daily_heart_rates = [
            hr['heart_rate'] for hr in heart_rate_data 
            if hr['timestamp'].date() == current_date.date() and hr.get('source') == 'google_fit'
        ]
        
        # Find REAL sleep data for this date
        daily_sleep = [
            sleep['duration_hours'] for sleep in sleep_data 
            if sleep['start_time'].date() == current_date.date() and sleep.get('source') == 'google_fit'
        ]
        
        # Find REAL step data for this date
        daily_steps = [
            step['steps'] for step in step_data 
            if step['timestamp'].date() == current_date.date() and step.get('source') == 'google_fit'
        ]
        
        # Find REAL calories data for this date
        daily_calories = [
            cal['calories'] for cal in calories_data 
            if cal['timestamp'].date() == current_date.date() and cal.get('source') == 'google_fit'
        ]
        
        # Use real data if available, otherwise use demo data
        if daily_heart_rates:
            avg_heart_rate = np.mean(daily_heart_rates)
            hr_source = 'google_fit'
        else:
            # Find demo heart rate data
            demo_hr = [hr['heart_rate'] for hr in heart_rate_data 
                      if hr['timestamp'].date() == current_date.date() and hr.get('source') == 'demo']
            avg_heart_rate = np.mean(demo_hr) if demo_hr else 72
            hr_source = 'demo'
        
        if daily_sleep:
            sleep_duration = np.mean(daily_sleep)
            sleep_source = 'google_fit'
        else:
            demo_sleep = [sleep['duration_hours'] for sleep in sleep_data 
                         if sleep['start_time'].date() == current_date.date() and sleep.get('source') == 'demo']
            sleep_duration = np.mean(demo_sleep) if demo_sleep else 7.0
            sleep_source = 'demo'
        
        if daily_steps:
            total_steps = sum(daily_steps)
            steps_source = 'google_fit'
        else:
            demo_steps = [step['steps'] for step in step_data 
                         if step['timestamp'].date() == current_date.date() and step.get('source') == 'demo']
            total_steps = sum(demo_steps) if demo_steps else 8000
            steps_source = 'demo'
        
        if daily_calories:
            total_calories = sum(daily_calories)
            calories_source = 'google_fit'
        else:
            demo_calories = [cal['calories'] for cal in calories_data 
                            if cal['timestamp'].date() == current_date.date() and cal.get('source') == 'demo']
            total_calories = sum(demo_calories) if demo_calories else 2000
            calories_source = 'demo'
        
        # Calculate stress level
        stress_level = calculate_stress_level(avg_heart_rate, total_steps, sleep_duration, total_calories)
        stress_category, stress_color = categorize_stress(stress_level)
        
        # Determine if we have any real data for this day
        has_real_data = any([daily_heart_rates, daily_sleep, daily_steps, daily_calories])
        
        processed_data.append({
            'date': date_str,
            'timestamp': current_date,
            'heart_rate': round(avg_heart_rate, 1),
            'sleep_duration': round(sleep_duration, 1),
            'steps': total_steps,
            'calories': round(total_calories, 1),
            'stress_level': round(stress_level, 1),
            'stress_category': stress_category,
            'stress_color': stress_color,
            'has_real_data': has_real_data,
            'data_sources': {
                'heart_rate': hr_source,
                'sleep': sleep_source,
                'steps': steps_source,
                'calories': calories_source
            }
        })
        
        data_type = "✅ REAL" if has_real_data else "🔄 DEMO"
        print(f"{data_type} Day {day_count + 1} ({date_str}): HR={avg_heart_rate:.1f}, Sleep={sleep_duration:.1f}h, Steps={total_steps}, Stress={stress_level:.1f}")
        
        current_date += timedelta(days=1)
        day_count += 1
    
    # Count real data days
    real_data_days = sum(1 for item in processed_data if item['has_real_data'])
    print(f"🎯 Processed {len(processed_data)} days - {real_data_days} with real data")
    
    return processed_data

# Keep your existing calculate_stress_level and categorize_stress functions
def calculate_stress_level(heart_rate, steps, sleep_duration, calories):
    stress_score = 50
    if heart_rate > 80: stress_score += (heart_rate - 80) * 0.5
    elif heart_rate < 60: stress_score += (60 - heart_rate) * 0.3
    if steps < 5000: stress_score += (5000 - steps) * 0.001
    if sleep_duration < 6: stress_score += (6 - sleep_duration) * 5
    return max(0, min(100, stress_score))

def categorize_stress(stress_level):
    if stress_level < 25: return 'LOW', 'success'
    elif stress_level < 50: return 'MODERATE', 'info'
    elif stress_level < 75: return 'HIGH', 'warning'
    else: return 'VERY_HIGH', 'danger'