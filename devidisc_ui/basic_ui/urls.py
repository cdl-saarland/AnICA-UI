from django.urls import path

from . import views

app_name = 'basic_ui'
urlpatterns = [
    path('', views.index, name='index'),
    path('campaign/<int:campaign_id>/', views.campaign, name='campaign'),
    path('campaign/<int:campaign_id>/discoveries/', views.discoveries, name='discoveries'),
    # path('campaign/', views.DiscoveryTableView.as_view(), name='all_discoveries'),
]
