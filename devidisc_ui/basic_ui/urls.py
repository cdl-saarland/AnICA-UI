from django.urls import path

from . import views

app_name = 'basic_ui'
urlpatterns = [
    path('', views.all_campaigns, name='all_campaigns'),
    path('campaign/<int:campaign_id>/', views.campaign, name='campaign'),
    path('campaign/<int:campaign_id>/discoveries/', views.all_discoveries, name='all_discoveries'),
    path('campaign/<int:campaign_id>/discoveries/<str:discovery_id>', views.discovery, name='discovery'),

    path('campaign/<int:campaign_id>/insnschemes/', views.all_insnschemes, name='all_insnschemes'),
]
