from django.urls import path
from graph import views

app_name = 'graph'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/', views.GraphAPIView.as_view(), name='graph-api'),
    path('welcome/', views.welcome, name='welcome'),
    path('map/', views.map_view, name='map'),           # Nueva — visualización del mapa
    path('add-node/', views.add_node, name='add-node'), # Nueva — agregar lugar al mapa
]