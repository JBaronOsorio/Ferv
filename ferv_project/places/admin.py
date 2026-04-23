from django.contrib import admin
from .models import Place, PlaceTag, PlaceDocument

# Register your models here.
admin.site.register(Place)
admin.site.register(PlaceTag)
admin.site.register(PlaceDocument)