from django.urls import path

from . import views

app_name = 'basic_ui'
urlpatterns = [
    path('', views.all_campaigns_view, name='all_campaigns'),
    path('campaign/<int:campaign_id>/', views.single_campaign_view, name='single_campaign'),
    path('campaign/<int:campaign_id>/discoveries/', views.all_discoveries_view, name='all_discoveries'),
    path('campaign/<int:campaign_id>/discoveries/<str:discovery_id>/', views.single_discovery_view, name='single_discovery'),
    path('campaign/<int:campaign_id>/discoveries/<str:discovery_id>/witness', views.witness_view, name='witness'),
    path('campaign/<int:campaign_id>/measurements-overview/<int:meas_id>', views.measurements_overview_view, name='measurements_overview'),

    path('campaign/<int:campaign_id>/discoveries/<str:discovery_id>/absblock.json', views.discovery_json_view, name='discovery_json'),

    path('no-measurements', views.measurements_empty_view, name='measurements_empty'),
    path('campaign/<int:campaign_id>/measurements/<int:meas_id>', views.measurements_view, name='measurements'),


    path('campaign/<int:campaign_id>/insnschemes/', views.all_insnschemes_view, name='all_insnschemes'),
    path('campaign/<int:campaign_id>/insnschemes/<int:ischeme_id>/', views.single_insnscheme_view, name='single_insnscheme'),
]
