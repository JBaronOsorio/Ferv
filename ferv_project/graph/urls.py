from django.urls import path
from graph import views

app_name = 'graph'

urlpatterns = [
    path('', views.index, name='index'),
    path('api/one_shot_recommendation/<str:query>', views.one_shot_recommendation, name='one-shot-recommendation'),
    path('welcome/', views.welcome, name='welcome'),
    path('map/', views.map_view, name='map'),           # Nueva — visualización del mapa
    path('add-node/', views.add_node, name='add-node'), # Nueva — agregar lugar al mapa
    path('api/fetch-graph/', views.fetch_graph, name='fetch-graph'), # Nueva — API para obtener nodos y edges
]