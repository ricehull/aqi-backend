from django.contrib import admin
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from aqi_app.views import UserViewSet, AQIViewSet

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'aqi', AQIViewSet, basename='aqi')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
] 