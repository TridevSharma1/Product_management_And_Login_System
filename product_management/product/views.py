from datetime import timedelta
import random

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.utils import timezone
from .models import Product, UserProfile, OTPCode
from .forms import ProductForm, RegisterForm, LoginForm, OTPVerificationForm


OTP_RESEND_DELAY_SECONDS = 60
OTP_RESEND_LIMIT = 5
OTP_RESEND_WINDOW_MINUTES = 60


def generate_otp_code(length=6):
    return ''.join(random.choices('0123456789', k=length))


def get_resend_delay(request):
    last_sent = request.session.get('otp_last_sent')
    if last_sent is None:
        return 0
    last_sent_dt = timezone.datetime.fromisoformat(last_sent)
    if timezone.is_naive(last_sent_dt):
        last_sent_dt = timezone.make_aware(last_sent_dt, timezone.get_current_timezone())
    elapsed = (timezone.now() - last_sent_dt).total_seconds()
    return max(0, OTP_RESEND_DELAY_SECONDS - int(elapsed))


def record_otp_sent(request):
    request.session['otp_last_sent'] = timezone.now().isoformat()
    request.session.modified = True


def send_otp_email(user, code, purpose, request):
    title = 'Verify your account' if purpose == OTPCode.PURPOSE_REGISTER else 'Your login verification code'
    subject = 'Complete your registration' if purpose == OTPCode.PURPOSE_REGISTER else 'Login verification code'
    context = {
        'user': user,
        'code': code,
        'purpose': title,
        'support_email': settings.DEFAULT_FROM_EMAIL,
        'site_url': request.build_absolute_uri('/'),
    }
    text_body = render_to_string('registration/email/otp_email.txt', context)
    html_body = render_to_string('registration/email/otp_email.html', context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_body, 'text/html')
    try:
        email.send(fail_silently=False)
        return True
    except Exception as e:
        messages.error(request, 'Unable to send OTP email. Please check your email settings or try again later.')
        return False


def send_welcome_email(user, request):
    subject = 'Welcome to ProductStore'
    profile = getattr(user, 'profile', None)
    context = {
        'user': user,
        'profile': profile,
        'site_name': 'ProductStore',
        'support_email': settings.DEFAULT_FROM_EMAIL,
        'site_url': request.build_absolute_uri('/'),
    }
    text_body = render_to_string('registration/email/welcome_email.txt', context)
    html_body = render_to_string('registration/email/welcome_email.html', context)
    email = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email]
    )
    email.attach_alternative(html_body, 'text/html')
    email.send(fail_silently=False)


# Signup View
def signup(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()

            UserProfile.objects.create(
                user=user,
                name=form.cleaned_data['name'],
                city=form.cleaned_data['city'],
                mobile_no=form.cleaned_data['mobile_no']
            )

            code = generate_otp_code()
            if send_otp_email(user, code, OTPCode.PURPOSE_REGISTER, request):
                OTPCode.objects.create(user=user, code=code, purpose=OTPCode.PURPOSE_REGISTER)
                record_otp_sent(request)
                request.session['otp_user_id'] = user.pk
                request.session['otp_purpose'] = OTPCode.PURPOSE_REGISTER
                messages.success(request, 'Registration successful. Enter the 6-digit code sent to your email to verify your account.')
                return redirect('verify_otp')
            messages.error(request, 'Registration succeeded, but the verification code could not be sent. Please try logging in again later.')
            return redirect('signup')
    else:
        form = RegisterForm()
    return render(request, 'registration/signup.html', {'form': form})


# Login View
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.cleaned_data.get('user')
            if user:
                code = generate_otp_code()
                if send_otp_email(user, code, OTPCode.PURPOSE_LOGIN, request):
                    OTPCode.objects.create(user=user, code=code, purpose=OTPCode.PURPOSE_LOGIN)
                    record_otp_sent(request)
                    request.session['otp_user_id'] = user.pk
                    request.session['otp_purpose'] = OTPCode.PURPOSE_LOGIN
                    messages.success(request, 'A verification code has been sent to your email. Enter it to complete login.')
                    return redirect('verify_otp')
                messages.error(request, 'Unable to send verification email. Please try again later.')
                return redirect('login')
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = LoginForm()
    return render(request, 'registration/login.html', {'form': form})


def verify_otp(request):
    otp_user_id = request.session.get('otp_user_id')
    otp_purpose = request.session.get('otp_purpose')
    if not otp_user_id or not otp_purpose:
        messages.error(request, 'No verification request found. Please login or sign up again.')
        return redirect('login')

    try:
        user = User.objects.get(pk=otp_user_id)
    except User.DoesNotExist:
        messages.error(request, 'Verification request is invalid. Please try again.')
        return redirect('login')

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data['code']
            otp = OTPCode.objects.filter(
                user=user,
                purpose=otp_purpose,
                code=code,
                used=False
            ).order_by('-created_at').first()

            if otp is None or otp.is_expired():
                form.add_error('code', 'The verification code is invalid or has expired.')
            else:
                otp.mark_used()
                if otp_purpose == OTPCode.PURPOSE_REGISTER:
                    user.is_active = True
                    user.save()
                    try:
                        send_welcome_email(user, request)
                    except Exception:
                        pass
                    login(request, user)
                    messages.success(request, 'Your account is verified and you are now logged in.')
                    return redirect('product_list')

                login(request, user)
                messages.success(request, 'Login successful. You are now logged in.')
                return redirect('product_list')
    else:
        form = OTPVerificationForm()

    resend_wait_seconds = get_resend_delay(request)
    return render(request, 'registration/verify_otp.html', {
        'form': form,
        'email': user.email,
        'purpose': otp_purpose,
        'resend_wait_seconds': resend_wait_seconds,
    })


def resend_otp(request):
    otp_user_id = request.session.get('otp_user_id')
    otp_purpose = request.session.get('otp_purpose')
    if not otp_user_id or not otp_purpose:
        messages.error(request, 'No verification request found. Please login or sign up again.')
        return redirect('login')

    try:
        user = User.objects.get(pk=otp_user_id)
    except User.DoesNotExist:
        messages.error(request, 'Verification request is invalid. Please try again.')
        return redirect('login')

    wait_seconds = get_resend_delay(request)
    if wait_seconds > 0:
        messages.error(request, f'Please wait {wait_seconds} seconds before requesting a new code.')
        return redirect('verify_otp')

    one_hour_ago = timezone.now() - timedelta(minutes=OTP_RESEND_WINDOW_MINUTES)
    recent_count = OTPCode.objects.filter(
        user=user,
        purpose=otp_purpose,
        created_at__gte=one_hour_ago
    ).count()
    if recent_count >= OTP_RESEND_LIMIT:
        messages.error(request, 'You have reached the maximum number of resend attempts. Please try again later.')
        return redirect('verify_otp')

    code = generate_otp_code()
    OTPCode.objects.create(user=user, code=code, purpose=otp_purpose)
    send_otp_email(user, code, otp_purpose, request)
    record_otp_sent(request)
    messages.success(request, 'A new verification code has been sent to your email.')
    return redirect('verify_otp')


# Logout View
def logout_view(request):
    logout(request)
    return redirect('product_list')


# User Profile View (Only Logged In User)
@login_required
def user_profile(request):
    user = request.user
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = None
    
    return render(request, 'registration/profile.html', {
        'user': user,
        'profile': profile
    })


@login_required
def delete_account_request(request):
    user = request.user
    if request.method == 'POST':
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)
        confirm_url = request.build_absolute_uri(
            reverse('confirm_delete_account', kwargs={'uidb64': uid, 'token': token})
        )

        subject = 'Confirm your account deletion'
        message = (
            f'Hello {user.username},\n\n'
            'You requested to delete your account.\n\n'
            'Please click the link below to confirm and permanently delete your account:\n\n'
            f'{confirm_url}\n\n'
            'If you did not request this, please ignore this email.\n'
            'This link can only be used once.'
        )
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)
        messages.success(request, 'A confirmation email has been sent to your address. Follow the link to complete account deletion.')
        return redirect('profile')

    return render(request, 'registration/delete_account.html', {
        'user': user
    })


def confirm_delete_account(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is None or not default_token_generator.check_token(user, token):
        messages.error(request, 'The deletion link is invalid or has expired.')
        return redirect('profile')

    if request.method == 'POST':
        username = user.username
        user.delete()
        messages.success(request, f'Account {username} has been permanently deleted.')
        return redirect('product_list')

    return render(request, 'registration/confirm_delete_account.html', {
        'user': user
    })


# Product List (Public)
def product_list(request):
    products = Product.objects.all().order_by('-created_at')
    return render(request, 'products/product_list.html', {
        'products': products
    })


# Product Detail (Public)
def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'products/product_detail.html', {
        'product': product
    })


# Create Product (Only Logged In User)
@login_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)

        if form.is_valid():
            form.save()
            return redirect('product_list')

    else:
        form = ProductForm()

    return render(request, 'products/product_form.html', {
        'form': form
    })


# Update Product (Only Logged In User)
@login_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        form = ProductForm(
            request.POST,
            request.FILES,
            instance=product
        )

        if form.is_valid():
            form.save()
            return redirect('product_list')

    else:
        form = ProductForm(instance=product)

    return render(request, 'products/product_form.html', {
        'form': form
    })


# Delete Product (Only Logged In User)
@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)

    if request.method == 'POST':
        product.delete()
        return redirect('product_list')

    return render(request, 'products/product_confirm_delete.html', {
        'product': product
    })