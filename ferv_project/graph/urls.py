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
    path('api/delete_node/<int:node_id>', views.delete_node, name='delete_node'),
    path('api/discovery-list/', views.discovery_list, name='discovery-list'),
    path('api/favorites-list/', views.favorites_list, name='favorites-list'),
    path('api/add-to-discovery/', views.add_to_discovery, name='add-to-discovery'),
    path('api/toggle-favorite/<int:node_id>/', views.toggle_favorite, name='toggle-favorite'),
    path('api/mark-visited/<int:node_id>/', views.mark_visited, name='mark-visited'),
    path('api/stats/', views.user_stats, name='stats'),
]