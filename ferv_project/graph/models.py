from django.conf import settings
from django.db import models



class GraphNode(models.Model):
    
    NODE_STATUS_CHOICES = [
        ('recommendation', 'Recommendation'),
        ('visited', 'Visited'),
        ('in_graph', 'In_Graph'),
        ('discovery', 'Discovery'),
        ('discarded', 'Discarded'),
        ('removed', 'Removed'),
    ]
    
    place = models.ForeignKey('places.Place', related_name='graph_nodes', on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, related_name='graph_nodes', on_delete=models.CASCADE)
    rationale = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=60, blank=False, default='recommendation')
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
    
    REASON_TYPE_CHOICES = [
        ('ambiance', 'Ambiance'),
        ('cuisine', 'Cuisine'),
        ('activity', 'Activity'),
        ('green_space', 'Green Space'),
        ('art_culture', 'Art & Culture'),
        ('family_friendly', 'Family Friendly'),
        ('nightlife', 'Nightlife'),
        ('outdoors', 'Outdoors'),
        ('drinks', 'Drinks'),
    ]
    
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
