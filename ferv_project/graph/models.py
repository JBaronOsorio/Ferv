from django.conf import settings
from django.db import models


class GraphNode(models.Model):
    place = models.ForeignKey('places.Place', related_name='graph_nodes', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='graph_nodes', on_delete=models.CASCADE)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "place"], name="unique_user_place_node")
        ]

    def __str__(self):
        return f"GraphNode for {self.place.name}"


class GraphEdge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='graph_edges', on_delete=models.CASCADE)
    from_node = models.ForeignKey(GraphNode, related_name='outgoing_edges', on_delete=models.CASCADE)
    to_node = models.ForeignKey(GraphNode, related_name='incoming_edges', on_delete=models.CASCADE)
    weight = models.FloatField(default=1.0)
    reason = models.CharField(max_length=255, blank=True)
    reason_type = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_node", "to_node"], name="unique_edge")
        ]

    def __str__(self):
        return f"Edge from {self.from_node.place.name} to {self.to_node.place.name} (weight={self.weight})"


from django.conf import settings
from django.db import models


class GraphNode(models.Model):
    place = models.ForeignKey('places.Place', related_name='graph_nodes', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='graph_nodes', on_delete=models.CASCADE)
    is_favorite = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "place"], name="unique_user_place_node")
        ]

    def __str__(self):
        return f"GraphNode for {self.place.name}"


class GraphEdge(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='graph_edges', on_delete=models.CASCADE)
    from_node = models.ForeignKey(GraphNode, related_name='outgoing_edges', on_delete=models.CASCADE)
    to_node = models.ForeignKey(GraphNode, related_name='incoming_edges', on_delete=models.CASCADE)
    weight = models.FloatField(default=1.0)
    reason = models.CharField(max_length=255, blank=True)
    reason_type = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["from_node", "to_node"], name="unique_edge")
        ]

    def __str__(self):
        return f"Edge from {self.from_node.place.name} to {self.to_node.place.name} (weight={self.weight})"


class UserNode(models.Model):
    """
    Lugar que el usuario agregó explícitamente a su mapa personal.
    Distinto de GraphNode (que es temporal, generado por el motor de recomendación).
    Un registro por par usuario-lugar.
    """
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='saved_nodes',
    )
    place = models.ForeignKey(
        'places.Place',
        on_delete=models.CASCADE,
        related_name='user_nodes',
    )
    is_favorite = models.BooleanField(default=False)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['user', 'place'], name='unique_user_saved_place')
        ]

    def __str__(self):
        return f"{self.user.username} → {self.place.name}"