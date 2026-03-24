from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import LoginForm, ProfileSetupForm, RegistrationForm


# Vistas de autenticación y configuración de perfil.
def register_view(request):
    
    if request.user.is_authenticated:
        return redirect('graph:index')

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'¡Bienvenido a Ferv, {user.username}! Cuéntanos un poco sobre ti.')
            return redirect('user:profile_setup')
    else:
        form = RegistrationForm()

    return render(request, 'user/register.html', {'form': form})


# Vista de configuración de perfil que se muestra después del registro.
@login_required
def profile_setup_view(request):

    if request.user.profile_completed:
        return redirect('graph:welcome')

    if request.method == 'POST':
        form = ProfileSetupForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Perfil listo! Ya podemos empezar a descubrir la ciudad.')
            return redirect('graph:welcome')
    else:
        form = ProfileSetupForm(instance=request.user)

    return render(request, 'user/profile_setup.html', {'form': form})


# Vista de login que autentica al usuario y lo redirige al grafo.
def login_view(request):
    if request.user.is_authenticated:
        return redirect('graph:welcome')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'¡Hola de nuevo, {user.username}!')

            # Si por alguna razón no completó la perfilación, lo mandamos allá
            if not user.profile_completed:
                return redirect('user:profile_setup')

            return redirect('graph:welcome')
        else:
            messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = LoginForm(request)

    return render(request, 'user/login.html', {'form': form})


# Vista de logout que cierra la sesión del usuario.
def logout_view(request):

    if request.method == 'POST':
        logout(request)
        messages.info(request, 'Sesión cerrada. ¡Hasta pronto!')
    return redirect('user:login')