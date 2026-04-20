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
    
    soft_characteristics = models.TextField(
        blank=True,
        help_text='Características suaves o preferencias adicionales del usuario.',
    )

    # Flag que indica si el usuario completó la perfilación inicial.
    # Permite redirigir al cuestionario si aún no lo ha hecho.
    profile_completed = models.BooleanField(default=False)

    def __str__(self):
        return self.username

    def get_profile_as_prompt_text(self) -> str:
        """
        Returns a prompt-ready string combining:
        Part 1 (derived): most frequent tag characteristics across in_graph nodes.
        Part 2 (authored): the user's explicitly set preferences.
        Pure method — no side effects, no caching.
        """
        from collections import Counter
        from graph.models import GraphNode  # lazy import to avoid circular dependency

        # Part 1: derive characteristics from the user's existing in_graph places
        in_graph = (
            GraphNode.objects
            .filter(user=self, status="in_graph")
            .prefetch_related("place__tags")
        )
        tag_counts = Counter(
            t.tag for node in in_graph for t in node.place.tags.all()
        )
        if tag_counts:
            derived = ", ".join(
                f"{tag}({count})" for tag, count in tag_counts.most_common(10)
            )
            part1 = f"Frequent characteristics in user's saved places: {derived}."
        else:
            part1 = ""

        # Part 2: explicit profile preferences
        profile_parts = []
        if self.preferred_place_types:
            profile_parts.append(
                f"Preferred place types: {', '.join(self.preferred_place_types)}."
            )
        if self.preferred_atmospheres:
            profile_parts.append(
                f"Preferred atmospheres: {', '.join(self.preferred_atmospheres)}."
            )
        if self.preferred_activities:
            profile_parts.append(
                f"Favourite activities: {', '.join(self.preferred_activities)}."
            )
        if self.budget_range:
            profile_parts.append(f"Budget range: {self.budget_range}.")
        if self.soft_characteristics:
            profile_parts.append(f"Additional notes: {self.soft_characteristics}.")
        part2 = " ".join(profile_parts)

        return "\n".join(filter(None, [part1, part2]))