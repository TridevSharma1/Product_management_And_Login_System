from django.urls import path
from . import views

urlpatterns = [
    path('', views.product_list, name='product_list'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),

    path('create/', views.product_create, name='product_create'),
    path('update/<int:pk>/', views.product_update, name='product_update'),
    path('delete/<int:pk>/', views.product_delete, name='product_delete'),

    path('login/', views.login_view, name='login'),
    path('signup/', views.signup, name='signup'),
    path('verify-otp/', views.verify_otp, name='verify_otp'),
    path('verify-otp/resend/', views.resend_otp, name='resend_otp'),
    path('logout/', views.logout_view, name='custom_logout'),
    path('profile/', views.user_profile, name='profile'),
    path('profile/delete/', views.delete_account_request, name='delete_account_request'),
    path('profile/delete/confirm/<uidb64>/<token>/', views.confirm_delete_account, name='confirm_delete_account'),
]