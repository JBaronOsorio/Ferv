from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import redirect, render

from .forms import LoginForm, RegisterForm


def register_view(request):
    if request.user.is_authenticated:
        return redirect('graph:questionnaire')

    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save(commit=False)
        user.set_password(form.cleaned_data['password'])
        user.save()
        login(request, user)
        request.session.set_expiry(60 * 60 * 24 * 14)
        return redirect('graph:questionnaire')

    return render(request, 'user/register.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('graph:index')

    form = LoginForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            request.session.set_expiry(60 * 60 * 24 * 14)
            return redirect('graph:index')

        messages.error(request, 'Invalid credentials.')

    return render(request, 'user/login.html', {'form': form})


def logout_view(request):
    logout(request)
    return redirect('user:login')
