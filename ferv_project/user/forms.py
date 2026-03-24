from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm

from .models import (
    ACTIVITY_CHOICES,
    ATMOSPHERE_CHOICES,
    BUDGET_CHOICES,
    PLACE_TYPE_CHOICES,
    FervUser,
)

# Formulario de registro que extiende UserCreationForm para incluir el campo de email.
class RegistrationForm(UserCreationForm):

    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'tu@correo.com'}),
    )

    class Meta:
        model = FervUser
        fields = ('username', 'email', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['placeholder'] = 'Nombre de usuario'
        self.fields['password1'].widget.attrs['placeholder'] = 'Contraseña'
        self.fields['password2'].widget.attrs['placeholder'] = 'Confirmar contraseña'


# Formulario de configuración de perfil que se muestra después del registro.
class ProfileSetupForm(forms.ModelForm):

    preferred_place_types = forms.MultipleChoiceField(
        choices=PLACE_TYPE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='¿Qué tipo de lugares disfrutas?',
        help_text='Selecciona todos los que quieras.',
    )

    preferred_atmospheres = forms.MultipleChoiceField(
        choices=ATMOSPHERE_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='¿Qué ambientes prefieres?',
        help_text='Selecciona todos los que quieras.',
    )

    preferred_activities = forms.MultipleChoiceField(
        choices=ACTIVITY_CHOICES,
        widget=forms.CheckboxSelectMultiple,
        label='¿Qué actividades disfrutas en tu tiempo libre?',
        help_text='Selecciona todas las que quieras.',
    )

    budget_range = forms.ChoiceField(
        choices=[('', 'Selecciona una opción')] + BUDGET_CHOICES,
        label='¿Cuál es tu presupuesto habitual para salir?',
        widget=forms.RadioSelect,
    )

    class Meta:
        model = FervUser
        fields = (
            'preferred_place_types',
            'preferred_atmospheres',
            'preferred_activities',
            'budget_range',
        )

    def save(self, commit=True):
        user = super().save(commit=False)
        user.profile_completed = True
        if commit:
            user.save()
        return user

# Formulario de inicio de sesión que extiende AuthenticationForm para personalizar los placeholders.
class LoginForm(AuthenticationForm):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs['placeholder'] = 'Nombre de usuario'
        self.fields['password'].widget.attrs['placeholder'] = 'Contraseña'