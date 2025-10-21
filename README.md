### General Disease Prediction based on symptoms provided by patient- powered by Django & Machine Learning


# How To Use This
First make sure PostgreSQL and pgadmin is install in your system. 
then you have to manually create a DB instance on PostgreSQL named "predico", better use PgAdmin for that.
make a new environment(recommended) and run...

- Run pip install -r requirements.txt to install dependencies
- Run python manage.py makemigrations
- Run python manage.py migrate
- Run python manage.py runserver
- Navigate to http://127.0.0.1:8000/ in your browser

### Dataset used - 
https://www.kaggle.com/neelima98/disease-prediction-using-machine-learning

### Some Sceenshots of This Webapp -

![](https://github.com/anuj-glitch/Disease-Prediction-using-Django-and-machine-learning/blob/master/screenshots/Capture1.PNG)
![](https://github.com/anuj-glitch/Disease-Prediction-using-Django-and-machine-learning/blob/master/screenshots/Capture2.PNG)
![](https://github.com/anuj-glitch/Disease-Prediction-using-Django-and-machine-learning/blob/master/screenshots/Capture3.PNG)
![](https://github.com/anuj-glitch/Disease-Prediction-using-Django-and-machine-learning/blob/master/screenshots/Capture4.PNG)
![](https://github.com/anuj-glitch/Disease-Prediction-using-Django-and-machine-learning/blob/master/screenshots/Capture5.PNG)


### ***Go to the [Readme.pdf](Readme.pdf) file for detailed information about the project & screenshots.***
and if you like this project, do give it a "Star" Thank you..
Stress Analysis Dashboard - Complete Documentation


🎯 Overview
The Stress Analysis Dashboard is a comprehensive Django web application that integrates with Google Fit to provide personalized stress analysis based on health metrics including heart rate, sleep patterns, physical activity, and calories burned. The application offers real-time data visualization, correlation analysis, and personalized wellness recommendations.

✨ Features
🔐 Authentication & Integration
Google Fit OAuth Integration - Secure connection to Google Fit API

Session Management - Persistent user sessions and data caching

Auto-refresh - Automatic data synchronization every 5 minutes

📊 Data Visualization
Interactive Charts - 8 different chart types using Chart.js

Real-time Updates - Live data refresh and visualization

Data Source Tracking - Clear indication of real vs demo data

Responsive Design - Mobile-friendly interface

🔍 Analysis Capabilities
Stress Level Tracking - Daily stress level monitoring (0-100 scale)

Health Metrics Correlation - Analysis of stress vs sleep, activity, heart rate

Pattern Recognition - Stress level distribution and trend analysis

Personalized Insights - AI-powered recommendations based on user data

📈 Dashboard Components
Statistics Overview - Key metrics at a glance

Trend Analysis - Weekly and daily trend comparisons

Correlation Matrix - Relationship between different health factors

Recommendation Engine - Personalized wellness suggestions

🛠 Technology Stack
Backend
Django 4.2+ - Python web framework

Django Sessions - User session management

REST API - JSON API endpoints for frontend communication

Frontend
HTML5/CSS3 - Semantic markup and responsive design

JavaScript ES6+ - Modern JavaScript with async/await

Chart.js 3.0+ - Interactive data visualization

Bootstrap 5 - Responsive UI framework

Font Awesome - Icon library

Data Integration
Google Fit API - Health data synchronization

Demo Data Fallback - Sample data when real data unavailable

Real-time Processing - On-the-fly data analysis and correlation

🚀 Installation & Setup
Prerequisites
Python 3.8+

Django 4.2+

Google Cloud Project with Fitness API enabled

Step 1: Clone and Setup
bash
# Clone the project
git clone <repository-url>
cd stress-analysis-dashboard

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install django
pip install requests  # For Google Fit API integration
Step 2: Django Configuration
bash
# Create Django project (if starting from scratch)
django-admin startproject stress_analysis_project .
cd stress_analysis_project

# Create the stress_analysis app
python manage.py startapp stress_analysis
Step 3: Database Setup
bash
# Apply migrations
python manage.py makemigrations
python manage.py migrate

# Create superuser (optional)
python manage.py createsuperuser
Step 4: Google Fit API Setup
Create Google Cloud Project

Go to Google Cloud Console

Create new project or select existing one

Enable Google Fitness API

Configure OAuth 2.0 Credentials

Go to APIs & Services → Credentials

Create OAuth 2.0 Client ID

Set authorized redirect URIs:

http://localhost:8000/stress-analysis/oauth-callback/

https://yourdomain.com/stress-analysis/oauth-callback/

Download Credentials

Download JSON file and save as google_fit_credentials.json

Place in project root directory

⚙ Configuration