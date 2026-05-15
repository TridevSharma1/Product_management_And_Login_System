from datetime import timedelta

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    mobile_no = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} - {self.name}'


class OTPCode(models.Model):
    PURPOSE_REGISTER = 'register'
    PURPOSE_LOGIN = 'login'
    PURPOSE_CHOICES = [
        (PURPOSE_REGISTER, 'Register'),
        (PURPOSE_LOGIN, 'Login'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_codes')
    code = models.CharField(max_length=6)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES)
    created_at = models.DateTimeField(auto_now_add=True)
    used = models.BooleanField(default=False)

    def __str__(self):
        return f'{self.user.username} - {self.purpose} - {self.code}'

    def is_expired(self):
        return self.created_at + timedelta(minutes=10) < timezone.now()

    def mark_used(self):
        self.used = True
        self.save()


class Product(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    image = models.ImageField(upload_to='products/')
    description = models.TextField()
    quantity = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name