from django.conf.urls import patterns, url

from cron import views
from players import views as players_views

urlpatterns = patterns('',
    url(r'registration/$', players_views.register, name='players_registration'),
    url(r'registration/([-\w]+)', players_views.activate, name='players_activation'),
    #url(r'changePassword/$', players_views.changePassword, name='players_change_password'),

    url(r'^$', views.index, name='cron_index'),
    url(r'login/', views.login, name='cron_login'),
    url(r'logout/', views.logout_view, name='cron_logout'),
    url(r'mission/([-\w]+)/intro', views.mission_intro, name='cron_mission_intro'),
    url(r'mission/([-\w]+)/briefing', views.mission_briefing, name='cron_mission_briefing'),
    url(r'mission/([-\w]+)/cases', views.mission_cases, name='cron_mission_cases'),
    url(r'mission/([-\w]+)/case/([-\w]+)/intro', views.case_intro, name='cron_case_intro'),
    url(r'mission/([-\w]+)/case/([-\w]+)/provenance/([-\w]+)', views.provenance, name='cron_provenance'),
    url(r'mission/([-\w]+)/case/([-\w]+)/outro', views.case_outro, name='cron_case_outro'),
    url(r'mission/([-\w]+)/debriefing', views.mission_debriefing, name='cron_mission_debriefing'),
    url(r'mission/([-\w]+)/outro', views.mission_outro, name='cron_mission_outro'),
    url(r'mission/([-\w]+)/reset', views.missionInstance_reset, name='cron_mission_reset'),
    url(r'mission/([-\w]+)/delete', views.missionInstance_delete, name='cron_mission_delete'),
    url(r'archive/$', views.archive, name='cron_archive'),
     
    url(r'profile/', views.profile, name='cron_profile'),
    url(r'hack/([-\w]+)', views.hack_document, name='cron_hack_document'),
    url(r'hq/$', views.hq, name='cron_hq'),
    url(r'hq/m/(\d+)/intro', views.hq_mission_intro, name='cron_hq_mission_intro'),
    url(r'hq/m/(\d+)/briefing', views.hq_mission_briefing, name='cron_hq_mission_briefing'),
    url(r'hq/m/(\d+)/cases', views.hq_cases, name='cron_hq_cases'),
    url(r'hq/m/(\d+)/debriefing', views.hq_mission_debriefing, name='cron_hq_mission_debriefing'),
    url(r'hq/m/(\d+)/outro', views.hq_mission_outro, name='cron_hq_mission_outro'),
    url(r'hq/c/(\d+)/intro', views.hq_case_intro, name='cron_hq_case_intro'),
    url(r'hq/c/(\d+)/outro', views.hq_case_outro, name='cron_hq_case_outro'),
)