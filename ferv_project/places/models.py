from django.db import models

# Create your models here.
class Place(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    latitude = models.FloatField()
    longitude = models.FloatField()
    address = models.CharField(max_length=255)
    images = models.ManyToManyField('PlaceImage', related_name='places')
    tags = models.ManyToManyField('PlaceTag', related_name='places')

    def __str__(self):
        return self.name

class PlaceImage(models.Model):
    place = models.ForeignKey(Place, related_name='images', on_delete=models.CASCADE)
    image = models.ImageField(upload_to='place_images/')

    def __str__(self):
        return f"Image for {self.place.name}"
    
class PlaceTag(models.Model):
    place = models.ForeignKey(Place, related_name='tags', on_delete=models.CASCADE)
    tag = models.CharField(max_length=50)

    def __str__(self):
        return f"Tag '{self.tag}' for {self.place.name}"