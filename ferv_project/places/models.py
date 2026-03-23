from django.db import models

class Place(models.Model):
    place_id = models.CharField(max_length=128, unique=True, db_index=True)
    name = models.CharField(max_length=150)
    address = models.CharField(max_length=500)
    neighborhood = models.CharField(max_length=120, blank=True)
    latitude = models.FloatField()
    longitude = models.FloatField()
    rating = models.FloatField(null=True, blank=True)
    price_level = models.PositiveSmallIntegerField(null=True, blank=True)
    hours = models.JSONField(default=list, blank=True)
    review_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"{self.name} ({self.place_id})"

class PlaceImage(models.Model):
    place = models.ForeignKey(Place, related_name='images', on_delete=models.CASCADE)
    url = models.URLField(max_length=500)
    source_reference = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"Image for {self.place.name}"
    
class PlaceTag(models.Model):
    place = models.ForeignKey(Place, related_name='tags', on_delete=models.CASCADE)
    tag = models.CharField(max_length=60)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["place", "tag"], name="unique_place_tag")
        ]

    def __str__(self):
        return f"Tag '{self.tag}' for {self.place.name}"