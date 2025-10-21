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
        """Fetch real heart rate data from Google Fit"""
        url = f"{self.base_url}/dataset:aggregate"
        
        # Convert to milliseconds since epoch
        start_time_millis = int(start_time.timestamp() * 1000)
        end_time_millis = int(end_time.timestamp() * 1000)
        
        body = {
            "aggregateBy": [{
                "dataTypeName": "com.google.heart_rate.bpm",
            }],
            "bucketByTime": {"durationMillis": 3600000},  # 1 hour buckets
            "startTimeMillis": start_time_millis,
            "endTimeMillis": end_time_millis
        }
        
        try:
            response = requests.post(url, headers=self.get_headers(), json=body)
            response.raise_for_status()
            data = response.json()
            
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
                                            'heart_rate': heart_rate
                                        })
                                    except (KeyError, ValueError, IndexError) as e:
                                        print(f"Error processing heart rate point: {e}")
                                        continue
            
            return heart_rate_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching heart rate data: {e}")
            return []
    
    def get_sleep_data(self, start_time, end_time):
        """Fetch real sleep data from Google Fit"""
        url = f"{self.base_url}/sessions"
        
        start_time_str = start_time.isoformat() + 'Z'
        end_time_str = end_time.isoformat() + 'Z'
        
        params = {
            'startTime': start_time_str,
            'endTime': end_time_str,
            'activityType': 72  # Sleep activity type
        }
        
        try:
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            
            sleep_data = []
            if 'session' in data:
                for session in data['session']:
                    try:
                        start_time = datetime.fromtimestamp(int(session['startTimeMillis']) / 1000)
                        end_time = datetime.fromtimestamp(int(session['endTimeMillis']) / 1000)
                        duration_hours = (end_time - start_time).total_seconds() / 3600
                        
                        sleep_data.append({
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration_hours': duration_hours,
                            'type': session.get('name', 'Unknown')
                        })
                    except (KeyError, ValueError) as e:
                        print(f"Error processing sleep session: {e}")
                        continue
            
            return sleep_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching sleep data: {e}")
            return []
    
    def get_step_count(self, start_time, end_time):
        """Fetch real step count data from Google Fit"""
        url = f"{self.base_url}/dataset:aggregate"
        
        start_time_millis = int(start_time.timestamp() * 1000)
        end_time_millis = int(end_time.timestamp() * 1000)
        
        body = {
            "aggregateBy": [{
                "dataTypeName": "com.google.step_count.delta",
            }],
            "bucketByTime": {"durationMillis": 86400000},  # 1 day buckets
            "startTimeMillis": start_time_millis,
            "endTimeMillis": end_time_millis
        }
        
        try:
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
                                            'steps': steps
                                        })
                                    except (KeyError, ValueError, IndexError) as e:
                                        print(f"Error processing step point: {e}")
                                        continue
            
            return step_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching step data: {e}")
            return []
    
    def get_calories_data(self, start_time, end_time):
        """Fetch real calories data from Google Fit"""
        url = f"{self.base_url}/dataset:aggregate"
        
        start_time_millis = int(start_time.timestamp() * 1000)
        end_time_millis = int(end_time.timestamp() * 1000)
        
        body = {
            "aggregateBy": [{
                "dataTypeName": "com.google.calories.expended",
            }],
            "bucketByTime": {"durationMillis": 86400000},
            "startTimeMillis": start_time_millis,
            "endTimeMillis": end_time_millis
        }
        
        try:
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
                                            'calories': calories
                                        })
                                    except (KeyError, ValueError, IndexError) as e:
                                        print(f"Error processing calories point: {e}")
                                        continue
            
            return calories_data
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching calories data: {e}")
            return []

class StressAnalysisService:
    def __init__(self):
        self.model = None
        self.load_model()
    
    def load_model(self):
        """Load pre-trained stress analysis model"""
        try:
            # Simple stress calculation based on common metrics
            # In production, you would load a trained ML model
            self.model_loaded = True
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model_loaded = False
    
    def calculate_stress_level(self, heart_rate, steps, sleep_duration, calories):
        """Calculate stress level based on health metrics"""
        # Base stress score (0-100)
        stress_score = 50  # Neutral starting point
        
        # Heart rate impact (resting HR typically 60-100 BPM)
        if heart_rate > 80:
            stress_score += (heart_rate - 80) * 0.5
        elif heart_rate < 60:
            stress_score += (60 - heart_rate) * 0.3
        
        # Activity impact (recommended: 7,000-10,000 steps)
        if steps < 5000:
            stress_score += (5000 - steps) * 0.001
        elif steps > 15000:
            stress_score += (steps - 15000) * 0.0005
        
        # Sleep impact (recommended: 7-9 hours)
        if sleep_duration < 6:
            stress_score += (6 - sleep_duration) * 5
        elif sleep_duration > 10:
            stress_score += (sleep_duration - 10) * 2
        
        # Normalize to 0-100 scale
        stress_score = max(0, min(100, stress_score))
        
        return stress_score
    
    def categorize_stress(self, stress_level):
        """Categorize stress level"""
        if stress_level < 25:
            return 'LOW', 'success'
        elif stress_level < 50:
            return 'MODERATE', 'info'
        elif stress_level < 75:
            return 'HIGH', 'warning'
        else:
            return 'VERY_HIGH', 'danger'

def process_health_data(heart_rate_data, sleep_data, step_data, calories_data):
    """Process and combine all health data"""
    processed_data = []
    
    # Create a date range for the last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        
        # Find heart rate data for this date
        daily_heart_rates = [
            hr['heart_rate'] for hr in heart_rate_data 
            if hr['timestamp'].date() == current_date.date()
        ]
        avg_heart_rate = np.mean(daily_heart_rates) if daily_heart_rates else 72
        
        # Find sleep data for this date
        daily_sleep = [
            sleep['duration_hours'] for sleep in sleep_data 
            if sleep['start_time'].date() == current_date.date()
        ]
        sleep_duration = np.mean(daily_sleep) if daily_sleep else 7.0
        
        # Find step data for this date
        daily_steps = [
            step['steps'] for step in step_data 
            if step['timestamp'].date() == current_date.date()
        ]
        total_steps = sum(daily_steps) if daily_steps else 8000
        
        # Find calories data for this date
        daily_calories = [
            cal['calories'] for cal in calories_data 
            if cal['timestamp'].date() == current_date.date()
        ]
        total_calories = sum(daily_calories) if daily_calories else 2000
        
        # Calculate stress level
        stress_service = StressAnalysisService()
        stress_level = stress_service.calculate_stress_level(
            avg_heart_rate, total_steps, sleep_duration, total_calories
        )
        stress_category, stress_color = stress_service.categorize_stress(stress_level)
        
        processed_data.append({
            'date': date_str,
            'timestamp': current_date,
            'heart_rate': round(avg_heart_rate, 1),
            'sleep_duration': round(sleep_duration, 1),
            'steps': total_steps,
            'calories': round(total_calories, 1),
            'stress_level': round(stress_level, 1),
            'stress_category': stress_category,
            'stress_color': stress_color
        })
        
        current_date += timedelta(days=1)
    
    return processed_data