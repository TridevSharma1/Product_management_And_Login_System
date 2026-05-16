from django.urls import path
from .views import *

urlpatterns = [
    path('', product_list, name='product_list'),
    path('product/<int:pk>/', product_detail, name='product_detail'),

    path('create/', product_create, name='product_create'),
    path('update/<int:pk>/', product_update, name='product_update'),
    path('delete/<int:pk>/', product_delete, name='product_delete'),

    path('login/', login_view, name='login'),
    path('signup/', signup, name='signup'),
    path('verify-otp/', verify_otp, name='verify_otp'),
    path('verify-otp/resend/', resend_otp, name='resend_otp'),
    path('logout/', logout_view, name='custom_logout'),
    path('profile/', user_profile, name='profile'),
    path('profile/delete/', delete_account_request, name='delete_account_request'),
    path('profile/delete/confirm/<uidb64>/<token>/', confirm_delete_account, name='confirm_delete_account'),
]