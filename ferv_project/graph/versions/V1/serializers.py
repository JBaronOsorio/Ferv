from rest_framework import serializers
from graph.models import GraphNode, GraphEdge
from places.models import Place, PlaceImage, PlaceTag

class PlaceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceImage
        fields = ['url']

class PlaceTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceTag
        fields = ['tag']
        
class PlaceSerializer(serializers.ModelSerializer):
    images = PlaceImageSerializer(many=True, read_only=True)
    tags = PlaceTagSerializer(many=True, read_only=True)
    
    class Meta:
        model = Place
        fields = ['place_id', 'name', 'rating', 'tags', 'images']

class GraphNodeSerializer(serializers.ModelSerializer):
    place = PlaceSerializer(read_only=True)
    
    class Meta:
        model = GraphNode
        fields = ['id', 'place', 'is_favorite']

class GraphEdgeSerializer(serializers.ModelSerializer):
    source = GraphNodeSerializer(read_only=True, source='from_node')
    target = GraphNodeSerializer(read_only=True, source='to_node')
    
    class Meta:
        model = GraphEdge
        fields = ['source', 'target', 'weight', 'reason', 'reason_type']