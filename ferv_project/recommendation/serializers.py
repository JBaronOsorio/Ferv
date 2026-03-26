from rest_framework import serializers
from places.models import Place, PlaceTag


class PlaceTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlaceTag
        fields = ['tag']


class RecommendationResultSerializer(serializers.ModelSerializer):
    """
    Serializes a Place object as a recommendation result.
    Includes distance score injected at query time.
    """
    tags = PlaceTagSerializer(many=True, read_only=True)
    distance = serializers.FloatField(read_only=True)

    class Meta:
        model = Place
        fields = [
            'place_id',
            'name',
            'neighborhood',
            'rating',
            'price_level',
            'editorial_summary',
            'tags',
            'distance',
        ]