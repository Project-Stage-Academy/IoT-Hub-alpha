from django.http import HttpResponse


def index(request):
    return HttpResponse("IoT Hub Alpha: System Online")


def health(request):
    return HttpResponse("ok")
