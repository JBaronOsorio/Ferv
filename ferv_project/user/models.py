from django.db import models
from django.contrib.auth.models import AbstractUser


# Create your models here.


# --- Opciones de perfilación ---
# Están definidas como constantes para que en el futuro
# puedan extenderse o reemplazarse por entradas semánticas
# sin tocar la lógica del modelo.

PLACE_TYPE_CHOICES = [
    ('bar', 'Bar'),
    ('cafe', 'Café'),
    ('restaurant', 'Restaurante'),
    ('park', 'Parque'),
    ('gallery', 'Galería'),
    ('bookstore', 'Librería'),
    ('cultural_space', 'Espacio cultural'),
    ('other', 'Otro'),
]

ATMOSPHERE_CHOICES = [
    ('quiet', 'Tranquilo'),
    ('lively', 'Animado'),
    ('intimate', 'Íntimo'),
    ('family', 'Familiar'),
    ('outdoor', 'Al aire libre'),
    ('nightlife', 'Nocturno'),
]

ACTIVITY_CHOICES = [
    ('live_music', 'Música en vivo'),
    ('sports', 'Deporte'),
    ('gastronomy', 'Gastronomía'),
    ('art', 'Arte'),
    ('reading', 'Lectura'),
    ('socializing', 'Socializar'),
    ('nature', 'Naturaleza'),
]

BUDGET_CHOICES = [
    ('low', 'Bajo'),
    ('medium', 'Medio'),
    ('high', 'Alto'),
]


# Modelo de usuario personalizado que extiende AbstractUser para incluir campos de perfilación.
class FervUser(AbstractUser):

    # Perfilación — selección múltiple guardada como lista JSON
    preferred_place_types = models.JSONField(
        default=list,
        blank=True,
        help_text='Tipos de lugar preferidos por el usuario.',
    )
    preferred_atmospheres = models.JSONField(
        default=list,
        blank=True,
        help_text='Ambientes preferidos por el usuario.',
    )
    preferred_activities = models.JSONField(
        default=list,
        blank=True,
        help_text='Actividades de ocio favoritas del usuario.',
    )

    # Perfilación — selección única
    budget_range = models.CharField(
        max_length=10,
        choices=BUDGET_CHOICES,
        blank=True,
        default='',
        help_text='Rango de presupuesto habitual del usuario.',
    )

    # Flag que indica si el usuario completó la perfilación inicial.
    # Permite redirigir al cuestionario si aún no lo ha hecho.
    profile_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.username