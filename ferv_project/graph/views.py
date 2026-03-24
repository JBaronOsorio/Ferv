from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from places.models import Place

# Create your views here.
def index(request):
    return render(request, 'graph/index.html')



@login_required
def welcome(request):
    featured_places = Place.objects.prefetch_related('images', 'tags').order_by('-rating')[:8]
    return render(request, 'graph/welcome.html', {
        'featured_places': featured_places,
    })