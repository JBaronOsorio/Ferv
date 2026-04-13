from django.db import models
from django.conf import settings
from places.models import Place


class UserNode(models.Model):
    """
    Represents a Place that a user has explicitly added to their personal map.
    One row per user-place pair.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='nodes',
    )
    place = models.ForeignKey(
        Place,
        on_delete=models.CASCADE,
        related_name='user_nodes',
    )
    is_favorite = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'place'], name='unique_user_place')
        ]

    def __str__(self):
        return f"{self.user.username} → {self.place.name}"