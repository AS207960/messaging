from django.http import HttpResponse, HttpResponseBadRequest
import gbc.models
from django.shortcuts import redirect
import urllib.parse
import json
import binascii
import base64
import datetime
import ics


def oauth_redirect(request):
    if "state" not in request.GET:
        return HttpResponseBadRequest()

    if str(request.GET["state"]).startswith("messaging_gbcauthstate"):
        state = gbc.models.OAuthState.objects.filter(id=request.GET["state"]).first()
        if not state:
            return HttpResponseBadRequest()

        auth_url = state.redirect_uri
        auth_params = {
            "state": str(state.google_state)
        }

        if "error" in request.GET:
            auth_params["error"] = str(request.GET["error"])
        elif "code" in request.GET:
            state.auth_code = str(request.GET["code"])
            state.save()
            auth_params["code"] = str(state.id)
        else:
            return HttpResponseBadRequest()

        url_parts = list(urllib.parse.urlparse(auth_url))
        query_parts = dict(urllib.parse.parse_qsl(url_parts[4]))
        query_parts.update(auth_params)
        url_parts[4] = urllib.parse.urlencode(query_parts)
        redirect_uri = urllib.parse.urlunparse(url_parts)

        return redirect(redirect_uri)
    else:
        return HttpResponseBadRequest()


def calendar_event(request, event_data):
    try:
        event_data = json.loads(base64.urlsafe_b64decode(event_data))
    except (binascii.Error, json.JSONDecodeError):
        return HttpResponseBadRequest()

    cal = ics.Calendar()
    event = ics.Event()
    event.begin = datetime.datetime.utcfromtimestamp(event_data["start"])
    event.end = datetime.datetime.utcfromtimestamp(event_data["end"])
    event.name = event_data["title"]
    event.description = event_data["description"]
    cal.events.add(event)

    return HttpResponse(str(cal), status=200, content_type="text/calendar")
