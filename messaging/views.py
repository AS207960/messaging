from django.http import HttpResponse


def oauth_redirect(request):
    return HttpResponse(status=200)
