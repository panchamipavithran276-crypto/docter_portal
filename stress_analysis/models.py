from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class GoogleFitUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    access_token = models.TextField()
    refresh_token = models.TextField(blank=True, null=True)
    token_expiry = models.DateTimeField(blank=True, null=True)
    fit_user_id = models.CharField(max_length=255, blank=True, null=True)
    is_connected = models.BooleanField(default=False)
    last_sync = models.DateTimeField(blank=True, null=True)
    
    def __str__(self):
        return f"{self.user.username} - Google Fit"

class StressData(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField()
    
    # Heart Rate Data
    heart_rate = models.FloatField(help_text="Heart rate in BPM")
    heart_rate_confidence = models.FloatField(default=0.0)
    
    # Sleep Data
    sleep_duration = models.FloatField(help_text="Sleep duration in hours", null=True, blank=True)
    sleep_quality = models.CharField(
        max_length=20,
        choices=[
            ('DEEP', 'Deep Sleep'),
            ('LIGHT', 'Light Sleep'),
            ('REM', 'REM Sleep'),
            ('AWAKE', 'Awake'),
        ],
        null=True,
        blank=True
    )
    
    # Activity Data
    steps = models.IntegerField(default=0)
    calories = models.FloatField(default=0.0)
    activity_duration = models.FloatField(default=0.0, help_text="Activity duration in minutes")
    
    # Stress Metrics
    stress_level = models.FloatField(help_text="Calculated stress level (0-100)")
    stress_category = models.CharField(
        max_length=20,
        choices=[
            ('LOW', 'Low Stress'),
            ('MODERATE', 'Moderate Stress'),
            ('HIGH', 'High Stress'),
            ('VERY_HIGH', 'Very High Stress'),
        ]
    )
    
    # Environmental Factors
    hrv = models.FloatField(null=True, blank=True, help_text="Heart Rate Variability")
    resting_heart_rate = models.FloatField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.timestamp} - {self.stress_category}"

class StressReport(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    report_date = models.DateField()
    average_stress = models.FloatField()
    max_stress = models.FloatField()
    min_stress = models.FloatField()
    stress_trend = models.CharField(
        max_length=20,
        choices=[
            ('IMPROVING', 'Improving'),
            ('STABLE', 'Stable'),
            ('WORSENING', 'Worsening'),
            ('FLUCTUATING', 'Fluctuating'),
        ]
    )
    recommendations = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.report_date}"