from django.contrib import admin
from .models import GraphNode, GraphEdge

# Register your models here.
admin.site.register(GraphNode)
admin.site.register(GraphEdge)