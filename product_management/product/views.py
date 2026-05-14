from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.contrib import messages
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.urls import reverse
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from .models import Product, UserProfile
from .forms import ProductForm, RegisterForm, LoginForm


# Signup View
def signup(request):
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

            subject = 'Welcome to ProductStore'
            profile = user.profile
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

            messages.success(request, 'Registration successful. A welcome email has been sent!')
            return redirect('product_list')
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
                login(request, user)
                
                try:
                    subject = 'Welcome Back!'
                    message = (
                        f'Hello {user.username},\n\n'
                        'Welcome back, you logged in successfully!\n\n'
                        'Thank you for using ProductStore!'
                    )
                    send_mail(
                        subject, 
                        message, 
                        settings.DEFAULT_FROM_EMAIL, 
                        [user.email], 
                        fail_silently=False
                    )
                    messages.success(request, 'Login successful. A confirmation email has been sent!')
                except Exception as e:
                    messages.warning(request, f'Login successful but email could not be sent: {str(e)}')
                
                return redirect('product_list')
        else:
            # Display form errors
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = LoginForm()
    return render(request, 'registration/login.html', {'form': form})


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