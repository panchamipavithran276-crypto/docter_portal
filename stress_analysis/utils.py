import os
import json
from django.conf import settings
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from django.core.exceptions import ImproperlyConfigured
import datetime

# Allow HTTP for local development - THIS IS CRUCIAL
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def get_google_fit_auth_url(request):
    """Generate Google Fit OAuth URL with proper error handling"""
    try:
        client_secret_file = os.path.join(settings.BASE_DIR, 'client_secret.json')
        
        if not os.path.exists(client_secret_file):
            raise ImproperlyConfigured(
                f"Google Fit client secret file not found at: {client_secret_file}"
            )
        
        # Create flow instance
        flow = Flow.from_client_secrets_file(
            client_secret_file,
            scopes=[
                'https://www.googleapis.com/auth/fitness.activity.read',
                'https://www.googleapis.com/auth/fitness.heart_rate.read',
                'https://www.googleapis.com/auth/fitness.sleep.read',
                'https://www.googleapis.com/auth/fitness.body.read'
            ]
        )
        
        # Use HTTP for local development
        flow.redirect_uri = 'http://localhost:8000/stress-analysis/google-fit-callback/'
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Store the state in the session for later validation
        request.session['google_fit_state'] = state
        request.session['google_fit_redirect_uri'] = flow.redirect_uri
        
        return authorization_url
        
    except Exception as e:
        print(f"Error generating auth URL: {e}")
        raise

def get_google_fit_credentials(request):
    """Get Google Fit credentials from session"""
    try:
        if 'google_fit_credentials' not in request.session:
            return None
            
        cred_data = request.session['google_fit_credentials']
        credentials = Credentials(
            token=cred_data.get('token'),
            refresh_token=cred_data.get('refresh_token'),
            token_uri=cred_data.get('token_uri', 'https://oauth2.googleapis.com/token'),
            client_id=cred_data.get('client_id'),
            client_secret=cred_data.get('client_secret'),
            scopes=cred_data.get('scopes', [])
        )
        
        # Refresh token if expired
        if credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                save_credentials_to_session(request, credentials)
            except Exception as e:
                print(f"Error refreshing token: {e}")
                return None
                
        return credentials
        
    except Exception as e:
        print(f"Error getting credentials: {e}")
        return None

def save_credentials_to_session(request, credentials):
    """Save credentials to session"""
    request.session['google_fit_credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes,
        'expiry': credentials.expiry.isoformat() if credentials.expiry else None
    }
    request.session.modified = True

def exchange_code_for_token(request, authorization_response):
    """Exchange authorization code for tokens"""
    try:
        client_secret_file = os.path.join(settings.BASE_DIR, 'client_secret.json')
        
        flow = Flow.from_client_secrets_file(
            client_secret_file,
            scopes=[
                'https://www.googleapis.com/auth/fitness.activity.read',
                'https://www.googleapis.com/auth/fitness.heart_rate.read',
                'https://www.googleapis.com/auth/fitness.sleep.read',
                'https://www.googleapis.com/auth/fitness.body.read'
            ],
            state=request.session.get('google_fit_state')
        )
        
        flow.redirect_uri = request.session.get('google_fit_redirect_uri')
        
        flow.fetch_token(authorization_response=authorization_response)
        
        return flow.credentials
        
    except Exception as e:
        print(f"Error exchanging code for token: {e}")
        raise

def is_google_fit_configured():
    """Check if Google Fit is properly configured"""
    try:
        client_secret_file = os.path.join(settings.BASE_DIR, 'client_secret.json')
        return os.path.exists(client_secret_file)
    except:
        return False